import timeit

setup = """
import json

incomplete_json = '{"key": "value", "another":'
complete_json = '{"key": "value", "another": "value"}'

def parse_with_exception(data):
    try:
        return json.loads(data)
    except Exception:
        return None

def parse_with_heuristic(data):
    if not data.rstrip().endswith("}"):
        return None
    try:
        return json.loads(data)
    except Exception:
        return None
"""

print(
    "parse_with_exception (incomplete):",
    timeit.timeit("parse_with_exception(incomplete_json)", setup=setup, number=1000000),
)
print(
    "parse_with_heuristic (incomplete):",
    timeit.timeit("parse_with_heuristic(incomplete_json)", setup=setup, number=1000000),
)
