#!/usr/bin/env python3
"""
最终观察模式：自动登录，等待用户导航，扫描目标页面
"""
import time
import json
from playwright.sync_api import sync_playwright

ACCOUNT = "[请填写账号]"
PASSWORD = "[请填写密码]"

print("=" * 60)
print("启动浏览器...")
print("=" * 60)

p = sync_playwright().start()
browser = p.chromium.launch(headless=False)
context = browser.new_context()
page = context.new_page()
page.goto("[请填写首页地址]", wait_until="domcontentloaded", timeout=15000)
time.sleep(3)

# 步骤1: 点击"单位登录"
print("\n【步骤1】自动点击'单位登录'...")
try:
    page.locator(".unit-btn").click()
    print("✓ 已点击单位登录")
except Exception as e:
    print(f"✗ 失败: {e}")

time.sleep(3)

# 步骤2: 填写账号密码
print("\n【步骤2】自动填写账号密码...")
try:
    inputs = page.locator("input:visible").all()
    if len(inputs) >= 2:
        inputs[0].fill(ACCOUNT)
        inputs[1].fill(PASSWORD)
        print("✓ 已填写账号密码")
    else:
        print(f"✗ 只找到 {len(inputs)} 个输入框")
except Exception as e:
    print(f"✗ 失败: {e}")

print("\n" + "=" * 60)
print("【请在浏览器中完成以下操作】")
print("")
print("  1. 输入验证码")
print("  2. 点击登录按钮")
print("  3. 选择单位并确认登录")
print("  4. 点击招采系统")
print("  5. 点击'骨科脊柱人工关节'")
print("  6. 点击'采购计划'")
print("  7. 点击'采购计划管理'")
print("")
print("  完成所有操作后，回到此终端按回车键")
print("=" * 60)

# 等待用户输入
while True:
    try:
        user_input = input("\n按回车继续（或输入'q'退出）: ")
        if user_input.lower() == 'q':
            print("退出...")
            browser.close()
            p.stop()
            exit(0)
        break
    except EOFError:
        # 后台运行模式，等待一段时间
        time.sleep(5)
        continue

# 扫描最终页面
print("\n【扫描页面元素】")
try:
    # 滚动页面加载所有元素
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
            }, 3000);
        });
    }
    """)
    time.sleep(1)
    
    # 扫描元素
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
    
    # 保存结果
    with open("output/obs_final.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ 扫描完成！")
    print(f"  URL: {result['url']}")
    print(f"  标题: {result['title']}")
    print(f"  元素数: {result['elementCount']}")
    
    # 显示菜单相关元素
    print("\n【菜单相关元素】")
    menu_items = [e for e in result['elements'] if any(kw in e['text'] for kw in ['骨科', '采购计划', '采购管理', '备案', '挂网', '目录'])]
    for item in menu_items:
        print(f"  [{item['tag']:8}] {item['text'][:50]:50} | class: {item['class'][:30]}")
    
    # 显示所有按钮
    print("\n【所有按钮】")
    buttons = [e for e in result['elements'] if e['tag'] == 'BUTTON']
    for btn in buttons[:20]:
        print(f"  {btn['text'][:40]:40} | class: {btn['class'][:30]}")
    
    # 显示所有输入框
    print("\n【所有输入框】")
    inputs = [e for e in result['elements'] if e['tag'] == 'INPUT']
    for inp in inputs:
        placeholder = inp.get('placeholder', '')
        print(f"  placeholder: {placeholder[:40]:40} | class: {inp['class'][:30]}")
    
except Exception as e:
    print(f"\n✗ 扫描失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("观察完成！请告诉我你当前看到的页面内容")
print("=" * 60)

# 保持浏览器打开
print("\n浏览器保持打开状态，请手动关闭或按Ctrl+C退出")
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass

browser.close()
p.stop()
