#!/usr/bin/env python3
"""
专门扫描登录页面，找到验证码输入框和登录按钮
"""
import time
import json
from playwright.sync_api import sync_playwright

ACCOUNT = "[请填写账号]"
PASSWORD = "[请填写密码]"

print("=" * 60)
print("🔍 扫描登录页面元素")
print("=" * 60)

p = sync_playwright().start()
browser = p.chromium.launch(headless=False)
context = browser.new_context()
page = context.new_page()
page.goto("[请填写首页地址]", wait_until="domcontentloaded", timeout=15000)
time.sleep(3)

# 点击单位登录
print("\n点击'单位登录'...")
page.locator(".unit-btn").click()
time.sleep(2)

# 填写账号密码
print("填写账号密码...")
inputs = page.locator("input:visible").all()
if len(inputs) >= 2:
    inputs[0].fill(ACCOUNT)
    inputs[1].fill(PASSWORD)

# 等待页面稳定
print("等待页面加载...")
time.sleep(2)

print("\n" + "=" * 60)
print("【扫描结果】")
print("=" * 60)

# 扫描所有输入框
result = page.evaluate("""
() => {
    const results = [];
    document.querySelectorAll('input').forEach(el => {
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);
        const isVisible = rect.width > 0 && rect.height > 0 &&
                          style.display !== 'none' &&
                          style.visibility !== 'hidden';

        if (isVisible) {
            results.push({
                tag: el.tagName,
                type: el.type,
                placeholder: el.placeholder || '',
                name: el.name || '',
                id: el.id || '',
                className: el.className || '',
                value: el.value || '',
                position: {
                    x: Math.round(rect.x),
                    y: Math.round(rect.y),
                    width: Math.round(rect.width),
                    height: Math.round(rect.height)
                }
            });
        }
    });
    return results;
}
""")

print(f"\n找到 {len(result)} 个输入框:\n")
for i, el in enumerate(result, 1):
    print(f"{i}. 类型: {el['type']}")
    print(f"   placeholder: '{el.get('placeholder', '')}'")
    print(f"   name: '{el.get('name', '')}'")
    print(f"   id: '{el.get('id', '')}'")
    print(f"   class: '{el.get('className', '')}'")
    print(f"   value: '{el.get('value', '')}'")

    # 生成选择器
    selectors = []
    if el.get('placeholder'):
        selectors.append(f"input[placeholder='{el.get('placeholder')}']")
    if el.get('name'):
        selectors.append(f"input[name='{el.get('name')}']")
    if el.get('id'):
        selectors.append(f"#{el.get('id')}")
    if el.get('className'):
        classes = el.get('className', '').split()
        if classes:
            selectors.append(f"input.{classes[0]}")

    print(f"   推荐选择器: {selectors[0] if selectors else '无'}")
    print()

# 扫描按钮
buttons = page.evaluate("""
() => {
    const results = [];
    document.querySelectorAll('button, [role="button"], div[class*="btn"]').forEach(el => {
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);
        const isVisible = rect.width > 0 && rect.height > 0 &&
                          style.display !== 'none' &&
                          style.visibility !== 'hidden';

        if (isVisible) {
            const text = (el.innerText || el.textContent || '').trim();
            results.push({
                tag: el.tagName,
                text: text,
                className: el.className || '',
                id: el.id || '',
                role: el.getAttribute('role') || ''
            });
        }
    });
    return results.filter(b => b.text.length < 50);
}
""")

print(f"找到 {len(buttons)} 个按钮:\n")
for i, btn in enumerate(buttons, 1):
    print(f"{i}. {btn['text']}")
    print(f"   class: {btn.get('className', '')[:50]}")
    print(f"   id: {btn.get('id', '')}")
    print()

# 保存结果
output = {
    "inputs": result,
    "buttons": buttons
}

with open("output/login_elements.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print("✅ 已保存到: output/login_elements.json")

print("\n" + "=" * 60)
print("请确认:")
print("1. 验证码输入框是第几个输入框？")
print("2. 登录按钮是哪个？")
print("=" * 60)

browser.close()
p.stop()