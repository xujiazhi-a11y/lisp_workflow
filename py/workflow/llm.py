"""
大模型调用模块
支持 DeepSeek / OpenAI 兼容 API
"""

import os
import json
from functools import lru_cache

# 默认配置
DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"

# API Key 可以通过环境变量设置，或直接传入
def get_api_key():
    """获取 API Key，优先从环境变量"""
    return os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY", "")


def call_llm(prompt: str, config: dict = None) -> str:
    """
    调用大模型 API
    
    参数:
        prompt: 提示词字符串
        config: 可选配置字典，包含:
            - api_key: API密钥
            - base_url: API基础URL
            - model: 模型名称
            - temperature: 温度参数
            - max_tokens: 最大token数
    
    返回:
        大模型返回的文本内容
    """
    config = config or {}
    
    # 合并配置
    api_key = config.get("api_key") or get_api_key()
    base_url = config.get("base_url", DEFAULT_BASE_URL)
    model = config.get("model", DEFAULT_MODEL)
    temperature = config.get("temperature", 0.7)
    max_tokens = config.get("max_tokens", 4096)
    
    if not api_key:
        # Mock 模式：返回模拟响应
        return f"[MOCK LLM] 收到提示词: {prompt[:100]}{'...' if len(prompt) > 100 else ''}"
    
    try:
        # 使用 OpenAI 兼容的 SDK
        import openai
        
        client = openai.OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=60
        )
        
        return response.choices[0].message.content
        
    except ImportError:
        # 如果没有 openai 库，使用 requests 直接调用
        import requests
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        resp = requests.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=(10, 60)
        )
        
        if resp.status_code != 200:
            raise Exception(f"API 调用失败: {resp.status_code} - {resp.text}")
        
        return resp.json()["choices"][0]["message"]["content"]


def call_llm_with_system(prompt: str, system_prompt: str, config: dict = None) -> str:
    """
    带系统提示词的大模型调用
    
    参数:
        prompt: 用户提示词
        system_prompt: 系统提示词
        config: 配置字典
    
    返回:
        大模型返回的文本内容
    """
    config = config or {}
    
    api_key = config.get("api_key") or get_api_key()
    base_url = config.get("base_url", DEFAULT_BASE_URL)
    model = config.get("model", DEFAULT_MODEL)
    temperature = config.get("temperature", 0.7)
    max_tokens = config.get("max_tokens", 4096)
    
    if not api_key:
        raise ValueError("未设置 API Key")
    
    import openai
    
    client = openai.OpenAI(
        api_key=api_key,
        base_url=base_url
    )
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        temperature=temperature,
        max_tokens=max_tokens
    )
    
    return response.choices[0].message.content
