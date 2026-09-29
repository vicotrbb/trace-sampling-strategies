"""Write a validation receipt without changing an identical verified snapshot."""
import json


def write_receipt(path, result):
    result = json.loads(json.dumps(result))
    if path.exists():
        previous = json.loads(path.read_text())
        without_time = lambda value: {key: item for key, item in value.items() if key != 'utc'}
        if without_time(previous) == without_time(result):
            return previous
    path.write_text(json.dumps(result, indent=2) + '\n')
    return result
