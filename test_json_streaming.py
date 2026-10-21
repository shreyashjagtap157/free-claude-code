
buffer = '{"test": 12'
if not buffer.rstrip().endswith("}"):
    print("Optimization triggered!")
else:
    print("Optimization failed!")
