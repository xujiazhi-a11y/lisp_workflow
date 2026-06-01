"""
文本处理工具
"""

import re
from typing import Optional


def remove_think_tags(text: str) -> str:
    """
    去除思考标签及其内容（支持多种格式）
    
    参数:
        text: 包含 think 标签的文本
    
    返回:
        清理后的纯文本
    """
    # 匹配各种思考标签格式：<think>...</think>、<thinking>...</thinking>、<thought>...</thought>
    # 使用非贪婪匹配 .*? 更准确
    patterns = [
        r'<think>.*?</think>',           # DeepSeek 格式
        r'<thinking.*?>.*?</thinking>', # 通用格式
        r'<thought.*?>.*?</thought>', # 另一种格式
    ]
    for pattern in patterns:
        text = re.sub(pattern, '', text, flags=re.DOTALL)
    return text.strip()


def format_string(template: str, *args) -> str:
    """
    格式化字符串
    
    参数:
        template: 模板字符串（使用 %s 占位符）
        *args: 替换值
    
    返回:
        格式化后的字符串
    """
    return template % args


def regex_match(pattern: str, text: str) -> Optional[str]:
    """
    正则匹配
    
    参数:
        pattern: 正则表达式
        text: 待匹配文本
    
    返回:
        匹配结果（第一个匹配组或整个匹配）
    """
    match = re.search(pattern, text)
    if match:
        # 如果有分组，返回第一个分组
        groups = match.groups()
        return groups[0] if groups else match.group(0)
    return None


def regex_replace(pattern: str, replacement: str, text: str) -> str:
    """
    正则替换
    
    参数:
        pattern: 正则表达式
        replacement: 替换内容
        text: 待处理文本
    
    返回:
        替换后的文本
    """
    return re.sub(pattern, replacement, text)


def split_text(text: str, separator: str = "\n") -> list:
    """
    分割文本
    
    参数:
        text: 待分割文本
        separator: 分隔符
    
    返回:
        分割后的字符串列表
    """
    return text.split(separator)


def join_text(parts: list, separator: str = "\n") -> str:
    """
    连接文本
    
    参数:
        parts: 字符串列表
        separator: 连接符
    
    返回:
        连接后的字符串
    """
    return separator.join(str(p) for p in parts)


def strip_text(text: str) -> str:
    """
    去除首尾空白
    
    参数:
        text: 待处理文本
    
    返回:
        处理后的文本
    """
    return text.strip()
