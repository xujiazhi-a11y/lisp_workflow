#!/usr/bin/env python3
"""
医疗备案填表 - 完整自动化录制
目标路径：骨科脊柱人工关节 -> 采购计划 -> 采购计划管理
"""
import time
import json
from playwright.sync_api import sync_playwright

ACCOUNT = "[请填写账号]"
PASSWORD = "[请填写密码]"

# 存储所有扫描结果
all_scans = {}

def scan_and_save(page, name):
    """扫描页面并保存"""
    print(f"\n{'='*60}")
    print(f"【扫描】{name}")
    print(f"{'='*60}")

    # 滚动加载
    for _ in range(3):
        page.evaluate("window.scrollBy(0, 300)")
        time.sleep(0.3)
    page.evaluate("window.scrollTo(0, 0)")
    time.sleep(0.5)

    elements = page.evaluate("""
    () => {
        const interactiveTags = ['A', 'BUTTON', 'INPUT', 'SELECT', 'TEXTAREA', 'LI', 'DIV', 'SPAN'];
        const results = [];
        const seen = new Set();

        interactiveTags.forEach(tag => {
            document.querySelectorAll(tag).forEach(el => {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                const isVisible = rect.width > 0 && rect.height > 0;

                if (isVisible) {
                    const text = (el.innerText || el.textContent || '').trim().substring(0, 100);
                    const placeholder = el.getAttribute('placeholder') || '';
                    const name = el.getAttribute('name') || '';
                    const id = el.id || '';
                    const type = el.type || '';
                    const role = el.getAttribute('role') || '';

                    let selectors = [];
                    if (id) selectors.push(`#${id}`);
                    if (placeholder) selectors.push(`${el.tagName.toLowerCase()}[placeholder='${placeholder}']`);
                    if (name) selectors.push(`${el.tagName.toLowerCase()}[name='${name}']`);
                    if (text && text.length < 30 && !text.includes('\\n')) {
                        selectors.push(`text='${text}'`);
                    }
                    if (el.className && typeof el.className === 'string') {
                        const classes = el.className.split(' ').filter(c => c && !c.includes(':'));
                        if (classes.length > 0) selectors.push(`${el.tagName.toLowerCase()}.${classes[0]}`);
                    }

                    const key = el.tagName + '|' + text + '|' + id;
                    if (!seen.has(key)) {
                        seen.add(key);
                        results.push({
                            tag: el.tagName,
                            text: text,
                            placeholder: placeholder,
                            class: el.className || '',
                            id: id,
                            name: name,
                            type: type,
                            role: role,
                            selectors: selectors,
                            x: Math.round(rect.x),
                            y: Math.round(rect.y)
                        });
                    }
                }
            });
        });
        return results;
    }
    """)

    result = {
        "step": name,
        "url": page.url,
        "title": page.title(),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elementCount": len(elements),
        "elements": elements
    }

    filename = f"output/{name.replace(' ', '_')}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    all_scans[name] = result

    print(f"URL: {page.url}")
    print(f"标题: {page.title()}")
    print(f"元素数: {len(elements)}")
    print(f"保存: {filename}")

    # 显示关键元素
    print("\n【输入框】")
    for el in [e for e in elements if e['tag'] == 'INPUT'][:10]:
        sel = el['selectors'][0] if el['selectors'] else '无'
        print(f"  '{el.get('placeholder', '')[:30]}' | {sel}")

    print("\n【按钮/链接】")
    for el in [e for e in elements if e['tag'] in ['A', 'BUTTON']][:15]:
        sel = el['selectors'][0] if el['selectors'] else '无'
        print(f"  '{el['text'][:30]}' | {sel}")

    print("\n【菜单项 (LI)】")
    for el in [e for e in elements if e['tag'] == 'LI'][:15]:
        sel = el['selectors'][0] if el['selectors'] else '无'
        print(f"  '{el['text'][:30]}' | {sel}")

    return elements

# ============================================================
# 主流程
# ============================================================
print("=" * 60)
print("🏥 医疗备案填表 - 自动化录制")
print("=" * 60)

p = sync_playwright().start()
browser = p.chromium.launch(headless=False)
context = browser.new_context()
page = context.new_page()

# ------------------------------------------------------------
# 阶段1: 打开首页
# ------------------------------------------------------------
print("\n【阶段1】打开首页...")
page.goto("[请填写首页地址]", wait_until="domcontentloaded", timeout=20000)
time.sleep(3)

# ------------------------------------------------------------
# 阶段2: 点击单位登录
# ------------------------------------------------------------
print("\n【阶段2】点击单位登录...")
try:
    page.locator(".unit-btn").click()
    time.sleep(2)
    print("  ✓ 已点击单位登录")
except Exception as e:
    print(f"  ✗ 失败: {e}")

# ------------------------------------------------------------
# 阶段3: 填写账号密码
# ------------------------------------------------------------
print("\n【阶段3】填写账号密码...")
try:
    page.locator("input[placeholder='单位账号/经办人账号']").fill(ACCOUNT)
    page.locator("input[placeholder='请输入密码']").fill(PASSWORD)
    print("  ✓ 已填写账号密码")
except Exception as e:
    print(f"  ✗ 失败: {e}")

# ------------------------------------------------------------
# 阶段4: 等待用户输入验证码并登录
# ------------------------------------------------------------
print("\n" + "=" * 60)
print("⏳ 请手动完成以下操作：")
print("   1. 输入验证码")
print("   2. 点击登录按钮")
print("   3. 如果有单位选择，选择并确认")
print("=" * 60)
print("\n等待60秒...")
for i in range(60, 0, -1):
    time.sleep(1)
    if i % 10 == 0:
        print(f"  还剩 {i} 秒...")

# ------------------------------------------------------------
# 阶段5: 扫描登录后的页面
# ------------------------------------------------------------
print("\n【阶段5】扫描登录后页面...")
scan_and_save(page, "登录后首页")

# ------------------------------------------------------------
# 阶段6: 查找并点击"骨科脊柱人工关节"
# ------------------------------------------------------------
print("\n【阶段6】查找'骨科脊柱人工关节'...")
time.sleep(2)

# 尝试多种选择器
selectors_to_try = [
    "text='骨科脊柱人工关节'",
    "text='骨科'",
    "li:has-text('骨科')",
    "div:has-text('骨科脊柱')",
    "[class*='骨科']"
]

found = False
for sel in selectors_to_try:
    try:
        if page.locator(sel).count() > 0:
            print(f"  找到: {sel}")
            page.locator(sel).first.click()
            print(f"  ✓ 已点击: {sel}")
            found = True
            time.sleep(2)
            break
    except:
        continue

if not found:
    print("  未自动找到，请手动点击...")
    time.sleep(5)

scan_and_save(page, "骨科脊柱人工关节页")

# ------------------------------------------------------------
# 阶段7: 查找并点击"采购计划"
# ------------------------------------------------------------
print("\n【阶段7】查找'采购计划'...")
time.sleep(2)

selectors_to_try = [
    "text='采购计划'",
    "li:has-text('采购计划')",
    "div:has-text('采购计划')",
    "a:has-text('采购计划')"
]

found = False
for sel in selectors_to_try:
    try:
        if page.locator(sel).count() > 0:
            print(f"  找到: {sel}")
            page.locator(sel).first.click()
            print(f"  ✓ 已点击: {sel}")
            found = True
            time.sleep(2)
            break
    except:
        continue

if not found:
    print("  未自动找到，请手动点击...")
    time.sleep(5)

scan_and_save(page, "采购计划页")

# ------------------------------------------------------------
# 阶段8: 查找并点击"采购计划管理"
# ------------------------------------------------------------
print("\n【阶段8】查找'采购计划管理'...")
time.sleep(2)

selectors_to_try = [
    "text='采购计划管理'",
    "li:has-text('采购计划管理')",
    "div:has-text('采购计划管理')",
    "a:has-text('采购计划管理')"
]

found = False
for sel in selectors_to_try:
    try:
        if page.locator(sel).count() > 0:
            print(f"  找到: {sel}")
            page.locator(sel).first.click()
            print(f"  ✓ 已点击: {sel}")
            found = True
            time.sleep(2)
            break
    except:
        continue

if not found:
    print("  未自动找到，请手动点击...")
    time.sleep(5)

# ------------------------------------------------------------
# 阶段9: 扫描最终目标页面
# ------------------------------------------------------------
print("\n【阶段9】扫描目标页面...")
time.sleep(3)
elements = scan_and_save(page, "采购计划管理页_目标")

# 特别关注左侧列表
print("\n" + "=" * 60)
print("【左侧菜单/列表】")
print("=" * 60)

# 过滤出可能是左侧菜单的元素（x坐标较小）
left_elements = [e for e in elements if e['x'] < 300 and e['tag'] in ['LI', 'DIV', 'A', 'SPAN']]
for el in left_elements[:20]:
    sel = el['selectors'][0] if el['selectors'] else '无'
    print(f"  [{el['tag']:5}] '{el['text'][:30]}' | x={el['x']} | {sel}")

# 保存完整录制结果
with open("output/完整录制结果.json", "w", encoding="utf-8") as f:
    json.dump(all_scans, f, ensure_ascii=False, indent=2)

print("\n" + "=" * 60)
print("✅ 录制完成！结果保存在 output/ 目录")
print("=" * 60)

# 保持浏览器打开
print("\n浏览器保持打开，按Ctrl+C退出...")
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass

browser.close()
p.stop()
