import io
import os
import sys
from hello import hello
#下面这一句是通知浏览器控制台用utf-8编码
if sys.stdout:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8')
contents = sys.argv[1]

# for n, a in enumerate(sys.argv):
#     print('arg {} has value {} endOfArg'.format(n, a))
# for n, a in enumerate(sys.argv):
#     print('arg {} has value {} endOfArg'.format(n, a))

#os.system(str(my_name))
# def hello(contents):
#     if contents:
#         print(contents)
hello(contents)
