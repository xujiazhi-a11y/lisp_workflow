#!/usr/bin/env python3
"""
简单扫描脚本：连接到浏览器，扫描当前页面
不需要用户输入，直接扫描并保存结果
"""
import time
import json
from playwright.sync_api import sync_playwright

print("=" * 60)
print("🔍 页面扫描工具")
print("=" * 60)
print("\n请在打开的浏览器中导航到目标页面...")
print("脚本会每10秒自动扫描一次并保存结果\n")

p = sync_playwright().start()
browser = p.chromium.launch(headless=False)
context = browser.new_context()
page = context.new_page()

# 快速导航到登录页
page.goto("[请填写首页地址]", wait_until="domcontentloaded", timeout=15000)
time.sleep(2)

# 点击单位登录
try:
    page.locator(".unit-btn").click()
    time.sleep(1)
    # 填写账号密码
    inputs = page.locator("input:visible").all()
    if len(inputs) >= 2:
        inputs[0].fill("[请填写账号]")
        inputs[1].fill("[请填写密码]")
except:
    pass

print("浏览器已打开，请完成登录并导航到目标页面...")
print("扫描结果会自动保存到 output/ 目录\n")

# 持续扫描模式
scan_count = 0
last_url = ""

while True:
    time.sleep(5)  # 每5秒检查一次

    current_url = page.url
    if current_url != last_url or scan_count == 0:
        last_url = current_url
        scan_count += 1

        # 扫描页面
        try:
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
                                    selector: selector,
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

            # 保存结果
            result = {
                "scanId": scan_count,
                "url": current_url,
                "title": page.title(),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "elementCount": len(elements),
                "elements": elements
            }

            filename = f"output/scan_{scan_count}_{current_url.split('/')[-1].replace('#', '') or 'page'}.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            print(f"[{time.strftime('%H:%M:%S')}] 扫描 #{scan_count}")
            print(f"  URL: {current_url}")
            print(f"  标题: {page.title()}")
            print(f"  元素: {len(elements)} 个")
            print(f"  保存: {filename}")
            print()

        except Exception as e:
            print(f"扫描出错: {e}")
