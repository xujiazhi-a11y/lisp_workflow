#!/usr/bin/env python3
"""
录制模式：捕获用户操作过程中的所有元素信息
使用 Playwright 的录制功能，在你操作时记录每一步的元素选择器
"""
import time
import json
from playwright.sync_api import sync_playwright
from datetime import datetime

ACCOUNT = "[请填写账号]"
PASSWORD = "[请填写密码]"

# 存储录制的操作
recorded_actions = []

def save_element_info(page, action_type, description=""):
    """保存当前焦点元素的详细信息"""
    element_info = page.evaluate("""
    () => {
        const el = document.activeElement;
        if (!el) return null;

        const rect = el.getBoundingClientRect();

        // 生成多种选择器策略
        const selectors = [];

        // 1. ID选择器（最优先）
        if (el.id) {
            selectors.push({
                type: 'id',
                value: `#${el.id}`,
                priority: 1
            });
        }

        // 2. data属性选择器
        for (const attr of el.attributes || []) {
            if (attr.name.startsWith('data-')) {
                selectors.push({
                    type: 'data-attr',
                    value: `[${attr.name}="${attr.value}"]`,
                    priority: 2
                });
            }
        }

        // 3. class组合选择器
        if (el.className && typeof el.className === 'string') {
            const classes = el.className.split(' ').filter(c => c && !c.includes(':'));
            if (classes.length > 0) {
                selectors.push({
                    type: 'class',
                    value: `${el.tagName.toLowerCase()}.${classes.join('.')}`,
                    priority: 3
                });
            }
        }

        // 4. 文本选择器
        const text = (el.innerText || el.textContent || el.value || el.placeholder || '').trim();
        if (text && text.length < 50) {
            selectors.push({
                type: 'text',
                value: `text="${text}"`,
                priority: 4
            });
        }

        // 5. role + name 选择器
        const role = el.getAttribute('role');
        const ariaLabel = el.getAttribute('aria-label');
        const name = el.getAttribute('name');
        if (role || ariaLabel || name) {
            let selector = el.tagName.toLowerCase();
            if (role) selector += `[role="${role}"]`;
            if (ariaLabel) selector += `[aria-label="${ariaLabel}"]`;
            if (name) selector += `[name="${name}"]`;
            selectors.push({
                type: 'aria',
                value: selector,
                priority: 2
            });
        }

        // 6. placeholder选择器
        const placeholder = el.getAttribute('placeholder');
        if (placeholder) {
            selectors.push({
                type: 'placeholder',
                value: `${el.tagName.toLowerCase()}[placeholder="${placeholder}"]`,
                priority: 2
            });
        }

        return {
            tag: el.tagName,
            type: el.type || '',
            text: text.substring(0, 100),
            placeholder: placeholder || '',
            value: el.value || '',
            name: name || '',
            id: el.id || '',
            className: el.className || '',
            role: role || '',
            href: el.href || '',
            selectors: selectors,
            position: {
                x: Math.round(rect.x),
                y: Math.round(rect.y),
                width: Math.round(rect.width),
                height: Math.round(rect.height)
            },
            isEditable: !el.disabled && !el.readOnly,
            isVisible: rect.width > 0 && rect.height > 0
        };
    }
    """)

    if element_info:
        action_record = {
            "timestamp": datetime.now().isoformat(),
            "action": action_type,
            "description": description,
            "url": page.url,
            "element": element_info
        }
        recorded_actions.append(action_record)
        print(f"\n✅ 已记录: {action_type}")
        print(f"   元素: {element_info['tag']} - {element_info['text'][:30] if element_info['text'] else '(无文本)'}")
        print(f"   推荐选择器: {element_info['selectors'][0] if element_info['selectors'] else '无'}")
        return action_record
    return None

def scan_current_page(page):
    """扫描当前页面的所有可交互元素"""
    result = page.evaluate("""
    () => {
        const interactiveTags = ['A', 'BUTTON', 'INPUT', 'SELECT', 'TEXTAREA', 'LI', 'DIV', 'SPAN'];
        const results = [];

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
                    } else if (el.className && typeof el.className === 'string') {
                        const classes = el.className.split(' ').filter(c => c && !c.includes(':'));
                        if (classes.length > 0) {
                            selector = `${el.tagName.toLowerCase()}.${classes.slice(0, 3).join('.')}`;
                        }
                    }
                    if (!selector) {
                        selector = el.tagName.toLowerCase();
                    }

                    // 判断是否可交互
                    const isClickable = el.tagName === 'A' || el.tagName === 'BUTTON' ||
                                        role === 'button' || el.onclick ||
                                        style.cursor === 'pointer';

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
                        isClickable: isClickable,
                        x: Math.round(rect.x),
                        y: Math.round(rect.y),
                        width: Math.round(rect.width),
                        height: Math.round(rect.height)
                    });
                }
            });
        });

        // 去重
        const seen = new Set();
        return results.filter(el => {
            const key = el.tag + '|' + el.text + '|' + el.id;
            if (seen.has(key)) return false;
            seen.add(key);
            return true;
        });
    }
    """)

    return result

print("=" * 70)
print("🎬 录制模式启动")
print("=" * 70)

p = sync_playwright().start()
browser = p.chromium.launch(headless=False)
context = browser.new_context()
page = context.new_page()

# ============================================================
# 第一阶段：自动登录
# ============================================================
print("\n【第一阶段】自动登录...")
page.goto("[请填写首页地址]", wait_until="domcontentloaded", timeout=15000)
time.sleep(3)

# 点击单位登录
print("  → 点击'单位登录'...")
try:
    page.locator(".unit-btn").click()
    time.sleep(2)
except Exception as e:
    print(f"  ✗ 失败: {e}")

# 填写账号密码
print("  → 填写账号密码...")
try:
    inputs = page.locator("input:visible").all()
    if len(inputs) >= 2:
        inputs[0].fill(ACCOUNT)
        inputs[1].fill(PASSWORD)
except Exception as e:
    print(f"  ✗ 失败: {e}")

print("\n" + "=" * 70)
print("【第二阶段】手动操作录制")
print("=" * 70)
print("""
📌 操作说明：

  你现在可以手动操作浏览器。每完成一个关键操作后，
  回到这里输入命令来记录该操作的元素信息。

  可用命令：
    - 按 Enter 记录当前焦点元素
    - 输入 's' 扫描当前页面所有元素
    - 输入 'd <描述>' 记录并添加描述
    - 输入 'w' 等待页面加载
    - 输入 'q' 退出并保存

  建议录制顺序：
    1. 输入验证码 → 回车 → 输入 'd 验证码输入框'
    2. 点击登录 → 回车 → 输入 'd 登录按钮'
    3. 选择单位 → 回车 → 输入 'd 单位选择'
    4. 进入招采系统 → 回车 → 输入 'd 招采系统入口'
    5. 导航到目标页面...

""")

# 交互式录制循环
while True:
    try:
        user_input = input("\n> ").strip()

        if user_input.lower() == 'q':
            print("退出录制...")
            break

        elif user_input.lower() == 's':
            print("扫描当前页面...")
            elements = scan_current_page(page)
            print(f"  发现 {len(elements)} 个可交互元素")

            # 保存页面扫描结果
            page_scan = {
                "timestamp": datetime.now().isoformat(),
                "url": page.url,
                "title": page.title(),
                "elementCount": len(elements),
                "elements": elements
            }

            filename = f"output/scan_{datetime.now().strftime('%H%M%S')}.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(page_scan, f, ensure_ascii=False, indent=2)
            print(f"  已保存到: {filename}")

            # 显示关键元素
            print("\n  【可点击元素】")
            clickable = [e for e in elements if e.get('isClickable')]
            for el in clickable[:15]:
                print(f"    [{el['tag']:6}] {el['text'][:40]:40} | {el['selector']}")

            print("\n  【输入框】")
            inputs = [e for e in elements if e['tag'] == 'INPUT']
            for el in inputs:
                print(f"    placeholder: {el.get('placeholder', '')[:30]:30} | name: {el.get('name', '')}")

        elif user_input.lower() == 'w':
            print("等待页面加载...")
            time.sleep(3)
            print("  当前URL:", page.url)

        elif user_input.lower().startswith('d '):
            description = user_input[2:]
            save_element_info(page, "user_action", description)

        elif user_input == '':
            # 只按回车，记录当前焦点元素
            save_element_info(page, "focus")

        else:
            print(f"未知命令: {user_input}")

    except EOFError:
        time.sleep(1)
        continue
    except KeyboardInterrupt:
        print("\n中断...")
        break

# ============================================================
# 保存录制结果
# ============================================================
print("\n" + "=" * 70)
print("【保存录制结果】")
print("=" * 70)

output = {
    "timestamp": datetime.now().isoformat(),
    "totalActions": len(recorded_actions),
    "actions": recorded_actions
}

filename = f"output/recorded_actions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
with open(filename, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n✅ 已保存 {len(recorded_actions)} 个操作记录到: {filename}")

# 生成自动化代码建议
print("\n" + "=" * 70)
print("【生成的 Playwright 代码建议】")
print("=" * 70)

for i, action in enumerate(recorded_actions):
    el = action.get('element', {})
    selectors = el.get('selectors', [])

    if selectors:
        best = selectors[0]
        code = f"# 步骤{i+1}: {action.get('description', action.get('action', ''))}\n"
        code += f"page.locator('{best['value']}').click()  # {el.get('tag')} - {el.get('text', '')[:30]}\n"
        print(code)

browser.close()
p.stop()
