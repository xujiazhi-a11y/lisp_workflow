#!/usr/bin/env python3
"""
快速扫描当前浏览器页面
"""
import time
import json
from playwright.sync_api import sync_playwright

print("启动浏览器并连接...")

p = sync_playwright().start()
browser = p.chromium.launch(headless=False)
context = browser.new_context()
page = context.new_page()

print("打开目标页面...")
print("请在浏览器中手动导航到你的目标页面，或者告诉我URL")

try:
    # 尝试常用的目标URL
    urls = [
        "[请填写地址]",
        "[请填写地址]",
    ]
    for url in urls:
        try:
            page.goto(url, timeout=5000)
            break
        except:
            continue

    print(f"当前URL: {page.url}")
    print(f"当前标题: {page.title()}")
    print("\n等待5秒让页面加载...")
    time.sleep(5)

    # 扫描
    elements = page.evaluate("""
    () => {
        const interactiveTags = ['A', 'BUTTON', 'INPUT', 'SELECT', 'TEXTAREA', 'LI', 'DIV', 'SPAN'];
        const results = [];
        const seen = new Set();

        interactiveTags.forEach(tag => {
            document.querySelectorAll(tag).forEach(el => {
                const rect = el.getBoundingClientRect();
                const isVisible = rect.width > 0 && rect.height > 0;

                if (isVisible) {
                    const text = (el.innerText || el.textContent || '').trim().substring(0, 100);
                    const placeholder = el.getAttribute('placeholder') || '';
                    const name = el.getAttribute('name') || '';
                    const type = el.type || '';

                    let selector = '';
                    if (el.id) selector = `#${el.id}`;
                    else if (placeholder) selector = `${el.tagName.toLowerCase()}[placeholder='${placeholder}']`;
                    else if (name) selector = `${el.tagName.toLowerCase()}[name='${name}']`;
                    else if (el.className && typeof el.className === 'string') {
                        const classes = el.className.split(' ').filter(c => c && !c.includes(':'));
                        if (classes.length > 0) selector = `${el.tagName.toLowerCase()}.${classes[0]}`;
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
                            selector: selector
                        });
                    }
                }
            });
        });
        return results;
    }
    """)

    # 保存
    result = {
        "url": page.url,
        "title": page.title(),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elementCount": len(elements),
        "elements": elements
    }

    filename = f"output/target_page_{int(time.time())}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 已保存到: {filename}")
    print(f"元素数量: {len(elements)}")

    # 显示关键元素
    print("\n【可点击元素】")
    clickable = [e for e in elements if e['tag'] in ['A', 'BUTTON'] or e.get('role') == 'button' or 'btn' in e.get('class', '').lower()]
    for el in clickable[:15]:
        print(f"  [{el['tag']:6}] {el['text'][:40]:40} | {el['selector']}")

    print("\n【输入框】")
    inputs = [e for e in elements if e['tag'] == 'INPUT']
    for el in inputs:
        print(f"  placeholder: {el.get('placeholder', '')[:30]:30} | {el['selector']}")

    print("\n【列表项】")
    lis = [e for e in elements if e['tag'] == 'LI']
    for el in lis[:15]:
        print(f"  {el['text'][:40]:40} | {el['selector']}")

except Exception as e:
    print(f"扫描出错: {e}")

browser.close()
p.stop()