import timeit

setup = """
import json
buffer = '{"run_in_background": true,'
"""

stmt_1 = """
try:
    args_json = json.loads(buffer)
except Exception:
    pass
"""

stmt_2 = """
if buffer.strip().endswith('}'):
    try:
        args_json = json.loads(buffer)
    except Exception:
        pass
"""

print("stmt_1 (always parse):", timeit.timeit(stmt_1, setup=setup, number=1000000))
print("stmt_2 (heuristic parse):", timeit.timeit(stmt_2, setup=setup, number=1000000))
