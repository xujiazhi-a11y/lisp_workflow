import sys
sys.path.insert(0, '.')
from workflow_lisp import run, GLOBAL_ENV, parse, Tokenizer, evaluate

GLOBAL_ENV['print'] = lambda *args: print(' '.join(str(a) for a in args))

# 测试 lambda body 中的字符串
print("=== 测试 1: 简单 lambda ===")
result = run("((lambda [x] x) 100)")
print(f"结果: {result}")

print("\n=== 测试 2: Lambda 带字符串参数 ===")
result2 = run('((lambda [x] (str "A" x)) "B")')
print(f"结果: {result2}")

print("\n=== 测试 3: 验证 AST ===")
import io
test = '(lambda [x] (str "A" x))'
tokens = Tokenizer(io.StringIO(test))
ast = parse(tokens)
print(f"AST: {ast}")
lambda_body = ast[2]  # body
print(f"lambda body: {lambda_body}")
print(f"body[1]: {repr(lambda_body[1])}, type: {type(lambda_body[1])}")

print("\n=== 测试 4: 检查 lambda 参数处理 ===")
# 检查带 __data__ 标记的参数
test2 = '(lambda [c f] (f c))'
tokens2 = Tokenizer(io.StringIO(test2))
ast2 = parse(tokens2)
print(f"AST: {ast2}")
params = ast2[1]
print(f"params: {params}")
print(f"params[1]: {repr(params[1])}, type: {type(params[1])}")  # 'c'
print(f"params[2]: {repr(params[2])}, type: {type(params[2])}")  # 'f'