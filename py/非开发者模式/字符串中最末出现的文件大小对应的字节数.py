import re
def 字符串中最末出现的文件大小对应的字节数(字符串):
    # test_string = '大小44.5MB\n12b\n6.5GB\n12pb'

    regex = re.compile(r'(\d+(?:\.\d+)?)\s*([kmgtp]?b)', re.IGNORECASE)

    order = ['b', 'kb', 'mb', 'gb', 'tb', 'pb']

    字节数列表 = []
    for value, unit in regex.findall(字符串):
        字节数列表.append(int(float(value) * (1024**order.index(unit.lower()))))
    
    return 字节数列表[len(字节数列表)-1]