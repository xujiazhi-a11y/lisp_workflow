#!/usr/bin/env python3
"""
观察模式：自动点击单位登录，然后暂停等待用户操作
使用原生 Playwright API，参考原脚本
"""
import time
from playwright.sync_api import sync_playwright

ACCOUNT = "[请填写账号]"
PASSWORD = "[请填写密码]"

print("=" * 50)
print("启动浏览器...")
print("=" * 50)

p = sync_playwright().start()
browser = p.chromium.launch(headless=False)
context = browser.new_context()
page = context.new_page()
page.goto("[请填写首页地址]", wait_until="domcontentloaded", timeout=15000)
time.sleep(3)

# 步骤1: 点击"单位登录"（使用原脚本的方式）
print("\n【步骤1】点击'单位登录'...")
try:
    page.locator(".unit-btn").click()
    print("✓ 已点击 .unit-btn")
except Exception as e:
    print(f"✗ 点击 .unit-btn 失败: {e}")
    # 尝试备用选择器
    try:
        page.locator("li:has-text('单位登录')").click()
        print("✓ 已点击 li:has-text('单位登录')")
    except Exception as e2:
        print(f"✗ 备用选择器也失败: {e2}")

time.sleep(3)

# 步骤2: 填写账号密码（使用原脚本的方式）
print("\n【步骤2】填写账号密码...")
try:
    inputs = page.locator("input:visible").all()
    print(f"  找到 {len(inputs)} 个可见input元素")
    if len(inputs) >= 2:
        inputs[0].fill(ACCOUNT)
        inputs[1].fill(PASSWORD)
        print("✓ 已填写账号密码")
    else:
        print("✗ 可见input元素不足2个")
except Exception as e:
    print(f"✗ 填写失败: {e}")

print("\n" + "=" * 50)
print("请在浏览器中：")
print("  1. 输入验证码")
print("  2. 点击登录按钮")
print("  3. 选择单位并确认")
print("  4. 点击招采系统")
print("  5. 点击'骨科脊柱人工关节'")
print("  6. 点击'采购计划'")
print("  7. 点击'采购计划管理'")
print("=" * 50)

input("\n完成所有操作后，在此按回车继续...")

# 扫描最终页面
print("\n扫描最终页面...")
try:
    result = page.evaluate("""
    () => {
        const interactiveTags = ['A', 'BUTTON', 'INPUT', 'SELECT', 'TEXTAREA', 'LI', 'DIV'];
        const results = [];
        const seen = new Set();
        
        interactiveTags.forEach(tag => {
            document.querySelectorAll(tag).forEach(el => {
                const text = (el.innerText || el.textContent || '').trim().substring(0, 100);
                const rect = el.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0) {
                    const key = el.tagName + '|' + text;
                    if (!seen.has(key)) {
                        seen.add(key);
                        results.push({
                            tag: el.tagName,
                            text: text,
                            class: el.className || '',
                            id: el.id || '',
                            placeholder: el.getAttribute('placeholder') || ''
                        });
                    }
                }
            });
        });
        
        return {
            url: window.location.href,
            title: document.title,
            elementCount: results.length,
            elements: results
        };
    }
    """)
    
    import json
    with open("output/obs_final.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"发现 {result.get('elementCount', 0)} 个元素")
    print(f"页面URL: {result.get('url', '')}")
    print(f"页面标题: {result.get('title', '')}")
    
    # 显示菜单相关元素
    print("\n菜单相关元素:")
    for el in result['elements']:
        text = el.get('text', '')
        if any(kw in text for kw in ['骨科', '采购计划', '采购管理', '备案']):
            print(f"  [{el['tag']}] {text[:40]}")
    
except Exception as e:
    print(f"扫描失败: {e}")

print("\n观察完成！")
browser.close()
p.stop()
