import timeit

setup = """
import json
"""

stmt_1 = """
try:
    json.loads('{"a": 1, "b":')
except json.JSONDecodeError:
    pass
"""

stmt_2 = """
val = '{"a": 1, "b":'
if val.rstrip().endswith('}'):
    try:
        json.loads(val)
    except json.JSONDecodeError:
        pass
"""

print(
    "stmt_1 (continually calling json.loads on incomplete JSON):",
    timeit.timeit(stmt_1, setup=setup, number=1000000),
)
print(
    "stmt_2 (heuristic check before json.loads):",
    timeit.timeit(stmt_2, setup=setup, number=1000000),
)
