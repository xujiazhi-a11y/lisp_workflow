import os

def 将ffmpeg注入临时环境变量():
    当前目录 = os.getcwd()
    ffmpeg中bin路径 = 当前目录 + '\\ffmpeg' + '\\bin'
    os.environ['PATH'] += ffmpeg中bin路径 

