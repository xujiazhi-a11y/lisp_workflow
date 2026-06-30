#!/usr/bin/env python3
"""交互式视频工作流测试 - 前台运行，支持用户输入"""
import sys
sys.path.insert(0, '.')

from workflow_lisp import run, GLOBAL_ENV, to_symbol
from workflow.ai_services import set_api_keys_provider
import json

# 加载 API keys
with open('.user_config.json', 'r') as f:
    api_keys = json.load(f).get('api_keys', {})
set_api_keys_provider(lambda: api_keys)

# 设置输入 - 使用你的暹罗猫图片
GLOBAL_ENV[to_symbol('client-input')] = {
    'ref-image': '.ark/uploads/siamese_cat.jpg',
    'story': '小猫做饭',
    'segment-count': 2,
    'character': '一只可爱的暹罗猫，蓝眼睛，浅色身体，深色耳朵和面部'
}

# 读取交互式工作流代码
with open('examples/AI视频创作_交互式.lisp', 'r', encoding='utf-8') as f:
    code = f.read()

print("=" * 60)
print("🎬 AI 视频创作工作流（交互式测试）")
print("=" * 60)
print("角色图: .ark/uploads/siamese_cat.jpg")
print("故事: 小猫做饭")
print("片段数: 2")
print("=" * 60)
print()
print("请根据提示输入您的选择...")
print()

# 执行 - 前台运行，支持交互输入
result = run(code)
print(f"\n{'=' * 60}")
print(f"🎉 最终结果: {result}")
print(f"{'=' * 60}")
