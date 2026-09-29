#!/usr/bin/env python3
"""Post-collection inspection of framing in every archived cost-study cell.

This explains recorded JSON-byte differences. It adds no treatment, confidence
procedure, or acceptance-based exclusion to the frozen experiment.
"""
from collections import defaultdict
from datetime import datetime, timezone
import argparse
import gzip
import json
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('raw', type=Path, nargs='?', default=ROOT / 'data/raw/final-cost-20260925/confirm-v1')
BASE = parser.parse_args().raw
manifest = json.loads((BASE / 'corpus/manifest.json').read_text())
measured = set(manifest['phases']['measured']['trace_ids'])
warmup = set(manifest['phases']['warmup']['trace_ids'])
groups = defaultdict(list)
rows = []
for result_path in sorted(BASE.glob('block-*/*/result.json')):
    result = json.loads(result_path.read_text())
    row = {key: result[key] for key in ('block', 'export', 'timeout_ms', 'sampler')}
    row.update(batches=0, resource_groups=0, scope_groups=0, spans=0, json_bytes=0)
    raw = gzip.decompress((result_path.parent / 'traces.jsonl.gz').read_bytes())
    for line in raw.splitlines(keepends=True):
        resource_groups = json.loads(line)['resourceSpans']
        scopes = [scope for resource in resource_groups for scope in resource['scopeSpans']]
        spans = [span for scope in scopes for span in scope['spans']]
        ids = {span['traceId'] for span in spans}
        assert ids and (ids <= measured or ids <= warmup)
        if ids <= measured:
            row['batches'] += 1
            row['resource_groups'] += len(resource_groups)
            row['scope_groups'] += len(scopes)
            row['spans'] += len(spans)
            row['json_bytes'] += len(line)
    assert row['batches'] == result['batch_count']
    assert row['spans'] == result['export_spans_measured']
    assert row['json_bytes'] == result['export_json_bytes_measured']
    groups[f"{result['export']}-{result['timeout_ms']}-{result['sampler']}"].append(row)
    rows.append(row)
assert len(rows) == 96 and all(len(group) == 8 for group in groups.values())
summary = {key: {field: {'values': [r[field] for r in group], 'mean': mean(r[field] for r in group)}
                   for field in ('batches', 'resource_groups', 'scope_groups', 'spans', 'json_bytes')}
           for key, group in sorted(groups.items())}
receipt = {'status': 'PASS', 'utc': datetime.now(timezone.utc).isoformat(),
           'scope': 'Post-collection descriptive framing inspection, additional to frozen primary analysis',
           'cells': len(rows), 'rows': rows, 'groups': summary}
output = ROOT / 'data/derived/final-cost-20260925/serialization-inspection.json'
output.write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({key: {field: value['mean'] for field, value in group.items()}
                  for key, group in summary.items()}, indent=2))
