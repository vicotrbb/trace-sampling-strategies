#!/usr/bin/env python3
"""Two bounded live applications. Injection controls are never span attributes."""
import argparse
from contextvars import ContextVar
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import http.client
import json
import os
from queue import Queue
import random
import signal
import threading
import psycopg
from opentelemetry import trace
from opentelemetry.propagate import extract, inject
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.id_generator import IdGenerator
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.trace import SpanKind, Status, StatusCode

root_id = ContextVar('opaque_root_id', default=None)

class OpaqueIdGenerator(IdGenerator):
    def generate_trace_id(self):
        return root_id.get() or random.getrandbits(128) or 1
    def generate_span_id(self):
        return random.getrandbits(64) or 1

def sid(span):
    return format(span.get_span_context().span_id, '016x')

def main():
    assert os.environ.get('STUDY_CONTEXT') == 'homelab'
    p = argparse.ArgumentParser()
    p.add_argument('--app', choices=['checkout', 'documents'], required=True)
    p.add_argument('--role', choices=['gateway', 'worker'], required=True)
    p.add_argument('--rate', type=float, required=True)
    a = p.parse_args()
    provider = TracerProvider(resource=Resource.create({'service.name': a.app + '-' + a.role}),
                              sampler=ParentBased(TraceIdRatioBased(a.rate)), id_generator=OpaqueIdGenerator())
    processor = BatchSpanProcessor(OTLPSpanExporter(endpoint='http://127.0.0.1:4318/v1/traces', timeout=10),
                                   max_queue_size=8192, max_export_batch_size=256, schedule_delay_millis=200)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    tracer = trace.get_tracer('live-observability-study', '1.0')
    pool = Queue()
    if a.role == 'worker':
        for _ in range(16):
            pool.put(psycopg.connect(os.environ['PG_DSN'], autocommit=True))

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'
        def log_message(self, *args): pass
        def reply(self, value, code=200):
            data = json.dumps(value, separators=(',', ':')).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        def do_GET(self):
            if self.path == '/health': self.reply({'ready': True}); return
            if self.path == '/flush': self.reply({'flushed': provider.force_flush(timeout_millis=15000)}); return
            self.reply({'error': 'unknown'}, 404)
        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            control = int(self.headers.get('X-Study-Control', '0'))
            if a.role == 'gateway':
                # No incoming traceparent is used here: every gateway request is a root.
                rid = self.headers['X-Request-Id']
                token = root_id.set(int.from_bytes(hashlib.sha256(rid.encode()).digest()[:16], 'big'))
                try:
                    with tracer.start_as_current_span('gateway.request', kind=SpanKind.SERVER) as root:
                        ids = {'gateway.request': sid(root)}
                        with tracer.start_as_current_span('worker.call', kind=SpanKind.CLIENT) as call:
                            ids['worker.call'] = sid(call)
                            headers = {'Content-Type': 'application/json', 'X-Study-Control': str(control)}
                            inject(headers)
                            conn = http.client.HTTPConnection('127.0.0.1', 8082, timeout=15)
                            conn.request('POST', '/process', json.dumps(data), headers)
                            response = conn.getresponse()
                            result = json.loads(response.read())
                            conn.close()
                            if response.status >= 500:
                                call.set_status(Status(StatusCode.ERROR))
                                root.set_status(Status(StatusCode.ERROR))
                            ids.update(result['span_ids'])
                            result.update(trace_id=format(root.get_span_context().trace_id, '032x'),
                                          span_ids=ids, sampled=root.get_span_context().trace_flags.sampled)
                        self.reply(result, response.status)
                finally:
                    root_id.reset(token)
            else:
                context = extract(dict(self.headers.items()))
                with tracer.start_as_current_span('worker.request', context=context, kind=SpanKind.SERVER) as work:
                    ids = {'worker.request': sid(work)}
                    failed = False
                    conn = pool.get()
                    try:
                        with tracer.start_as_current_span('db.query', kind=SpanKind.CLIENT,
                                attributes={'db.system.name': 'postgresql', 'server.address': 'postgresql',
                                            'db.operation.name': 'SELECT'}) as db:
                            ids['db.query'] = sid(db)
                            try:
                                if control == 1: conn.execute('SELECT amount FROM absent_study_relation').fetchone()
                                elif control == 2: conn.execute('SELECT pg_sleep(0.35)').fetchone()
                                if a.app == 'checkout':
                                    rows = conn.execute('SELECT unit_price FROM study_products ORDER BY id').fetchall()
                                    actual = sum(price[0] * quantity for price, quantity in zip(rows, data['quantities']))
                                    expected = sum(price * quantity for price, quantity in zip([100, 250, 75], data['quantities']))
                                else:
                                    content = conn.execute('SELECT content FROM study_documents WHERE id=%s', (data['document_id'],)).fetchone()[0]
                                    actual = len(content.casefold().split())
                                    expected = data['expected_tokens']
                                if control == 3: actual -= 1
                            except psycopg.Error as error:
                                db.set_attribute('db.response.status_code', error.sqlstate or 'unknown')
                                db.set_attribute('exception.type', type(error).__name__)
                                db.set_status(Status(StatusCode.ERROR))
                                failed = True
                                actual = expected = 0
                    finally:
                        pool.put(conn)
                    # Five spans occur in every request, including SQL errors.
                    with tracer.start_as_current_span('domain.validate', attributes={
                            'domain.expected': expected, 'domain.actual': actual,
                            'domain.owner': a.app + '-worker'}) as validation:
                        ids['domain.validate'] = sid(validation)
                    if failed: work.set_status(Status(StatusCode.ERROR))
                    self.reply({'result': actual, 'span_ids': ids}, 500 if failed else 200)

    ThreadingHTTPServer.request_queue_size = 128
    server = ThreadingHTTPServer(('127.0.0.1', 8081 if a.role == 'gateway' else 8082), Handler)
    def shutdown(*_): threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, shutdown)
    try: server.serve_forever(poll_interval=.1)
    finally:
        server.server_close()
        provider.shutdown()
        while not pool.empty(): pool.get().close()

if __name__ == '__main__': main()
