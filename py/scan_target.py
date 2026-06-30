#!/usr/bin/env python3
"""
扫描目标页面：先登录，再访问招采系统页面
"""
import time
import json
from playwright.sync_api import sync_playwright

ACCOUNT = "[请填写账号]"
PASSWORD = "[请填写密码]"
TARGET_URL = "[请填写目标页面地址]"

print("=" * 60)
print("启动浏览器并登录...")
print("=" * 60)

p = sync_playwright().start()
browser = p.chromium.launch(headless=False)
context = browser.new_context()
page = context.new_page()

# 1. 打开首页
page.goto("[请填写首页地址]", wait_until="domcontentloaded", timeout=15000)
time.sleep(3)

# 2. 点击单位登录
print("\n点击单位登录...")
page.locator(".unit-btn").click()
time.sleep(3)

# 3. 填写账号密码
print("填写账号密码...")
inputs = page.locator("input:visible").all()
if len(inputs) >= 2:
    inputs[0].fill(ACCOUNT)
    inputs[1].fill(PASSWORD)
    print("✓ 已填写")

print("\n" + "=" * 60)
print("请在浏览器中：")
print("  1. 输入验证码并点击登录")
print("  2. 选择单位并确认")
print("  3. 点击招采系统")
print("  4. 导航到采购计划管理页面")
print("")
print("  完成后在此按回车...")
print("=" * 60)

input()

# 4. 访问目标URL
print(f"\n访问目标页面: {TARGET_URL}")
page.goto(TARGET_URL, timeout=30000)
time.sleep(5)

# 5. 滚动加载
page.evaluate("""
() => {
    return new Promise((resolve) => {
        let totalHeight = 0;
        const distance = 300;
        const timer = setInterval(() => {
            const scrollHeight = document.body.scrollHeight;
            window.scrollBy(0, distance);
            totalHeight += distance;
            if (totalHeight >= scrollHeight) {
                clearInterval(timer);
                window.scrollTo(0, 0);
                resolve('done');
            }
        }, 100);
        setTimeout(() => {
            clearInterval(timer);
            window.scrollTo(0, 0);
            resolve('timeout');
        }, 5000);
    });
}
""")
time.sleep(2)

# 6. 扫描元素
print("\n扫描页面元素...")
result = page.evaluate("""
() => {
    const interactiveTags = ['A', 'BUTTON', 'INPUT', 'SELECT', 'TEXTAREA', 'LI', 'DIV', 'SPAN'];
    const results = [];
    const seen = new Set();
    
    interactiveTags.forEach(tag => {
        document.querySelectorAll(tag).forEach(el => {
            const text = (el.innerText || el.textContent || '').trim().substring(0, 100);
            const rect = el.getBoundingClientRect();
            const style = window.getComputedStyle(el);
            const isVisible = rect.width > 0 && rect.height > 0 && 
                              style.display !== 'none' && 
                              style.visibility !== 'hidden';
            
            if (isVisible) {
                const key = el.tagName + '|' + text + '|' + (el.className || '');
                if (!seen.has(key)) {
                    seen.add(key);
                    results.push({
                        tag: el.tagName,
                        text: text,
                        class: el.className || '',
                        id: el.id || '',
                        placeholder: el.getAttribute('placeholder') || '',
                        role: el.getAttribute('role') || '',
                        x: Math.round(rect.x),
                        y: Math.round(rect.y),
                        width: Math.round(rect.width),
                        height: Math.round(rect.height)
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

with open("output/scan_target_page.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f"\n✓ 扫描完成！")
print(f"  URL: {result['url']}")
print(f"  标题: {result['title']}")
print(f"  元素数: {result['elementCount']}")

# 显示菜单项
print("\n【菜单相关元素】")
for el in result['elements']:
    text = el.get('text', '')
    if any(kw in text for kw in ['骨科', '采购计划', '采购管理', '备案', '挂网', '目录', '人工关节', '采购']):
        print(f"  [{el['tag']:8}] {text[:50]:50} | class: {el['class'][:40]}")

print("\n【所有LI元素】")
for el in result['elements']:
    if el['tag'] == 'LI' and el.get('text', '').strip():
        print(f"  {el['text'][:50]:50} | class: {el['class'][:40]}")

print("\n【所有按钮】")
for el in result['elements']:
    if el['tag'] == 'BUTTON' and el.get('text', '').strip():
        print(f"  {el['text'][:40]:40} | class: {el['class'][:30]}")

print("\n【所有输入框】")
for el in result['elements']:
    if el['tag'] == 'INPUT':
        ph = el.get('placeholder', '')
        if ph:
            print(f"  placeholder: {ph[:40]:40}")

browser.close()
p.stop()
