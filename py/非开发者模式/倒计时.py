import time
import sys

def 倒计时(秒数):
    for 剩余秒数 in range(秒数, 0, -1):
        sys.stdout.write("\r")
        sys.stdout.write("{:2d}".format(剩余秒数))
        sys.stdout.flush()
        time.sleep(1) 
    sys.stdout.flush()
    sys.stdout.write("\n")



