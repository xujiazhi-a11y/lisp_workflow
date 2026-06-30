"""
用户可见错误信息格式化（中文）
"""

import re
from typing import Union

EXCEPTION_CN = {
    "SyntaxError": "语法错误",
    "TypeError": "类型错误",
    "LookupError": "查找错误",
    "ValueError": "值错误",
    "RuntimeError": "运行时错误",
    "FileNotFoundError": "文件未找到",
    "IndexError": "索引错误",
    "KeyError": "键错误",
    "JSONDecodeError": "JSON 解析错误",
    "TimeoutError": "超时",
    "OSError": "系统错误",
    "PermissionError": "权限错误",
    "Exception": "异常",
    "ZeroDivisionError": "除零错误",
    "AttributeError": "属性错误",
    "ImportError": "导入错误",
    "ModuleNotFoundError": "模块未找到",
    "NotImplementedError": "未实现",
    "RecursionError": "递归过深",
    "StopIteration": "迭代结束",
}

_MESSAGE_RULES = [
    (r"\[Errno 2\] No such file or directory(?:: '([^']*)')?", lambda m: f"文件或目录不存在{m.group(1) and '：' + m.group(1) or ''}"),
    (r"No such file or directory: '([^']*)'", r"文件或目录不存在：\1"),
    (r"\[Errno 13\] Permission denied", "权限被拒绝"),
    (r"Permission denied: '([^']*)'", r"没有权限访问：\1"),
    (r"list index out of range", "列表索引超出范围"),
    (r"division by zero", "除零错误"),
    (r"Expecting value: line (\d+) column (\d+)", r"JSON 格式无效（第 \1 行第 \2 列）"),
    (r"Invalid control character at", "JSON 包含无效控制字符"),
    (r"Unterminated string starting at", "JSON 字符串未闭合"),
    (r"Extra data: line (\d+) column (\d+)", r"JSON 后有多余内容（第 \1 行第 \2 列）"),
    (r"the JSON object must be str, bytes or bytearray, not ", "JSON 输入类型无效"),
    (r"not enough values to unpack", "解包值数量不足"),
    (r"too many values to unpack", "解包值数量过多"),
    (r"'NoneType' object is not subscriptable", "空值无法取下标"),
    (r"'NoneType' object is not iterable", "空值无法迭代"),
    (r"object of type 'int' has no len\(\)", "整数没有长度"),
    (r"object of type '([^']+)' has no len\(\)", r"\1 类型没有长度"),
]


def exception_name_cn(exc: BaseException) -> str:
    return EXCEPTION_CN.get(type(exc).__name__, type(exc).__name__)


def translate_message(msg: str) -> str:
    if not msg:
        return msg
    out = str(msg)
    for pattern, repl in _MESSAGE_RULES:
        if callable(repl):
            out = re.sub(pattern, repl, out)
        else:
            out = re.sub(pattern, repl, out)
    return out


def format_user_error(exc: Union[BaseException, str]) -> str:
    if isinstance(exc, BaseException):
        name = exception_name_cn(exc)
        body = translate_message(str(exc))
        return f"{name}：{body}"
    text = str(exc)
    if "：" in text and not text.startswith("Error"):
        return translate_message(text)
    return translate_message(text)
