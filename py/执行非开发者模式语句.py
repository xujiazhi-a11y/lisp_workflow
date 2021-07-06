import time
import webbrowser
import re
import os
import operator
import psutil
import itertools
import math
import subprocess
# import ffmpeg
import sys
import pypinyin
from 非开发者模式 .包不存在 import 包不存在
from 非开发者模式 .包含中文 import 包含中文
from 非开发者模式 .倒计时 import 倒计时
from 非开发者模式 .是合法的时间格式 import 是合法的时间格式
from 非开发者模式 .将ffmpeg注入临时环境变量 import 将ffmpeg注入临时环境变量
from 非开发者模式 .执行快捷键指令并给出温馨提示 import 执行快捷键指令并给出温馨提示
from 非开发者模式 .字符串中最末出现的文件大小对应的字节数 import 字符串中最末出现的文件大小对应的字节数
from 非开发者模式 .ffprobe获取采样率 import ffprobe获取采样率
from 非开发者模式 .百度语音听写 .听写 import 返回说出的内容, 录音
from 非开发者模式 .路径字典 import b站内容名字对应路径字典, 爱奇艺内容名字对应路径字典, 落霞小说鲲弩小说路径字典, b站优质课程对应路径字典

def 各种大小写组合(字符串):
    组合列表 =list(map(''.join, itertools.product(*((字母.upper(), 字母.lower()) for 字母 in 字符串))))
    return 组合列表

def 字符串中的整数(字符串):
    return int(''.join(元素 for 元素 in 字符串 if 元素.isdigit()))

def 使用用户友好的文件大小单位(bytes, units=[' bytes','KB','MB','GB','TB', 'PB', 'EB']):
    """ Returns a human readable string representation of bytes """
    return str(bytes) + units[0] if bytes < 1024 else 使用用户友好的文件大小单位(bytes>>10, units[1:])

def 文件大小(文件路径):
    文件字节数 = os.path.getsize(文件路径) 
    return 使用用户友好的文件大小单位(文件字节数)

def 文件名(文件):
    return 文件.rsplit("\\",1)[1]

def 不带后缀文件名(文件):
    return (文件.rsplit("\\",1)[1]).rsplit(".", 1)[0]

def 后缀名(文件):
    return 文件.rsplit(".",1)[1]

def 所处路径(文件):
    return 文件.rsplit("\\",1)[0]

def 所处路径相同(文件路径列表):
    return(all(所处路径(文件路径) == 所处路径(文件路径列表[0]) for 文件路径 in 文件路径列表))

def 后缀相同(文件列表):
    return(all(后缀名(文件) == 后缀名(文件列表[0]) for 文件 in 文件列表))

def 拼音(汉字字符串):
    无分隔拼音=pypinyin.slug(汉字字符串,separator="")
    return 无分隔拼音

def 根据内容名字打开网页(内容名字,字典):
    for key in 字典.keys():
        if 内容名字 in key:
            webbrowser.open(字典[key])

def 执行下载(视频网址):
    os.system('pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --upgrade youtube-dl')
    time.sleep(0.1)
    下载指令 = 'youtube-dl' + ' ' + 视频网址
    os.system(下载指令) 

class ffmpeg格式转化:
    def 格式转化(self, 传入文件路径, 转出文件路径):
        print("格式转化")
        stream = ffmpeg.input(传入文件路径)
        stream = ffmpeg.output(stream, 转出文件路径)
        ffmpeg.run(stream)

def 建文件夹(文件夹名):
	存在文件夹名 = os.path.exists(文件夹名)
	if not 存在文件夹名:                   #判断是否存在文件夹如果不存在则创建为文件夹
		os.makedirs(文件夹名)            #makedirs 创建文件时如果路径不存在会创建这个路径

def 更新pip():
    os.system('pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --upgrade pip')

def 执行非开发者模式语句(指令表达式):
    if '文件大小' in 指令表达式[0]:
        #可以设计成可输入一串文件，看似健壮性会高些？但真的有人会这么干吗？
        多文件路径列表 = 指令表达式[1:]
        for 文件 in 多文件路径列表:
            print(文件大小(文件))
    elif ('中国' in 指令表达式[0] or '中华' in 指令表达式) and '传统' in 指令表达式[0] and '颜色' in 指令表达式[0]:
        webbrowser.open('https://github.com/yourtion/30dayMakeOS')
    elif '壁纸' in 指令表达式[0] and '动态' not in 指令表达式[0]:
        webbrowser.open('http://lab.mkblog.cn/wallpaper/')
    elif '桌面背景' in 指令表达式[0] and '动态' not in 指令表达式[0]:
        webbrowser.open('http://lab.mkblog.cn/wallpaper/') 
    elif '壁纸' in 指令表达式[0] and '动态' in 指令表达式[0]:
        webbrowser.open('https://gitee.com/exq80730/lively?_from=gitee_search')
    elif '脑图' in 指令表达式[0] or '导图' in 指令表达式[0]:
        webbrowser.open('https://gitee.com/mirrors/desktopnaotu?_from=gitee_search')
    elif ('查找' in 指令表达式[0] and '游戏' in 指令表达式[0]) or ('整理' in 指令表达式[0] and '游戏' in 指令表达式[0]):
        webbrowser.open('https://www.steamgriddb.com/manager')
    elif '打谱' in 指令表达式[0] or '制谱' in 指令表达式[0] or ('制作' in 指令表达式[0] and '谱子' in 指令表达式[0]):
        webbrowser.open('https://musescore.org/zh-hans')
    elif 指令表达式[0] == '播放' and  len(指令表达式) == 2:
        内容名字 = 指令表达式[1]
        根据内容名字打开网页(内容名字,b站内容名字对应路径字典)
        根据内容名字打开网页(内容名字,爱奇艺内容名字对应路径字典)
    elif 指令表达式[0] == '学习' and len(指令表达式) == 2:
        内容名字 = 指令表达式[1]
        根据内容名字打开网页(内容名字,b站优质课程对应路径字典)
    elif 指令表达式[0] == '阅读' and len(指令表达式) == 2:
        书名 = 指令表达式[1]
        # https://www.kunnu.com/santi/#santi-1
        对应鲲弩网址 = 'https://www.kunnu.com/' + 拼音(书名)
        webbrowser.open(对应鲲弩网址)
    elif '播放' in 指令表达式[0] and '歌' in 指令表达式[0] and  len(指令表达式) == 2:
        歌名 = 指令表达式[1]
        对应MyFreeMp3网址 = 'http://tool.liumingye.cn/music/?page=audioPage&type=migu&name=' + 歌名
        webbrowser.open(对应MyFreeMp3网址)
    elif 指令表达式[0] == '下载' and len(指令表达式) == 2:
        更新pip()
        视频下载链接 = 指令表达式[1]
        所有盘符 = psutil.disk_partitions()
        本机盘符列表 = []
        可能盘符倒序列表 = ['G:\\','F:\\','E:\\','D:\\','C:\\']
        当前盘 = ''
        for 盘符信息 in 所有盘符:
            本机盘符列表.append(str(盘符信息))
        本机盘符列表.reverse()
        尾盘 = ''
        def 获取尾盘(本机盘符列表,可能盘符倒序列表):
            for 盘符信息 in 本机盘符列表:
                for 可能盘符 in 可能盘符倒序列表:
                    if 可能盘符 in 盘符信息:
                        尾盘 = 可能盘符
                        return(尾盘)
        尾盘 = 获取尾盘(本机盘符列表,可能盘符倒序列表)
        欲往之盘 = 尾盘.rsplit('\\')[0]
        os.chdir(欲往之盘)
        建文件夹("志语下载的视频")
        os.chdir('志语下载的视频')
        执行下载(视频下载链接)
        print('视频已下载至' + 欲往之盘.replace(':', '') + '盘下的“志语下载的视频”文件夹')
        # 执行下载(视频下载链接)
        #   
        # except RuntimeError('下载失败')
    elif '支持' in 指令表达式[0] and '格式' in 指令表达式[0]:
        将ffmpeg注入临时环境变量()
        os.system('ffmpeg -formats')
    # 用ffmpeg执行格式转化
    elif '转为' in 指令表达式[0]:
        可编码或可编解码格式列表 = ['3g2', '3gp', 'a64', 'ac3', 'adts', 'adx', 'aiff', 'alaw', 'alp', 'amr', 'amv', 
                'apm', 'apng', 'aptx', 'aptx_hd', 'argo_asf', 'asf', 'asf_stream', 'ass', 'ast', 'au', 'avi', 'avm2', 
                'avs2', 'bit', 'caf', 'cavsvideo', 'codec2', 'codec2raw', 'crc', 'dash', 'data', 'daud', 'dirac', 'dnxhd', 
                'dts', 'dv', 'dvd', 'eac3', 'f32be', 'f32le', 'f4v', 'f64be', 'f64le', 'ffmetadata', 'fifo', 'fifo_test', 
                'film_cpk', 'filmstrip', 'fits', 'flac', 'flv', 'framecrc', 'framehash', 'framemd5', 'g722', 'g723_1', 
                'g726', 'g726le', 'gif', 'gsm', 'gxf', 'h261', 'h263', 'h264', 'hash', 'hds', 'hevc', 'hls', 'ico', 'ilbc', 
                'image2', 'image2pipe', 'ipod', 'ircam', 'ismv', 'ivf', 'jacosub', 'kvag', 'latm', 'lrc', 'm4v', 'matroska', 
                'md5', 'microdvd', 'mjpeg', 'mkvtimestamp_v2', 'mlp', 'mmf', 'mov', 'mp2', 'mp3', 'mp4', 'mpeg', 'mpeg1video', 
                'mpeg2video', 'mpegts', 'mpjpeg', 'mulaw', 'mxf', 'mxf_d10', 'mxf_opatom', 'null', 'nut', 'oga', 'ogg', 'ogv', 
                'oma', 'opus', 'psp', 'rawvideo', 'rm', 'roq', 'rso', 'rtp', 'rtp_mpegts', 'rtsp', 's16be', 's16le', 's24be', 
                's24le', 's32be', 's32le', 's8', 'sap', 'sbc', 'scc', 'sdl,sdl2', 'segment', 'singlejpeg', 'smjpeg', 
                'smoothstreaming', 'sox', 'spdif', 'spx', 'srt', 'stream_segment,ssegment', 'streamhash', 'sup', 'svcd', 
                'swf', 'tee', 'truehd', 'tta', 'u16be', 'u16le', 'u24be', 'u24le', 'u32be', 'u32le', 'u8', 'uncodedframecrc', 
                'vc1', 'vc1test', 'vcd', 'vidc', 'vob', 'voc', 'w64', 'wav', 'webm', 'webm_chunk', 'webm_dash_manifest', 'webp', 
                'webvtt', 'wtv', 'wv', 'yuv4mpegpipe']
        if len(指令表达式) == 2:
            (格式转换请求,欲转文件绝对路径) = 指令表达式
            if 包含中文(欲转文件绝对路径):
                raise ValueError('抱歉，文件格式转化时路径中不能包含中文，你可以把文件的名字、它所在的一系列文件夹的名字先临时改成不含中文的，回头再改回来，你这里所给的文件的路径是：%s' % 欲转文件绝对路径)
            elif ' ' in 欲转文件绝对路径:
                raise ValueError('抱歉，要转化的文件的路径中不能有空格，改一下就好啦，试一试？你给到的文件的路径为：%s，把这里面的文件夹、文件名含空格的去掉即可' % 欲转文件绝对路径)
            else:
                将ffmpeg注入临时环境变量()
                #比如指令“将MP3格式文件转为WAV格式”，下面这句判断，判断的是从右往左出现的第一个“wav”
                # 音频格式 = ('pcm','wav','aiff','mp3','aac','wma','flac','alac','wma')              
                for 可编码或可编解码格式 in 可编码或可编解码格式列表:
                    #这里rfind，从右找到的第一个说格式是什么的子字符串应该是用户想表达的要转换成的字符串，类似“转为MP3格式”或“由avi格式转为MP3格式”
                    if 格式转换请求.rfind(可编码或可编解码格式) != -1 or 格式转换请求.rfind(可编码或可编解码格式.upper()) != -1:
                        #替换之前的后缀，生成新文件路径
                        转后文件绝对路径 = 欲转文件绝对路径.rsplit( ".", 1 )[0] + '.' +  可编码或可编解码格式
                        转换指令 = 'ffmpeg' + ' ' + '-i' + ' ' +  欲转文件绝对路径 + ' ' + 转后文件绝对路径
                        os.system(转换指令)
                        print("转换完格式的文件在原文件所在的文件夹中（原路径下），转完格式的文件和原文件它俩在一块呐，去看看吧！")
        elif len(指令表达式) == 3:
            (格式转换请求, 欲转文件绝对路径, 新文件绝对路径) = 指令表达式
            if 包含中文(欲转文件绝对路径):
                raise ValueError('抱歉，文件格式转化时路径中不能包含中文，你可以把文件的名字、它所在的一系列文件夹的名字先临时改成不含中文的，回头再改回来，你这里所给的文件的路径是：%s' % 欲转文件绝对路径)
            # 下面这一句根本判断不出来的，一旦有空格，会直接报参数个数不对
            # elif ' ' in 欲转文件绝对路径:
            #     raise ValueError('抱歉，要转化的文件的路径中不能有空格，改一下就好啦，试一试？你给到的文件的路径为：%s，把这里面的文件夹、文件名含空格的去掉即可' % 欲转文件绝对路径)
            else:
                将ffmpeg注入临时环境变量()             
                转换指令 = 'ffmpeg' + ' ' + '-i' + ' ' +  欲转文件绝对路径 + ' ' + 新文件绝对路径
                os.system(转换指令)
                print("转换完格式的文件在原文件所在的文件夹中（原路径下），转完格式的文件和原文件它俩在一块呐，去看看吧！")
    elif '剪切' in 指令表达式[0] and len(指令表达式) == 4:
        将ffmpeg注入临时环境变量()
        起始时间 = 指令表达式[1]
        终止时间 = 指令表达式[2]
        欲剪文件路径 = 指令表达式[3]
        if 是合法的时间格式(起始时间) and 是合法的时间格式(终止时间):
            输出文件路径 = 欲剪文件路径.rsplit(".", 1)[0] + 'CUT' + '.' + 欲剪文件路径.rsplit(".", 1)[1]
            剪切指令 = 'ffmpeg' + ' ' + '-ss' + ' ' + 起始时间 + ' ' + '-to' + ' ' + 终止时间 + ' ' + '-i' + ' ' + 欲剪文件路径 + ' ' + '-c' + ' ' + 'copy' + ' ' + 输出文件路径
            os.system(剪切指令)
            print("剪过的音视频文件在原文件所在的文件夹里（原路径下），在文件名结尾加了一个CUT")
    # elif '合并' in 指令表达式[0]:
    #     将ffmpeg注入临时环境变量()
    #     音视频文件列表 = 指令表达式[1:]
    #     if 后缀相同(音视频文件列表) == False:
    #         raise TypeError('你给的文件类型不都相同（后缀没有全一样），可能只能合并同类的文件啊~，本软件支持类型转换，可以先把它们转为同一类型的文件后再合并')
    #     if 所处路径相同(音视频文件列表):
    #         os.chdir(所处路径(音视频文件列表[0]))
    #     elif 所处路径相同(音视频文件列表) == False:
    #         raise ValueError('你给的媒体文件没在同一文件夹下，需要挪到同一文件夹下。。。这样你也好整理不是吗？')
    #     with open(f"音视频顺序文件.txt", "wb") as f:
    #         for 每条音视频 in 指令表达式[1:]:
    #             f.write(('file' + ' ').encode())
    #             f.write((文件名(每条音视频) + '\n').encode())  #这里需要调一个encode方法，否则会报类型错
    #     志语合并的媒体文件名 = '志语合并的媒体文件1'
    #     该目录下的文件列表 = os.listdir(所处路径(音视频文件列表[0]))
    #     for 文件 in 该目录下的文件列表:
    #         if '志语合并的媒体文件10' in 文件:
    #             raise ValueError('当前文件夹下合并后未改名的文件太多啦，已经不方便整理了。')
    #         for 序号 in range(9, 0, -1):
    #             if '志语合并的媒体文件' + str(序号) in 文件:
    #                 志语合并的媒体文件名 = '志语合并的媒体文件' + str(序号 + 1)
    #                 break
    #     合并指令 = 'ffmpeg' + ' ' + '-f' + ' ' + 'concat' + ' ' + '-safe' + ' ' + '0' + ' ' + '-i' + ' ' + '音视频顺序文件.txt' + ' ' + '-c' + ' ' + 'copy' + ' ' + 志语合并的媒体文件名 + '.' + 后缀名(音视频文件列表[0]) 
    #     subprocess.Popen(合并指令,shell = True).wait()
    #     # os.system(合并指令)
    #     time.sleep(0.1)
    #     print('合好的音视频文件在它们的所共同在的文件夹中，名字是'+'“'+志语合并的媒体文件名+'.'+后缀名(音视频文件列表[0])+'”'+':')
    #     # # 都处理完以后，返回本路径
    #     # os.chdir(os.getcwd())  #这样写对吗？
    elif '合并' in 指令表达式[0]:
        将ffmpeg注入临时环境变量()
        音视频文件列表 = 指令表达式[1:]
        # 如果采样率相同则可以使用concat合并（只是采样率相同就可以吗？）
        if all(ffprobe获取采样率(音视频文件)  == ffprobe获取采样率(音视频文件列表[0]) for 音视频文件 in 音视频文件列表):
            print('采样率相同')
            if 后缀相同(音视频文件列表) == False:
                raise TypeError('你给的文件类型不都相同（后缀没有全一样），可能只能合并同类的文件啊~，本软件支持类型转换，可以先把它们转为同一类型的文件后再合并')
            if 所处路径相同(音视频文件列表):
                os.chdir(所处路径(音视频文件列表[0]))
            elif 所处路径相同(音视频文件列表) == False:
                raise ValueError('你给的媒体文件没在同一文件夹下，需要挪到同一文件夹下。。。这样你也好整理不是吗？')
            with open(f"音视频顺序文件.txt", "wb") as f:
                for 每条音视频 in 指令表达式[1:]:
                    f.write(('file' + ' ').encode())
                    f.write((文件名(每条音视频) + '\n').encode())  #这里需要调一个encode方法，否则会报类型错
            志语合并的媒体文件名 = 'ZhiYu_media_HeBing1'
            该目录下的文件列表 = os.listdir(所处路径(音视频文件列表[0]))
            for 文件 in 该目录下的文件列表:
                if 'ZhiYu_media_HeBing10' in 文件:
                    raise ValueError('当前文件夹下合并后未改名的文件太多啦，已经不方便整理了。')
                for 序号 in range(9, 0, -1):
                    if 'ZhiYu_media_HeBing' + str(序号) in 文件:
                        志语合并的媒体文件名 = 'ZhiYu_media_HeBing' + str(序号 + 1)
                        break
            合并指令 = 'ffmpeg' + ' ' + '-f' + ' ' + 'concat' + ' ' + '-safe' + ' ' + '0' + ' ' + '-i' + ' ' + '音视频顺序文件.txt' + ' ' + '-c' + ' ' + 'copy' + ' ' + 志语合并的媒体文件名 + '.' + 后缀名(音视频文件列表[0]) 
            subprocess.Popen(合并指令,shell = True).wait()
            print('合好的音视频文件在它们的所共同在的文件夹中，名字是'+'“'+志语合并的媒体文件名+'.'+后缀名(音视频文件列表[0])+'”'+':')
        # 如果任何文件的采样率不同于其它的，且文件后缀都是MP4则使用如下方法来合并
        elif any(ffprobe获取采样率(音视频文件)  != ffprobe获取采样率(音视频文件列表[0]) for 音视频文件 in 音视频文件列表)\
            and all(后缀名(音视频文件) == 'mp4' for 音视频文件 in 音视频文件列表):
            合并指令 = 'ffmpeg -i \"concat:' 
            os.chdir(所处路径(音视频文件列表[0]))
            if not os.path.exists('./ZhiYu_ts'):
                os.mkdir('ZhiYu_ts')
            os.chdir('ZhiYu_ts')
            for 音视频文件 in 音视频文件列表:
                ts文件序号 = 0
                ts文件 = 不带后缀文件名(音视频文件) + str(ts文件序号) +  '.ts'
                while os.path.exists('./' + ts文件):     
                    ts文件序号 = ts文件序号 + 1
                    ts文件 = 不带后缀文件名(音视频文件) + str(ts文件序号) +  '.ts'
                转为ts指令 = 'ffmpeg' + ' ' + '-i' + ' ' + 音视频文件 + ' ' + '-c' + ' ' + 'copy' + ' ' + '-bsf:v' + ' ' + 'h264_mp4toannexb' + ' ' + '-f' + ' ' + 'mpegts' + ' ' + ts文件
                subprocess.Popen(转为ts指令, shell = True)
                合并指令 = 合并指令 + ts文件 + '|'
            # os.chdir(os.pardir())
            os.chdir(所处路径(音视频文件列表[0]))
            合并文件序号 = 0
            志语合并的文件名 = 'ZhiYu_MP4_HeBing' + str(合并文件序号) + '.mp4'
            while os.path.exists("./" + 志语合并的文件名):
                合并文件序号 = 合并文件序号 + 1
                志语合并的文件名 = 'ZhiYu_MP4_HeBing' + str(合并文件序号) + '.mp4' 
            合并指令 = 合并指令 + '\" -c copy -bsf:a aac_adtstoasc -movflags +faststart ' + 所处路径(音视频文件列表[0]) + '\\' + 志语合并的文件名
            subprocess.Popen(合并指令, shell = True).wait()
        # 都处理完以后，返回本路径
        os.chdir(os.getcwd())  #这样写对吗？
    elif "分辨率" in 指令表达式[0] or "画质" in 指令表达式[0] or '降为' in 指令表达式[0]:
        将ffmpeg注入临时环境变量()
        原视频路径 = 指令表达式[1]  
        os.chdir(所处路径(原视频路径))
        常用分辨率字典 = {'4K':'3840:2160','2K':'2560:1440','1080P':'1920:1080','720P':'1280:720','480P':'640:480','360P':'480:360' }
        键入了合法的转后分辨率 = False
        for 分辨率 in 常用分辨率字典.keys():
            if 指令表达式[0].rfind(分辨率) != -1 or 指令表达式[0].rfind(分辨率) != -1:
                键入了合法的转后分辨率 = True
                显示分辨率 = 常用分辨率字典[分辨率]
                新视频路径 = 不带后缀文件名(原视频路径) + 分辨率 + '.' + 后缀名(原视频路径)
            #这里是不是应该加个用户输入的分辨率没在字典中的情况？
        if 键入了合法的转后分辨率:  
            降低分辨率命令 = 'ffmpeg' + ' ' + '-i' + ' ' + 原视频路径 + ' ' + '-vf' + ' ' + 'scale=' + 显示分辨率 + ' ' + 新视频路径
            print(降低分辨率命令)
            os.system(降低分辨率命令)
            os.chdir(os.getcwd()) 
        # 下面是针对降为固定大小，使用将长宽线数均降低
        else:
            要求的文件字节量 =  字符串中最末出现的文件大小对应的字节数(指令表达式[0])
            print('要求的文件字节量')
            print(要求的文件字节量)
            原文件字节量 =  os.path.getsize(原视频路径)
            print('原文件字节量:')
            print(原文件字节量)
            # 实测iw/3,ih/3，视频大小缩小倍数约为3倍（而非想象中的9倍），iw/2，ih/2，视频大小缩小倍数约为2倍，而非想象中的4倍
            缩小倍数 = 原文件字节量 / 要求的文件字节量
            print(缩小倍数)
            #测试一下写死的命令，看会缩小多少
            新视频路径 = 不带后缀文件名(原视频路径) + '_s' + '.' + 后缀名(原视频路径)
            压缩大小命令 = 'ffmpeg' + ' ' + '-i' + ' ' + 文件名(原视频路径) + ' ' + '-vf' + ' ' + '\"' + 'scale=trunc(iw/(2*' + str(缩小倍数) + '))*2:trunc(ih/(2*' + str(缩小倍数) + '))*2' + '\"' + ' ' + 新视频路径
            print(压缩大小命令)
            os.system(压缩大小命令)
    elif "百度" in 指令表达式[0] and "语音" in 指令表达式[0]:
        语音识别代码 = 指令表达式[1:]
        # 先从代码块中找寻appID等三个值的定义，【appid appid】这样来定义三个所需值
        # APP_ID, API_KEY, SECRET_KEY
        for 语句 in 语音识别代码:
            if any(大小写组合 in 语句[0] for 大小写组合 in 各种大小写组合("appID")):
                APP_ID = str(语句[1])
            elif any(大小写组合 in 语句[0] for 大小写组合 in 各种大小写组合("APP_ID")):
                APP_ID = str(语句[1])
            elif any(大小写组合 in 语句[0] for 大小写组合 in 各种大小写组合("apiKEY")):
                API_KEY = str(语句[1])
            elif any(大小写组合 in 语句[0] for 大小写组合 in 各种大小写组合("API_KEY")):
                API_KEY = str(语句[1])
            elif any(大小写组合 in 语句[0] for 大小写组合 in 各种大小写组合("secretKEY")):
                SECRET_KEY = str(语句[1])
            elif any(大小写组合 in 语句[0] for 大小写组合 in 各种大小写组合("SECRET_KEY")):
                SECRET_KEY = str(语句[1])
        # print(语音识别代码)
        # 下面这一句起语音识别
        # 为啥没有直接显示开始录音？我现在把录音拆出来试试
        # 说出的内容 = 返回说出的内容('24449406', 'pIFYzT039XeeBynO5pyleO1Z', 'pxaRaOYVhr26iSa4aiTYGCrsF9EH4WrT') 
        说出的内容  = 返回说出的内容(APP_ID, API_KEY, SECRET_KEY)
        # 下面一句写死一个说出的内容以测试
        # 说出的内容 = "播放你的名字"
        for 语音识别语句 in 语音识别代码:
            # print(语音识别语句)
            if "如果" in 语音识别语句[0]:
                条件 = 语音识别语句[1]
                执行命令 = 语音识别语句[2]
                if "含" in 条件[0]:
                    关键字列表 = 条件[1:]
                    if all(关键字 in 说出的内容 for 关键字 in 关键字列表):
                        print(执行命令)
                        执行非开发者模式语句(执行命令)
                    # print(关键字列表)

    # ———————————————————————————————————windows快捷键—————————————————————————————————————————-
    elif ('录屏' in 指令表达式[0]) or ('屏幕' in 指令表达式[0] and '录制' in 指令表达式[0]) or ('录课' in 指令表达式[0]):
        执行快捷键指令并给出温馨提示("alt+esc","")
        执行快捷键指令并给出温馨提示("windows+alt+g", '为你打开windows自带的录屏工具，开启快捷键为“win+g”，如日后常有需要，可以记一下喽~') 
    elif '截屏' in 指令表达式[0] or '截图' in 指令表达式[0]:
        执行快捷键指令并给出温馨提示("alt+esc","")
        执行快捷键指令并给出温馨提示("windows+shift+s", '为你打开windows自带的截图工具，开启快捷键为“Win+Shift+S”，如日后常有需要，可以记一下喽~')
    elif ('剪贴版' in 指令表达式[0] and ('记录' in 指令表达式[0] or '历史' in 指令表达式[0]))\
        or ('复制' in 指令表达式[0] and ('记录' in 指令表达式[0] or '历史' in 指令表达式[0])) :
        执行快捷键指令并给出温馨提示("windows+v", '为你打开windows自带的剪贴版记录工具，开启快捷键为“Win+V”，如日后常有需要，可以记一下喽~')
    elif '我的电脑' in 指令表达式[0] or '资源管理器' in 指令表达式[0]:
        执行快捷键指令并给出温馨提示("windows+e", 'windows系统打开“我的电脑”的快捷键是“Win+E”，如日后常有需要，可以记一下喽~')
    elif '锁屏' in 指令表达式[0]:
        执行快捷键指令并给出温馨提示("windows+l", 'windows系统锁屏的快捷键是“Win+L”，如日后常有需要，可以记一下喽~')
    elif '撤销' in 指令表达式[0]:
        执行快捷键指令并给出温馨提示("ctrl+z", 'windows系统撤销的快捷键是“ctrl+z”，如日后常有需要，可以记一下喽~')
    elif "取消" in 指令表达式[0] and "撤销" in 指令表达式[0]:
        执行快捷键指令并给出温馨提示("ctrl+y", 'windows系统取消撤销的快捷键是“ctrl+y”，如日后常有需要，可以记一下喽~')
    elif "白版" in 指令表达式[0]:
        执行快捷键指令并给出温馨提示("windows+w", "windows系统打开白版的快捷键是“windows+w，如日后常有需要，可以记一下喽")

    #——————————————————————————————————————————qq快捷键————————————————————————————————————————————————-———
    elif '识图' in 指令表达式[0] or ('识别' in 指令表达式[0] and '文字' in 指令表达式[0]):
        执行快捷键指令并给出温馨提示("alt+esc","")
        执行快捷键指令并给出温馨提示("ctrl+alt+o", '如果有安装qq的话，windows系统下qq框选屏幕识图的快捷键是ctrl+alt+o，如日后常有需要，可以记一下喽~')
    elif '翻译' in 指令表达式[0]:
        执行快捷键指令并给出温馨提示("alt+esc","")
        执行快捷键指令并给出温馨提示("ctrl+alt+f", '如果有安装qq的话，windows系统下qq框选屏幕翻译的快捷键是ctrl+alt+f，如日后常有需要，可以记一下喽~')
    
          