#!/usr/bin/env python3
"""
医疗备案填表 - 自动化脚本
基于已录制的元素信息生成
"""
import time
import json
from playwright.sync_api import sync_playwright

# ============================================================
# 配置
# ============================================================
ACCOUNT = "[请填写账号]"
PASSWORD = "[请填写密码]"

# 登录页面元素选择器
LOGIN_SELECTORS = {
    "单位登录按钮": ".unit-btn",
    "账号输入框": "input[placeholder='单位账号/经办人账号']",
    "密码输入框": "input[placeholder='请输入密码']",
    "验证码输入框": "input[placeholder='请输入验证码']",
    "登录按钮": "button.login-btn, .el-button.login-btn"
}

# ============================================================
# 工具函数
# ============================================================
def scan_page_elements(page):
    """扫描当前页面的所有可交互元素"""
    result = page.evaluate("""
    () => {
        const interactiveTags = ['A', 'BUTTON', 'INPUT', 'SELECT', 'TEXTAREA', 'LI', 'DIV', 'SPAN'];
        const results = [];
        const seen = new Set();

        interactiveTags.forEach(tag => {
            document.querySelectorAll(tag).forEach(el => {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                const isVisible = rect.width > 0 && rect.height > 0 &&
                                  style.display !== 'none' &&
                                  style.visibility !== 'hidden';

                if (isVisible) {
                    const text = (el.innerText || el.textContent || '').trim().substring(0, 100);
                    const placeholder = el.getAttribute('placeholder') || '';
                    const role = el.getAttribute('role') || '';
                    const name = el.getAttribute('name') || '';
                    const href = el.getAttribute('href') || '';
                    const type = el.type || el.getAttribute('type') || '';

                    // 生成选择器
                    let selector = '';
                    if (el.id) {
                        selector = `#${el.id}`;
                    } else if (placeholder) {
                        selector = `${el.tagName.toLowerCase()}[placeholder='${placeholder}']`;
                    } else if (name) {
                        selector = `${el.tagName.toLowerCase()}[name='${name}']`;
                    } else if (el.className && typeof el.className === 'string') {
                        const classes = el.className.split(' ').filter(c => c && !c.includes(':'));
                        if (classes.length > 0) {
                            selector = `${el.tagName.toLowerCase()}.${classes.slice(0, 3).join('.')}`;
                        }
                    }
                    if (!selector) {
                        selector = el.tagName.toLowerCase();
                    }

                    const key = el.tagName + '|' + text + '|' + selector;
                    if (!seen.has(key)) {
                        seen.add(key);
                        results.push({
                            tag: el.tagName,
                            text: text,
                            placeholder: placeholder,
                            class: el.className || '',
                            id: el.id || '',
                            name: name,
                            type: type,
                            role: role,
                            href: href,
                            selector: selector,
                            isVisible: true,
                            x: Math.round(rect.x),
                            y: Math.round(rect.y),
                            width: Math.round(rect.width),
                            height: Math.round(rect.height)
                        });
                    }
                }
            });
        });

        return results;
    }
    """)

    return result

def print_elements(elements, filter_text=None):
    """打印元素信息"""
    if filter_text:
        elements = [e for e in elements if filter_text.lower() in e['text'].lower() or filter_text.lower() in e.get('placeholder', '').lower()]

    for el in elements[:20]:
        text = el.get('text', '')[:40] or el.get('placeholder', '')[:40] or '(无文本)'
        print(f"  [{el['tag']:6}] {text:40} | {el['selector'][:50]}")

def save_scan(page, filename):
    """保存扫描结果"""
    elements = scan_page_elements(page)
    result = {
        "url": page.url,
        "title": page.title(),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elementCount": len(elements),
        "elements": elements
    }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✅ 已保存到: {filename}")
    return result

# ============================================================
# 主流程
# ============================================================
print("=" * 70)
print("医疗备案填表 - 自动化脚本")
print("=" * 70)

p = sync_playwright().start()
browser = p.chromium.launch(headless=False)
context = browser.new_context()
page = context.new_page()

# ------------------------------------------------------------
# 步骤1: 打开首页
# ------------------------------------------------------------
print("\n【步骤1】打开医保平台首页...")
page.goto("[请填写首页地址]", wait_until="domcontentloaded", timeout=15000)
time.sleep(3)

# ------------------------------------------------------------
# 步骤2: 点击单位登录
# ------------------------------------------------------------
print("【步骤2】点击'单位登录'...")
try:
    page.locator(LOGIN_SELECTORS["单位登录按钮"]).click()
    print("  ✓ 已点击单位登录")
    time.sleep(2)
except Exception as e:
    print(f"  ✗ 失败: {e}")

# ------------------------------------------------------------
# 步骤3: 填写账号密码
# ------------------------------------------------------------
print("【步骤3】填写账号密码...")
try:
    page.locator(LOGIN_SELECTORS["账号输入框"]).fill(ACCOUNT)
    page.locator(LOGIN_SELECTORS["密码输入框"]).fill(PASSWORD)
    print("  ✓ 已填写账号密码")
    time.sleep(1)
except Exception as e:
    print(f"  ✗ 失败: {e}")

# ------------------------------------------------------------
# 步骤4: 等待用户输入验证码并登录
# ------------------------------------------------------------
print("\n" + "=" * 70)
print("【需要手动操作】")
print("  1. 在浏览器中输入验证码")
print("  2. 点击登录按钮")
print("  3. 选择单位并确认")
print("  4. 导航到目标页面")
print("=" * 70)

input("\n完成所有操作后，按回车继续...")

# ------------------------------------------------------------
# 扫描当前页面
# ------------------------------------------------------------
print("\n【扫描当前页面】")
result = save_scan(page, "output/current_page.json")

print(f"\n  URL: {result['url']}")
print(f"  标题: {result['title']}")
print(f"  元素数: {result['elementCount']}")

print("\n【可点击元素】")
clickable = [e for e in result['elements'] if e['tag'] in ['A', 'BUTTON'] or e.get('role') == 'button']
print_elements(clickable)

print("\n【输入框】")
inputs = [e for e in result['elements'] if e['tag'] == 'INPUT']
print_elements(inputs)

print("\n【下拉框】")
selects = [e for e in result['elements'] if e['tag'] == 'SELECT']
print_elements(selects)

print("\n【菜单/列表项】")
lis = [e for e in result['elements'] if e['tag'] == 'LI']
print_elements(lis)

# ------------------------------------------------------------
# 交互模式
# ------------------------------------------------------------
print("\n" + "=" * 70)
print("【交互模式】")
print("  - 输入关键词搜索元素")
print("  - 输入 'scan' 重新扫描")
print("  - 输入 'highlight <选择器>' 高亮元素")
print("  - 输入 'q' 退出")
print("=" * 70)

while True:
    try:
        user_input = input("\n> ").strip()

        if user_input.lower() == 'q':
            break
        elif user_input.lower() == 'scan':
            result = save_scan(page, "output/current_page.json")
            print(f"  元素数: {result['elementCount']}")
        elif user_input.lower().startswith('highlight '):
            selector = user_input[10:]
            try:
                page.locator(selector).highlight()
                print(f"  ✓ 已高亮: {selector}")
            except Exception as e:
                print(f"  ✗ 失败: {e}")
        elif user_input:
            print(f"\n搜索结果: '{user_input}'")
            print_elements(result['elements'], user_input)
    except EOFError:
        time.sleep(1)
        continue
    except KeyboardInterrupt:
        break

browser.close()
p.stop()
print("\n完成！")
