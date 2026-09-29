#!/usr/bin/env python3
"""Reconstruct the final batching explanation from archived JSON and counters."""
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
from publication_receipts import write_receipt
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/final-publication-20260928'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def metric(text, name):
    return sum(float(line.rsplit(' ', 1)[1]) for line in text.splitlines()
               if re.match(r'^' + re.escape(name) + r'(?:_total)?(?:\{| )', line))


def main():
    base = ROOT / 'data/raw/fifth-audit-20260928/batching-confirm-v2'
    rows = []
    for block in sorted(base.glob('block-*')):
        for cell in sorted(block.glob('batching-*')):
            config = json.loads((cell / 'config.json').read_text())
            batch = config['processors']['batch']
            timeout = int(batch['timeout'].removesuffix('ms'))
            tail = 'tail_sampling' in config['processors']
            assert (batch['send_batch_size'], batch['send_batch_max_size']) == (256, 512)
            counts = Counter()
            first_partial = last_partial = None
            with gzip.open(cell / 'traces.jsonl.gz', 'rt') as stream:
                for line in stream:
                    obj = json.loads(line)
                    spans = [s for r in obj['resourceSpans']
                             for scope in r['scopeSpans'] for s in scope['spans']]
                    phases = {a['value']['stringValue'] for s in spans
                              for a in s['attributes'] if a['key'] == 'study.phase'}
                    assert len(phases) == 1, cell
                    if phases != {'measured'}:
                        continue
                    size = len(spans)
                    counts[size] += 1
                    if size < 256:
                        if first_partial is None:
                            first_partial = size
                        last_partial = size
            before = (cell / 'collector-metrics-before.txt').read_text()
            after = (cell / 'collector-metrics-after.txt').read_text()
            names = ['otelcol_processor_batch_batch_size_trigger_send',
                     'otelcol_processor_batch_timeout_trigger_send']
            size_triggers, timeout_triggers = [int(metric(after, n) - metric(before, n)) for n in names]
            assert sum(n * c for n, c in counts.items()) == 300000
            assert sum(counts.values()) == size_triggers + timeout_triggers
            if not tail:
                assert counts == {300: 1000}
                assert (size_triggers, timeout_triggers) == (1000, 0)
            elif timeout == 100:
                assert counts[260] == 1139
                assert sum(c for n, c in counts.items() if n < 256) == 61
                assert (size_triggers, timeout_triggers) == (1139, 61)
            else:
                assert timeout == 1000 and counts == {260: 1153, 220: 1}
                assert (size_triggers, timeout_triggers) == (1153, 1)
            rows.append({'cell': cell.relative_to(ROOT).as_posix(), 'timeout_ms': timeout,
                         'tail': tail, 'measured_spans': 300000,
                         'batch_size_histogram': dict(sorted(counts.items())),
                         'size_triggers': size_triggers, 'timeout_triggers': timeout_triggers,
                         'first_partial': first_partial, 'last_partial': last_partial,
                         'json_sha256': sha(cell / 'traces.jsonl.gz')})
    assert len(rows) == 20
    source = OUT / 'sources/batch_processor.go'
    code = source.read_text()
    assert 'b.batch.add(item)' in code
    assert 'b.batch.itemCount() >= b.processor.sendBatchSize' in code
    assert 'bt.itemCount() > sendBatchMaxSize' in code
    assert 'b.resetTimer()' in code
    result = {'status': 'PASS', 'utc': datetime.now(timezone.utc).isoformat(),
              'cells': len(rows), 'measured_spans_reconstructed': 6000000,
              'raw_observations_modified': False, 'batch_source_sha256': sha(source),
              'observed_short_timeout_is_not_1140_size_plus_60_timeout': True,
              'rows': rows}
    result = write_receipt(OUT / 'batch-mechanism-validation.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'rows'}, indent=2))


if __name__ == '__main__':
    main()
