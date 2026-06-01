import re

pattern = r'''\s*([('`,)]|"(?:[\\].|[^\\"\n])*"|;.*|[^\s('"`,;)]*)([\s\S]*)'''

with open('test_debug.lisp', 'r') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    print(f'行{i}: {repr(line)}')
    try:
        m = re.match(pattern, line)
        if m:
            print(f'  token: {repr(m.group(1))}')
            print(f'  剩余: {repr(m.group(2))}')
    except Exception as e:
        print(f'  错误: {e}')
