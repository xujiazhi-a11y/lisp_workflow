import sys
import io
import os
#下面这一句是通知浏览器控制台用utf-8编码
# sys.stdout = io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8')
# my_name = sys.argv[1]

# for n, a in enumerate(sys.argv):
#     print('arg {} has value {} endOfArg'.format(n, a))

# #os.system(str(my_name))
# print("Hello and welcome " + str(my_name) + "!")

def hello(contents):
    if contents:
        print(contents)

# hello(my_name)
