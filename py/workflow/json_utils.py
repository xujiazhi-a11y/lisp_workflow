"""
JSON 处理工具
"""

import json
import re
from typing import Any


def parse_json(text: str) -> Any:
    """
    解析 JSON 字符串为 Python 数据结构
    
    参数:
        text: JSON 字符串
    
    返回:
        Python 数据结构（dict/list/等）
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"JSON 解析失败：{e.msg}（第 {e.lineno} 行第 {e.colno} 列）"
        ) from e


def to_json(data: Any, indent: int = 2) -> str:
    """
    将 Python 数据结构转换为 JSON 字符串
    
    参数:
        data: Python 数据结构
        indent: 缩进空格数
    
    返回:
        JSON 字符串
    """
    return json.dumps(data, ensure_ascii=False, indent=indent)


def extract_json(text: str, default=None) -> Any:
    """
    从文本中提取 JSON 数组或对象

    参数:
        text: 可能包含 JSON 的文本
        default: 提取失败时的默认返回值

    返回:
        解析后的 Python 数据结构，失败时返回 default
    """
    text = text.strip()

    # 先去除 think 标签
    text = re.sub(r'<think\b[^>]*>.*?</think\s*>', '', text, flags=re.DOTALL).strip()

    # 尝试匹配最外层的 [] 或 {} 包裹的内容（贪婪匹配确保完整性）
    match = re.search(r'(\[[\s\S]*\]|\{[\s\S]*\})', text)

    if match:
        json_str = match.group(1)
    else:
        json_str = text

    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, ValueError):
        # 尝试将单引号转为双引号（用于处理 Lisp 字符串中的单引号 JSON）
        try:
            # 简单转换：' -> "
            converted = json_str.replace("'", '"')
            return json.loads(converted)
        except (json.JSONDecodeError, ValueError):
            return default


def safe_parse_json(text: str, default=None) -> Any:
    """
    安全解析 JSON，失败时返回默认值
    
    参数:
        text: JSON 字符串
        default: 解析失败时的默认返回值
    
    返回:
        解析结果或默认值
    """
    try:
        return parse_json(text)
    except (json.JSONDecodeError, ValueError):
        return default
