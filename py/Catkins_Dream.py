import re
import sys
import math
import os
import io
import operator as 基操
from 执行非开发者模式语句 import 执行非开发者模式语句

#下面这一句是通知浏览器控制台用utf-8编码
if sys.stdout:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8')
绝对路径 = sys.argv[1]

class 符号(str): pass
数字 = (int, float)
序列 = list
字符串 = str

def 定为符号(符, 符号表={}):
    if 符 not in 符号表: 符号表[符] = 符号(符)
    return 符号表[符]

保留字定义, 保留字如果, 保留字赋, 保留字道, 保留字开始, 保留字宏, 保留字引 = map(定为符号,\
"定义      如果        ！赋        道       开始        宏       引      ".split())

程序终止 = 符号('#<eof-object>')

class 文件句读(object):
    句读方法 = r'''\s*([('`,)]|"(?:[\\].|[^\\"])*"|;.*|[^\s('"`,;)]*)(.*)'''
    #句读方法 = r'(.*)'
    def __init__(自身, file):
        自身.file = file;
        自身.行内容 = ''
    def 下一实词或虚词(自身):
        while True:
            if 自身.行内容 == '': 自身.行内容 = 自身.file.readline()
            "----------------------替换开始------------------------"
            #括号可以用合适的文言文虚词代替
            意为左括号序列 = ['【', '~其', '~然', '~是', '~此', '~斯']
            意为右括号序列 = ['】', '也~', '者~', '耳~', '焉~', '哉~']
            for 左起符 in 意为左括号序列:
                自身.行内容 = re.sub(左起符, ' 【 ', 自身.行内容)
            for 右落符 in 意为右括号序列:
                自身.行内容 = re.sub(右落符, ' 】 ', 自身.行内容)
            #（）括起的东西会被去除，比如（为），但现在这个写法会导致引号中的（）内容消失，所以以后需要改
            自身.行内容 = re.sub(r'（.*?）', '', 自身.行内容)
            #中文引号替换为英文引号
            自身.行内容 = re.sub(r'\“', '\"', 自身.行内容)
            自身.行内容 = re.sub(r'\”', '\"', 自身.行内容)
            #中文分号替换为英文分号
            自身.行内容 = re.sub(r'；', ';', 自身.行内容)
            "----------------------替换完毕------------------------"
            if 自身.行内容 == '': return 程序终止
            实词或虚词, 自身.行内容 = re.match(文件句读.句读方法, 自身.行内容).groups()
            #实词或虚词, 自身.行内容 = re.match(文件句读.句读方法, 自身.行内容)
            if 实词或虚词 != '' and not 实词或虚词.startswith(';'):
                return 实词或虚词

#暂未写引号分支
def 逐句读(句读后文件):
    def 读取(实词或虚词):
        if 实词或虚词 == '【':
            句 = []
            while True:
                实词或虚词 = 句读后文件.下一实词或虚词()
                if 实词或虚词 == '】': return 句
                else: 句.append(读取(实词或虚词))
        elif 实词或虚词 == '】' : raise SyntaxError('多余的 】')
        elif 实词或虚词 is 程序终止: raise SyntaxError('程序异常终止')
        else: return 按实词解(实词或虚词)
    新实词或虚词 = 句读后文件.下一实词或虚词()
    return 程序终止 if 新实词或虚词 is 程序终止 else 读取(新实词或虚词)

def 按实词解(实词或虚词):
    if 实词或虚词 == '#t': return True
    elif 实词或虚词 == '#f': return False
    elif 实词或虚词[0] == '"':  
        return 实词或虚词[1:-1]
    try: return int(实词或虚词)
    except ValueError:
        try: return float(实词或虚词)
        except ValueError:
            try: return complex(实词或虚词.replace('i', 'j', 1))
            except ValueError:
                return 定为符号(实词或虚词)

def 转絮梦表达式(表达式):
    "表达式格式转换"
    if 表达式 is True: return "#真"
    elif 表达式 is False: return "#假"
    elif isinstance(表达式, 符号): return 表达式
    #这一行留给字符串类型
    elif isinstance(表达式, str): return '"%s"' % 表达式.replace('"',r'\"')
    elif isinstance(表达式, 序列): return '【' + ' '.join(map(转絮梦表达式, 表达式)) + '】'
    else: return str(表达式)


def 加载(文件路径):
    终端交互(None, 文件句读(open(文件路径, encoding='UTF-8')), None)

#python的运算符是二元的，这里需要改为可以支持多个运算数的版本：
def 加(*参数序列):
    和 = 0
    for 参数 in 参数序列:
        和 = 和 + 参数
    return 和

def 减(*参数序列):
    差 = 0
    被减数 = 参数序列[0]
    减数序列 = 参数序列[1:]
    for 减数 in 减数序列:
        被减数 = 被减数 - 减数
    差 = 被减数
    return 差

def 乘(*参数序列):
    积 = 1
    for 参数 in 参数序列:
        积 = 参数 * 积
    return 积

def 除(*参数序列):
    商 = 1
    被除数 = 参数序列[0]
    除数序列 = 参数序列[1:]
    for 除数 in 除数序列:
        被除数 = 被除数 / 除数
    商 = 被除数
    return 商

def 与(*参数序列):
    结果 = True
    for 参数 in 参数序列:
        结果 = 结果 and 参数
    return 结果

def 或(*参数序列):
    结果 = False
    for 参数 in 参数序列:
        结果 = 结果 or 参数
    return 结果
# 是否需要在最底层就有“平均值”的定义待考虑，也许后续可再将此注释掉，开放出来给用户 
def 平均值(*参数序列):
    结果 = 0
    和 = 0
    for 参数 in 参数序列:
        和 = 和 + 参数
    结果 = 和 / len(参数序列)
    return 结果
        
#可以声明一个形参为一个列表，此时传入的实参会构成一个列表和这单个的形参发生匹配
class 忆义(dict):
    def __init__(自身, 形参序列=(), 实参序列=(), 下层忆义=None):
        自身.下层忆义 = 下层忆义
        "如果形参'序列'是单个符号的话，用户会希望这一个符号能够接收一个序列"
        if isinstance(形参序列, 符号):
            self.update({形参序列:序列(实参序列)})
        else:
            if len(形参序列) != len(实参序列):
                raise TypeError('形参个数和实参个数不匹配，形参为：%s，传入实参为：%s， '
                                % (转絮梦表达式(形参序列), 转絮梦表达式(实参序列)))
            自身.update(zip(形参序列, 实参序列))
    def 询义(自身, 符):
        if 符 in 自身: return 自身
        elif 自身.下层忆义 is None: raise LookupError(符)
        else: return 自身.下层忆义.询义(符)                

class 新层忆义中衍求过程体(object):
    def __init__(自身, 形参序列, 过程体, 所在层忆义):
        自身.形参序列 = 形参序列
        自身.过程体 = 过程体
        自身.所在层忆义 = 所在层忆义
    def __call__(自身, *实参序列):
        #在所在层忆义上根据传入的实参，去和定义的道中的形参去绑定，“垒”出一层新的忆义，在新层忆义中衍过程体，
        #即新层忆义中，有对道的过程体(+ x 1)中的x的定义x: 1，那就能在新层中求算出过程体的值的结果为2传给下层
        return 衍(自身.过程体, 忆义(自身.形参序列, 实参序列, 自身.所在层忆义))  

def 成对(表达式): return 表达式 != [] and isinstance(表达式, 序列)
def 宇对(显者,隐者):
    return [显者] + 隐者

def 伊始忆义():
    忆 = 忆义()
    忆.update(vars(math)) # sin, cos, sqrt, pi, ...
    忆.update({
        '+':加, '-':减, '*':乘, '/':除,
        '平均值':平均值,
        '求余': 基操.mod,
        '>':基操.gt, '<':基操.lt, '>=':基操.ge, '<=':基操.le, '=':基操.eq,
        '大于':基操.gt, '小于':基操.lt, '大于等于':基操.ge, '小于等于':基操.le,
        '与': 与,
        '或': 或,
        '#真': True,
        '#假': False,
        #下面若想支持别的布尔值名称，涉及返回值问题，不能像下面这样简单添加
        #'#是': True,
        #'#否': False,
        #绝对的空值要怎么定义？需要一种方法定义绝对的空值，仅仅把空值定义[]不能满足需求，需要[]里面的那么空
        # '不': 基操.not,
        '绝对值':      abs,
        '合':          基操.add,
        '求':          lambda 执行操作, 参数序列: 执行操作(*参数序列),
        '开始':        lambda *元: 元[-1],
        '显者':        lambda 元: 元[0],
        '隐者':        lambda 元: 元[1:],
        '宇对':        宇对, 
        '？成对':      成对,
        '？同':        基操.is_,
        '？等':        基操.eq,
        '次方':        pow,
        '？等':        基操.eq,
        '长度':        len,
        '序列':        lambda *元: 序列(元),
        '？序列':      lambda 元: isinstance(元, 序列),
        #'映射':        map,  #映射操作可以用scheme语法实现，python的map返回的是一个迭代器
        '最大值':      max,
        '最小值':      min,
        '不':         基操.not_,
        '？空':       lambda 元: 元 == [],
        '？数':       lambda 元: isinstance(元, 数字),
        '？过程':     callable,
        '舍入':       round,
        '？符':       lambda 元: isinstance(元, 符号),
        '输出':       lambda 表达式,控制台输出=sys.stdout: 控制台输出.write(表达式+'\n' if isinstance(表达式, str) else 转絮梦表达式(表达式)+'\n'),
        '加载':       lambda 文件路径: 加载(文件路径)
    })
    return 忆
底层忆义 = 伊始忆义()

def 衍(表达式, 忆=底层忆义):
    if 表达式 == None:
        return 表达式
    if isinstance(表达式, 符号):
        return 忆.询义(表达式)[表达式]
    #注！还没写完，除了数字直接返回，现在应该还有字符串等等类型需要直接返回
    elif not isinstance(表达式, 序列):
        #常量直接返回
        return 表达式
    elif 表达式[0] == '如果':
        (_, 条件表达式, 真时表达式, 假时表达式) = 表达式  #按语句形式分别赋值
        结果表达式 = (真时表达式 if 衍(条件表达式, 忆) else 假时表达式)
        return 衍(结果表达式, 忆)
    elif 表达式[0] == '情况符合':
        #print(表达式)
        for 分支 in 表达式[1:]:
            if 分支[0] == '其它情况' or 分支[0] == '否则':
                return 衍(分支[1], 忆)
            elif 衍(分支[0], 忆) == True:
                return 衍(分支[1], 忆)
    elif 表达式[0] == '定义':
        (_, 被定义符, 所给定义) = 表达式
        忆[被定义符] = 衍(所给定义, 忆)
    elif 表达式[0] == '引':
        #【引 【1 2】】
        (_, 所引表达式) = 表达式
        return 所引表达式
    elif 表达式[0] == '！赋':
        (_, 被赋值符号, 所赋值) = 表达式
        if 被赋值符号 not in 忆:
            忆[被赋值符号] = 衍(所赋值, 忆)
            忆.询义(被赋值符号)[被赋值符号] = 衍(所赋值, 忆)
        else: 忆.询义(被赋值符号)[被赋值符号] = 衍(所赋值, 忆)
    elif 表达式[0] == '道':
        (_, 形参序列, 过程体) = 表达式
        #当调用时实参会传入和形参组成新层忆义，具体看 新层忆义中衍求过程体 这个类的实现
        return 新层忆义中衍求过程体(形参序列, 过程体, 忆)
    elif 表达式[0] == '非开发者模式':
        命令表达式序列 = 表达式[1:]
        for 命令表达式 in 命令表达式序列:
            执行非开发者模式语句(命令表达式)
    #播放音乐彩蛋
    elif len(表达式) == 1 and 表达式[0] == '送别':
        os.system('音乐\送别.mp3')
    elif len(表达式) == 1 and 表达式[0] == '永远同在':
        os.system('音乐\永远同在.mp3')
    else:
        #其它情况对形如(+ 1 2)的式子进行求值操作
        执行操作 = 衍(表达式[0], 忆)
        参数序列 = [衍(参数, 忆) for 参数 in 表达式[1:]]
        return 执行操作(*参数序列)

def 解析(句读后文件):
    if isinstance(句读后文件, str): 句读后文件 = 文件句读(StringIO.StringIO(句读后文件))
    return 训诂(逐句读(句读后文件))

def 检验(表达式, 条件, 报错信息="语句长度不对"):
    if not 条件: raise SyntaxError(to_String(表达式)+':'+报错信息)

def 训诂(表达式):
    检验(表达式, 表达式!=[])
    if not isinstance(表达式, 序列):
        return 表达式
    elif 表达式[0] is 保留字引:
        检验(表达式, len(表达式)==2)
        return 表达式
    elif 表达式[0] is 保留字如果:
        if len(表达式)==3: 表达式 = 表达式 + [None]    #【如果 条件 执行操作】 => 【如果 条件 执行操作 None】
        检验(表达式, len(表达式)==4)
        return [训诂(表达项) for 表达项 in 表达式]
    elif 表达式[0] is 保留字赋:
        检验(表达式, len(表达式)==3)
        变元 = 表达式[1]
        检验(表达式, isinstance(变元, 符号), "只能赋值一个符号！")
        return [保留字赋, 变元, 训诂(表达式[2])]
    elif 表达式[0] is 保留字定义:
        # print("到这里了")
        检验(表达式, len(表达式) >= 3)
        保留字_定义, 被定义项, 所给定义 = 表达式[0], 表达式[1], 表达式[2:] 
        if isinstance(被定义项, 序列) and 被定义项:     #   【定义 【过程名 参数序列】 过程体】
            过程名, 参数序列 = 被定义项[0], 被定义项[1:] # =>【定义 过程名【道【参数序列】 过程体】】    
            return 训诂([保留字定义, 过程名, [保留字道, 参数序列] + 所给定义])
        else:
            检验(表达式, len(表达式)==3)
            检验(表达式, isinstance(被定义项, 符号), "只能定义一个符号！")
            实际定义 = 训诂(表达式[2])
            return [保留字定义, 被定义项, 实际定义]
    elif 表达式[0] is 保留字开始:
        if len(表达式) == 1: return None    # 【开始】 => None
        else: return [训诂(表达项) for 表达项 in 表达式]
    elif 表达式[0] is 保留字道:
        检验(表达式, len(表达式)>=3)
        参数序列, 过程体 = 表达式[1], 表达式[2:]
        检验(表达式, (isinstance(参数序列, 序列) and all(isinstance(参数, 符号) for 参数 in 参数序列)) or isinstance(参数序列, 符号), "非法道参数声明")
        实际过程体 = 过程体[0] if len(过程体) == 1 else [保留字开始] + 过程体
        return [保留字道, 参数序列, 训诂(实际过程体)]
    elif isinstance(表达式[0], 符号) and 表达式[0] in 宏忆义:
        return 训诂(宏忆义[表达式[0]](*表达式[1:]))  
    else:
        return [训诂(表达项) for 表达项 in 表达式]

保留字宇对, 保留字令 = map(定为符号,"宇对 令".split())

def 令(*语句项):
    语句项 = 序列(语句项)
    表达式 = 宇对(保留字令, 语句项)
    检验(表达式, len(语句项)>1)
    符义对序列, 过程体 = 语句项[0], 语句项[1:]
    检验(表达式, all(isinstance(符义对, 序列) and len(符义对)==2 and isinstance(符义对[0], 符号) for 符义对 in 符义对序列), "语句格式存在问题，符号与定义可能未一一对应")
    符序列, 义序列 = zip(*符义对序列)
    return [[保留字道, 序列(符序列)] + [训诂(过程语句项) for 过程语句项 in 过程体]] + [训诂(义) for 义 in 义序列]

宏忆义 = {保留字令:令}

def 终端交互(prompt='絮梦.py >>> ', 句读后文件=文件句读(sys.stdin), 输出内容=sys.stdout):
    while True:
        try:
            if prompt: sys.stderr.write(prompt)
            表达式 = 解析(句读后文件)
            if 表达式 is 程序终止: return
            结果 = 衍(表达式)
            if 结果 is not None and 输出内容: print >> 输出内容, 转絮梦表达式(结果)
        except Exception as 错误:
            print('%s: %s' % (type(错误).__name__, 错误))

def 运行():
    欲运行文件= input("希望运行的文件的绝对路径：")
    加载(欲运行文件)

加载(绝对路径)
# 加载('E:\\scheme\\Catkins_Dream\\Catkins_Dream\\测试开发者模式语句\\print1')

 
