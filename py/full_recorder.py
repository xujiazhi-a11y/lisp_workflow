#!/usr/bin/env python3
"""
医疗备案填表 - 完整录制脚本
包含多个页面的元素扫描和录制
"""
import time
import json
from playwright.sync_api import sync_playwright

ACCOUNT = "[请填写账号]"
PASSWORD = "[请填写密码]"

# 存储所有录制的步骤
recorded_steps = []

def scan_page(page, step_name):
    """扫描当前页面并保存元素信息"""
    print(f"\n【扫描 {step_name}】")

    # 滚动加载所有元素
    page.evaluate("""
    () => {
        window.scrollBy(0, 500);
        return new Promise(r => setTimeout(r, 200));
    }
    """)
    page.evaluate("window.scrollTo(0, 0)")

    elements = page.evaluate("""
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
                    const name = el.getAttribute('name') || '';
                    const id = el.id || '';
                    const type = el.type || '';
                    const role = el.getAttribute('role') || '';

                    // 生成多种选择器策略
                    let selectors = [];

                    if (id) selectors.push({type: 'id', value: `#${id}`, priority: 1});
                    if (placeholder) selectors.push({type: 'placeholder', value: `${el.tagName.toLowerCase()}[placeholder='${placeholder}']`, priority: 2});
                    if (name) selectors.push({type: 'name', value: `${el.tagName.toLowerCase()}[name='${name}']`, priority: 2});
                    if (role) selectors.push({type: 'role', value: `${el.tagName.toLowerCase()}[role='${role}']`, priority: 2});
                    if (text && text.length < 30 && !text.includes('\n')) {
                        selectors.push({type: 'text', value: `text='${text}'`, priority: 3});
                    }
                    if (el.className && typeof el.className === 'string') {
                        const classes = el.className.split(' ').filter(c => c && !c.includes(':'));
                        if (classes.length > 0) {
                            selectors.push({type: 'class', value: `${el.tagName.toLowerCase()}.${classes[0]}`, priority: 3});
                        }
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
                            position: {
                                x: Math.round(rect.x),
                                y: Math.round(rect.y),
                                width: Math.round(rect.width),
                                height: Math.round(rect.height)
                            }
                        });
                    }
                }
            });
        });
        return results;
    }
    """)

    # 保存扫描结果
    page_info = {
        "step": step_name,
        "url": page.url,
        "title": page.title(),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elementCount": len(elements),
        "elements": elements
    }

    filename = f"output/step_{len(recorded_steps)+1}_{step_name.replace(' ', '_')}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(page_info, f, ensure_ascii=False, indent=2)

    recorded_steps.append(page_info)

    print(f"  URL: {page.url}")
    print(f"  标题: {page.title()}")
    print(f"  元素数: {len(elements)}")
    print(f"  保存: {filename}")

    # 显示关键元素
    print("\n  【输入框】")
    inputs = [e for e in elements if e['tag'] == 'INPUT']
    for el in inputs:
        placeholder = el.get('placeholder', '')[:30]
        selector = el['selectors'][0]['value'] if el['selectors'] else '无'
        print(f"    placeholder: '{placeholder}' | {selector}")

    print("\n  【可点击元素】")
    clickable = [e for e in elements if e['tag'] in ['A', 'BUTTON'] or e.get('role') == 'button' or 'btn' in e.get('class', '').lower()]
    for el in clickable[:10]:
        text = el.get('text', '')[:30] or el.get('placeholder', '')[:30]
        selector = el['selectors'][0]['value'] if el['selectors'] else '无'
        print(f"    '{text}' | {selector}")

    print("\n  【下拉框】")
    selects = [e for e in elements if e['tag'] == 'SELECT']
    for el in selects:
        selector = el['selectors'][0]['value'] if el['selectors'] else '无'
        print(f"    SELECT | {selector}")

    return page_info

def record_action(page, action_type, description=""):
    """记录一个用户操作"""
    # 获取当前焦点元素
    element_info = page.evaluate("""
    () => {
        const el = document.activeElement;
        if (!el) return null;

        const rect = el.getBoundingClientRect();

        let selectors = [];

        if (el.id) selectors.push({type: 'id', value: `#${el.id}`, priority: 1});
        const placeholder = el.getAttribute('placeholder');
        if (placeholder) selectors.push({type: 'placeholder', value: `${el.tagName.toLowerCase()}[placeholder='${placeholder}']`, priority: 2});
        const name = el.getAttribute('name');
        if (name) selectors.push({type: 'name', value: `${el.tagName.toLowerCase()}[name='${name}']`, priority: 2});
        const role = el.getAttribute('role');
        if (role) selectors.push({type: 'role', value: `${el.tagName.toLowerCase()}[role='${role}']`, priority: 2});

        if (el.className && typeof el.className === 'string') {
            const classes = el.className.split(' ').filter(c => c && !c.includes(':'));
            if (classes.length > 0) {
                selectors.push({type: 'class', value: `${el.tagName.toLowerCase()}.${classes[0]}`, priority: 3});
            }
        }

        return {
            tag: el.tagName,
            text: (el.innerText || el.textContent || '').trim().substring(0, 50),
            placeholder: placeholder || '',
            id: el.id || '',
            className: el.className || '',
            value: el.value || '',
            selectors: selectors,
            position: {x: Math.round(rect.x), y: Math.round(rect.y)}
        };
    }
    """)

    if element_info and element_info['selectors']:
        action = {
            "step": len(recorded_steps) + 1,
            "type": action_type,
            "description": description,
            "element": element_info,
            "url": page.url
        }
        recorded_steps.append(action)

        selector = element_info['selectors'][0]['value']
        print(f"\n✅ 已记录: {action_type} - {description}")
        print(f"   元素: {element_info['tag']} - {element_info.get('text', '')[:30]}")
        print(f"   选择器: {selector}")

        return selector
    return None

# ============================================================
# 主流程
# ============================================================
print("=" * 70)
print("🎬 医疗备案填表 - 完整录制")
print("=" * 70)

p = sync_playwright().start()
browser = p.chromium.launch(headless=False)
context = browser.new_context()
page = context.new_page()

# ------------------------------------------------------------
# 步骤1: 打开首页
# ------------------------------------------------------------
print("\n【步骤1】打开首页...")
page.goto("[请填写首页地址]", wait_until="domcontentloaded", timeout=15000)
time.sleep(2)
scan_page(page, "首页")

# ------------------------------------------------------------
# 步骤2: 点击单位登录
# ------------------------------------------------------------
print("\n【步骤2】点击'单位登录'...")
try:
    page.locator(".unit-btn").click()
    time.sleep(2)
    scan_page(page, "单位登录页")
except Exception as e:
    print(f"  ✗ 失败: {e}")

# ------------------------------------------------------------
# 步骤3: 填写账号密码
# ------------------------------------------------------------
print("\n【步骤3】填写账号密码...")
try:
    page.locator("input[placeholder='单位账号/经办人账号']").fill(ACCOUNT)
    page.locator("input[placeholder='请输入密码']").fill(PASSWORD)
    print("  ✓ 已填写")
    time.sleep(1)
except Exception as e:
    print(f"  ✗ 失败: {e}")

# ------------------------------------------------------------
# 手动操作引导
# ------------------------------------------------------------
print("\n" + "=" * 70)
print("【手动操作模式】")
print("=" * 70)
print("""
📌 请在浏览器中完成以下操作，每完成一步，告诉我是哪一步：

  [验证码] - 输入验证码后告诉我"验证码"
  [登录] - 点击登录按钮后告诉我"登录"
  [单位] - 选择单位后告诉我"单位"
  [招采] - 进入招采系统后告诉我"招采"
  [骨科] - 找到骨科脊柱后告诉我"骨科"
  [计划] - 点击采购计划后告诉我"计划"
  [备案] - 到达备案填表页面后告诉我"备案"

  每告诉我一个步骤，我会自动扫描并记录元素信息！
""")
print("=" * 70)

# 定义每个步骤的提示
step_prompts = {
    "验证码": "请输入验证码...",
    "登录": "请点击登录按钮...",
    "单位": "请选择单位并确认...",
    "招采": "请进入招采系统...",
    "骨科": "请找到并点击'骨科脊柱人工关节'...",
    "计划": "请点击'采购计划'...",
    "备案": "请导航到备案填表页面..."
}

current_prompt = "验证码"

while True:
    try:
        user_input = input(f"\n当前步骤: [{current_prompt}] - 完成后请输入'yes'，或直接输入下一步名称: ").strip().lower()

        if user_input == 'q':
            break

        # 扫描当前页面
        scan_page(page, f"步骤_{current_prompt}")

        # 切换到下一步
        if user_input == 'yes':
            # 按顺序进入下一步
            steps_order = ["验证码", "登录", "单位", "招采", "骨科", "计划", "备案"]
            try:
                idx = steps_order.index(current_prompt)
                if idx < len(steps_order) - 1:
                    current_prompt = steps_order[idx + 1]
            except:
                current_prompt = "完成"
        elif user_input in step_prompts:
            current_prompt = user_input

        print(f"\n下一步: [{current_prompt}]")
        print(step_prompts.get(current_prompt, "继续操作..."))

    except EOFError:
        time.sleep(1)
        continue
    except KeyboardInterrupt:
        break

# ------------------------------------------------------------
# 保存所有录制结果
# ------------------------------------------------------------
print("\n" + "=" * 70)
print("【保存录制结果】")
print("=" * 70)

output = {
    "totalSteps": len(recorded_steps),
    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    "steps": recorded_steps
}

with open("output/full_recording.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n✅ 已保存 {len(recorded_steps)} 个步骤到: output/full_recording.json")

# 生成自动化代码
print("\n" + "=" * 70)
print("【生成的自动化代码】")
print("=" * 70)

code_lines = ["# 医疗备案填表自动化脚本\n", "import time\n", "from playwright.sync_api import sync_playwright\n\n"]
code_lines.append("def beian_automation():\n")
code_lines.append("    p = sync_playwright().start()\n")
code_lines.append("    browser = p.chromium.launch(headless=False)\n")
code_lines.append("    context = browser.new_context()\n")
code_lines.append("    page = context.new_page()\n\n")

for step in recorded_steps:
    if 'url' in step and 'elements' in step:
        # 这是页面扫描结果
        code_lines.append(f"    # 页面: {step.get('step', '未知')}\n")
        code_lines.append(f"    # URL: {step.get('url', '')}\n")
        code_lines.append(f"    # 元素数: {step.get('elementCount', 0)}\n")
        code_lines.append(f"    time.sleep(2)\n\n")

code_lines.append("    browser.close()\n")
code_lines.append("    p.stop()\n\n")
code_lines.append("if __name__ == '__main__':\n")
code_lines.append("    beian_automation()\n")

with open("output/automation_code.py", "w", encoding="utf-8") as f:
    f.writelines(code_lines)

print("\n✅ 代码已保存到: output/automation_code.py")

browser.close()
p.stop()
print("\n录制完成！")