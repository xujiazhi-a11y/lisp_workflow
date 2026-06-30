;; 测试跨行字符串
【定义 【测试多行字符串】
  【打印 "测试跨行字符串："】
  【定义 代码 "这是一行
这是第二行
这是第三行"】
  【打印 代码】
】

【定义 【测试多行JS】
  【打印 "\n测试跨行JS代码："】
  【定义 JS代码 "var btns = document.querySelectorAll('button');
for (var i = 0; i < btns.length; i++) {
  if (btns[i].innerText.includes('保存')) {
    btns[i].click();
    break;
  }
}"】
  【打印 JS代码】
】

【测试多行字符串】
【测试多行JS】
【打印 "\n✓ 测试完成！跨行字符串支持正常。"】