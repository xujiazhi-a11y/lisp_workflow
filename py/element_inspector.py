#!/usr/bin/env python3
"""
元素检查工具：查看任意元素的详细信息和选择器策略
使用 Playwright 的 locator.highlight 功能
"""
import time
from playwright.sync_api import sync_playwright

ACCOUNT = "[请填写账号]"
PASSWORD = "[请填写密码]"

print("=" * 60)
print("🔍 元素检查工具")
print("=" * 60)

p = sync_playwright().start()
browser = p.chromium.launch(headless=False)
context = browser.new_context()
page = context.new_page()
page.goto("[请填写首页地址]", wait_until="domcontentloaded", timeout=15000)
time.sleep(3)

# 自动登录部分
print("\n【自动登录】")
try:
    page.locator(".unit-btn").click()
    time.sleep(2)
    inputs = page.locator("input:visible").all()
    if len(inputs) >= 2:
        inputs[0].fill(ACCOUNT)
        inputs[1].fill(PASSWORD)
    print("✓ 已填写账号密码")
except Exception as e:
    print(f"✗ 失败: {e}")

print("\n" + "=" * 60)
print("【检查模式】")
print("=" * 60)
print("""
📌 在浏览器中手动操作，然后在此输入元素信息：

  用法：
    1. 在浏览器中点击或悬停在你想检查的元素上
    2. 按 F12 打开开发者工具
    3. 使用 Elements 面板选中元素
    4. 在控制台运行以下代码获取元素信息：
       console.log(JSON.stringify({
         tagName: $0.tagName,
         id: $0.id,
         className: $0.className,
         text: $0.innerText?.substring(0,50),
         placeholder: $0.placeholder,
         name: $0.name,
         role: $0.getAttribute('role'),
         type: $0.type
       }, null, 2))

  或者使用命令：
    - 'scan' - 扫描当前页面所有元素
    - 'highlight <选择器>' - 高亮显示元素
    - 'q' - 退出

""")

while True:
    try:
        user_input = input("\n> ").strip()

        if user_input.lower() == 'q':
            break

        elif user_input.lower() == 'scan':
            elements = page.locator("*, *").element_handles()
            print(f"页面总元素数: {len(elements)}")

            # 显示按钮
            print("\n【按钮】")
            buttons = page.locator("button:visible, [role='button']:visible").all()
            print(f"  找到 {len(buttons)} 个按钮")

            # 显示输入框
            print("\n【输入框】")
            inputs = page.locator("input:visible, textarea:visible").all()
            for inp in inputs[:10]:
                placeholder = inp.get_attribute("placeholder") or ""
                name = inp.get_attribute("name") or ""
                print(f"  - placeholder: '{placeholder}' name: '{name}'")

            # 显示链接
            print("\n【链接】")
            links = page.locator("a:visible").all()
            print(f"  找到 {len(links)} 个链接")
            for link in links[:10]:
                text = link.inner_text() or ""
                href = link.get_attribute("href") or ""
                print(f"  - '{text[:40]}' → {href[:40]}")

        elif user_input.lower().startswith('highlight '):
            selector = user_input[10:]
            try:
                page.locator(selector).highlight()
                print(f"✓ 已高亮: {selector}")
                time.sleep(3)
            except Exception as e:
                print(f"✗ 高亮失败: {e}")

        elif user_input:
            # 尝试解析为 JSON（从控制台复制的结果）
            try:
                import json
                el_info = json.loads(user_input)
                print("\n【元素信息】")
                print(json.dumps(el_info, indent=2, ensure_ascii=False))

                # 生成选择器建议
                selectors = []
                if el_info.get('id'):
                    selectors.append(f"#{el_info['id']}")
                if el_info.get('name'):
                    selectors.append(f"[name='{el_info['name']}']")
                if el_info.get('placeholder'):
                    selectors.append(f"[placeholder='{el_info['placeholder']}']")
                if el_info.get('className'):
                    classes = el_info['className'].split()
                    if classes:
                        selectors.append(f".{'.'.join(classes[:2])}")
                if el_info.get('text'):
                    text = el_info['text'].strip()
                    if text and len(text) < 30:
                        selectors.append(f"text='{text}'")

                print("\n【推荐选择器】")
                for i, sel in enumerate(selectors[:5], 1):
                    print(f"  {i}. {sel}")

                # 尝试定位
                for sel in selectors[:3]:
                    try:
                        locator = page.locator(sel)
                        if locator.count() == 1:
                            print(f"\n✅ 唯一匹配: {sel}")
                            locator.highlight()
                            break
                        elif locator.count() > 1:
                            print(f"\n⚠️ 多个匹配 ({locator.count()} 个): {sel}")
                    except:
                        pass

            except json.JSONDecodeError:
                print("无法解析输入，请输入有效的 JSON")

    except EOFError:
        time.sleep(1)
        continue
    except KeyboardInterrupt:
        break

browser.close()
p.stop()
print("\n检查完成！")