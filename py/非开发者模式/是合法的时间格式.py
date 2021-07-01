def 是合法的时间格式(字符串):
    合法 = False
    时分秒和毫秒 = 字符串.rsplit( ".", 1 )
    时分秒 = 时分秒和毫秒[0]
    时分秒 = 时分秒.replace('：', ':')
    时分秒列表 = 时分秒.split(':')
    if any(时或分或秒.isdigit() == False for 时或分或秒 in 时分秒列表):
        raise TypeError('输入的时间中时或分或秒上有非数字元素：%s' % 字符串)      
    elif all(int(时或分或秒) >= 0 and int(时或分或秒) < 60 for 时或分或秒 in 时分秒列表):
        合法 = True 
    if len(时分秒和毫秒) == 2: 
        毫秒 = 时分秒和毫秒[1]  
        if 毫秒.isdigit() == False:
            合法 = False
    return 合法

# print(是合法的时间格式("59:00.163"))
