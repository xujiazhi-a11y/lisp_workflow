# 志语编辑器

## 1 简介
这是一个简陋的编辑器，里面内嵌了一个汉化Lisp语言的解释器，愚以为lisp和汉语乃至中国文化可产生有趣碰撞，汉化lisp聊可接近自然语言编程一事；同时，结合汉化lisp的形式，又尝试简化并汉化开源社区中那些好用的包的使用命令，集成到一个编辑器中，通过这种新的交互上的尝试，试图希望能够让开源社区更好地普惠到中国大众。

## 2 汉化lisp关键字命名说明

## 3 使用说明（具体案例）
### 3.1 非开发者模式案例
#### 非开发者模式-视频下载

用户可以通过输入“【下载 （视频url）】”，而后点击“运行”的方式完成主流视频网站平台（如bilibili、youtube等）上视频的下载，此功能可有效帮助视频创作者获取到所需的视频素材。所要输入的代码和程序执行效果如下面的图3.8、图3.9所示：
<div align=center>
<img src="https://gitee.com/jiafaCompiler/blog-editor/raw/master/upload/%E9%9D%9E%E5%BC%80%E5%8F%91%E8%80%85%E6%A8%A1%E5%BC%8F-%E8%A7%86%E9%A2%91%E4%B8%8B%E8%BD%BD-%E8%BE%93%E5%85%A5%E4%BB%A3%E7%A0%81.png" width=80% />
</div>
<p align="center"> 图3.8 非开发者模式-视频下载-输入代码 </p>

<div align=center>
<img src="https://gitee.com/jiafaCompiler/blog-editor/raw/master/upload/%E9%9D%9E%E5%BC%80%E5%8F%91%E8%80%85%E6%A8%A1%E5%BC%8F-%E8%A7%86%E9%A2%91%E4%B8%8B%E8%BD%BD-%E6%89%A7%E8%A1%8C%E7%BB%93%E6%9E%9C.png" width=80% />
</div>
<p align="center"> 图3.9 非开发者模式-视频下载-执行结果 </p>


#### 非开发者模式-格式转换

用户可以通过输入“【转为某某格式 文件存储地址】”，而后点击“运行”的方式完多媒体文件的格式转换，支持绝大部分多媒体文件格式，此功能可有效帮助到工作流中会涉及多媒体文件处理的人。所要输入的代码和程序执行效果如下面的图3.10、图3.11所示：

<div align=center>
<img src="https://gitee.com/jiafaCompiler/blog-editor/raw/master/upload/%E9%9D%9E%E5%BC%80%E5%8F%91%E8%80%85%E6%A8%A1%E5%BC%8F-%E6%A0%BC%E5%BC%8F%E8%BD%AC%E6%8D%A2-%E8%BE%93%E5%85%A5%E4%BB%A3%E7%A0%81.png" width=80% />
</div>
<p align="center"> 图3.10 非开发者模式-格式转换-输入代码 </p>

<div align=center>
<img src="https://gitee.com/jiafaCompiler/blog-editor/raw/master/upload/%E9%9D%9E%E5%BC%80%E5%8F%91%E8%80%85%E6%A8%A1%E5%BC%8F-%E6%A0%BC%E5%BC%8F%E8%BD%AC%E6%8D%A2-%E6%89%A7%E8%A1%8C%E7%BB%93%E6%9E%9C.png" width=80% />
</div>
<p align="center"> 图3.11 非开发者模式-格式转换-执行结果 </p>

#### 非开发者模式-格式转换

非开发者模式-智能语音助手
用户可以通过输入“【百度语音听写 【APP_ID （APP_ID）】【API_KEY（API_KEY）】【SECRET_KEY （SECRET_KEY）】（语音命令式操作）】”就能完成一个简单的语音识别助手，现在可以实现用语音控制方式帮用户完成录屏、截屏、屏幕文字识别、播放具体视频、播放具体音频、看某某小说等等操作。实现成本（代码量）相对较低。所要输入的代码和程序执行效果如下面的图3.12、图3.13所示：

<div align=center>
<img src="https://gitee.com/jiafaCompiler/blog-editor/raw/master/upload/%E9%9D%9E%E5%BC%80%E5%8F%91%E8%80%85%E6%A8%A1%E5%BC%8F-%E6%99%BA%E8%83%BD%E8%AF%AD%E9%9F%B3%E5%8A%A9%E6%89%8B-%E8%BE%93%E5%85%A5%E4%BB%A3%E7%A0%81.jpg" width=80% />
</div>
<p align="center"> 图3.12 非开发者模式-智能语音助手-输入代码 </p>

<div align=center>
<img src="https://gitee.com/jiafaCompiler/blog-editor/raw/master/upload/%E9%9D%9E%E5%BC%80%E5%8F%91%E8%80%85%E6%A8%A1%E5%BC%8F-%E6%99%BA%E8%83%BD%E8%AF%AD%E9%9F%B3%E5%8A%A9%E6%89%8B-%E6%89%A7%E8%A1%8C%E7%BB%93%E6%9E%9C.png" width=80% />
</div>
<p align="center"> 图3.13 非开发者模式-智能语音助手-执行结果 </p>
### 3.2 开发者模式案例

“开发者模式”主在用汉化lisp语言实现一些工程、算法过程，完成对语言能力的进一步扩展。

#### 开发者模式-阶乘

下图3.14展示如何用本研究中产出的汉化lisp语言以常规递归思路来实现阶乘算法过程。

#### 开发者模式-开根

下图3.15展示用不动点手段来实现开根算法过程（不动点计算公式：$x = f(x)$）
