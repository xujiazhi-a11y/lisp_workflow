def 包不存在(包名):
    exec('import importlib')
    exec('包路径 = importlib.util.find_spec(包名)')
    #下面是在stackOverflow上找到的一种返回exec语句中的变量的方法，如果直接访问exec语句中的变量是访问不到的
    不存在 = [0]
    exec('不存在[0] = 包路径 is None')
    return 不存在[0]
