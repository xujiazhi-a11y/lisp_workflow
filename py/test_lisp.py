#!/usr/bin/env python3
import re
import io

# 测试正则匹配
TOKEN_PATTERN = r'''\s*([('`,)]|"(?:[^"\\]|\\.)*"|;.*|[^\s('"`,;)]*)(.*)'''

print("=== 问题分析 ===")
print()

# 在 workflow_server.py 中，HTML 中的 Lisp 代码示例
# 当这个代码作为 JavaScript 字符串被处理后，发送到后端时，
# 字符串 "[{\"chapter\": \"引言\"}]" 实际上变成了:
# [{"chapter": "引言"}]

# 让我们测试这个字符串在 tokenizer 中的行为
test = '"[{"chapter": "引言"}]"'
print("测试字符串:", repr(test))
print("字符:", list(test))
print()

# 正则匹配
matched = re.match(TOKEN_PATTERN, test, re.DOTALL)
if matched:
    print("匹配到的 token:", repr(matched.group(1)))
    print("剩余:", repr(matched.group(2)))
else:
    print("没有匹配")

print()
print("=== 问题根源 ===")
print("正则表达式 \"(?:[^\"\\\\]|\\\\.)*\" 在遇到未转义的引号时停止。")
print("在字符串 '[{chapter}]' 中，位置 3 的引号被认为是字符串结束符。")
print()

# 解决方案：修改 workflow_server.py 中的示例代码
# 使用单引号定义字符串，或使用不同的格式

# 选项 1: 使用不同的格式定义 JSON
print("=== 测试不同格式 ===")

# 如果我们把 JSON 定义为变量，然后引用
test2 = '(get item "chapter")'
matched2 = re.match(TOKEN_PATTERN, test2, re.DOTALL)
if matched2:
    print("测试2:", repr(test2))
    print("Token:", repr(matched2.group(1)))
    print("Remainder:", repr(matched2.group(2)))

print()
# 问题在于 "chapter" 被正确解析为字符串...
# 让我再检查一下

print("=== 检查转义引号 ===")
test3 = '"\\""'  # 转义引号字符串
print("测试3:", repr(test3))
matched3 = re.match(TOKEN_PATTERN, test3, re.DOTALL)
if matched3:
    print("Token:", repr(matched3.group(1)))
else:
    print("没有匹配")