from .包不存在 import 包不存在

def 执行快捷键指令并给出温馨提示(快捷键, 温馨提示):
    if(包不存在('keyboard')):
        os.system('pip install -i https://pypi.tuna.tsinghua.edu.cn/simple keyboard')
    exec('import keyboard')
    print(温馨提示)
    exec('keyboard.press_and_release(' + '\"' + 快捷键 + '\"' + ')')
