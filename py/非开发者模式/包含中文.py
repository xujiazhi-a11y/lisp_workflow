def 包含中文(检查字符串):
    """
    判断字符串中是否包含中文
    :param check_str: {str} 需要检测的字符串
    :return: {bool} 包含返回True， 不包含返回False
    """
    for 字符 in 检查字符串:
        if u'\u4e00' <= 字符 <= u'\u9fff':
            return True
    return False

