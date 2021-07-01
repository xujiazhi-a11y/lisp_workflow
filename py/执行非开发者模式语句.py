import time
import webbrowser
import re
import os
import operator
import psutil
# import ffmpeg
import sys
from 非开发者模式 .包不存在 import 包不存在
from 非开发者模式 .包含中文 import 包含中文
from 非开发者模式 .倒计时 import 倒计时
from 非开发者模式 .是合法的时间格式 import 是合法的时间格式
from 非开发者模式 .将ffmpeg注入临时环境变量 import 将ffmpeg注入临时环境变量
from 非开发者模式 .执行快捷键指令并给出温馨提示 import 执行快捷键指令并给出温馨提示
from 非开发者模式 .百度语音听写 .听写 import 返回说出的内容, 录音
from 非开发者模式 .路径字典 import b站内容名字对应路径字典, 爱奇艺内容名字对应路径字典, 落霞小说鲲弩小说路径字典

def 文件名(文件):
    return 文件.rsplit("\\",1)[1]

def 后缀名(文件):
    return 文件.rsplit(".",1)[1]

def 所处路径(文件):
    return 文件.rsplit("\\",1)[0]

def 所处路径相同(文件路径列表):
    return(all(所处路径(文件路径) == 所处路径(文件路径列表[0]) for 文件路径 in 文件路径列表))

def 后缀相同(文件列表):
    return(all(后缀名(文件) == 后缀名(文件列表[0]) for 文件 in 文件列表))

def 根据内容名字打开网页(内容名字,字典):
    for key in 字典.keys():
        #print(key)
        if 内容名字 in key:
            #print(key)
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
    exec('pip install -i https://pypi.tuna.tsinghua.edu.cn/simple pip -U')

def 执行非开发者模式语句(指令表达式):
    if ('中国' in 指令表达式[0] or '中华' in 指令表达式) and '传统' in 指令表达式[0] and '颜色' in 指令表达式[0]:
        webbrowser.open('https://github.com/yourtion/30dayMakeOS') 
    elif (指令表达式[0] == '播放' or 指令表达式[0] == '阅读') and  len(指令表达式) == 2:
        内容名字 = 指令表达式[1]
        根据内容名字打开网页(内容名字,b站内容名字对应路径字典)
        根据内容名字打开网页(内容名字,爱奇艺内容名字对应路径字典)
        根据内容名字打开网页(内容名字,落霞小说鲲弩小说路径字典) 
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
        # print(type(尾盘))
        # print(os.getcwd())      
        # print(当前盘)
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
        (格式转换请求,欲转文件绝对路径) = 指令表达式
        if 包含中文(欲转文件绝对路径):
            raise ValueError('抱歉，文件格式转化时路径中不能包含中文，你可以把文件的名字、它所在的一系列文件夹的名字先临时改成不含中文的，回头再改回来，你这里所给的文件的路径是：%s' % 欲转文件绝对路径)
        elif ' ' in 欲转文件绝对路径:
            raise ValueError('抱歉，要转化的文件的路径中不能有空格，改一下就好啦，试一试？你给到的文件的路径为：%s，把这里面的文件夹、文件名含空格的去掉即可' % 欲转文件绝对路径)
        else:
            将ffmpeg注入临时环境变量()
            #比如指令“将MP3格式文件转为WAV格式”，下面这句判断，判断的是从右往左出现的第一个“wav”
            # 音频格式 = ('pcm','wav','aiff','mp3','aac','wma','flac','alac','wma')
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
            for 可编码或可编解码格式 in 可编码或可编解码格式列表:
                #这里rfind，从右找到的第一个说格式是什么的子字符串应该是用户想表达的要转换成的字符串，类似“转为MP3格式”或“由avi格式转为MP3格式”
                if 格式转换请求.rfind(可编码或可编解码格式) != -1 or 格式转换请求.rfind(可编码或可编解码格式.upper()) != -1:
                    #替换之前的后缀，生成新文件路径
                    转后文件绝对路径 = 欲转文件绝对路径.rsplit( ".", 1 )[0] + '.' +  可编码或可编解码格式
                    转换指令 = 'ffmpeg' + ' ' + '-i' + ' ' +  欲转文件绝对路径 + ' ' + 转后文件绝对路径
                    os.system(转换指令)
                    print("转换完格式的文件在原文件所在的文件夹中（原路径下），转完格式的文件和原文件它俩在一块呐，去看看吧！")
    # elif '新转' in 指令表达式[0]:
    #     (格式转换请求, 传入文件) = 指令表达式
    #     转格式 = ffmpeg格式转化()
    #     转格式.格式转化(r"F:\\test.mp3",r"F:\\test.wav")
    #     可编码或可编解码格式列表 = ['3g2', '3gp', 'a64', 'ac3', 'adts', 'adx', 'aiff', 'alaw', 'alp', 'amr', 'amv', 
    #         'apm', 'apng', 'aptx', 'aptx_hd', 'argo_asf', 'asf', 'asf_stream', 'ass', 'ast', 'au', 'avi', 'avm2', 
    #         'avs2', 'bit', 'caf', 'cavsvideo', 'codec2', 'codec2raw', 'crc', 'dash', 'data', 'daud', 'dirac', 'dnxhd', 
    #         'dts', 'dv', 'dvd', 'eac3', 'f32be', 'f32le', 'f4v', 'f64be', 'f64le', 'ffmetadata', 'fifo', 'fifo_test', 
    #         'film_cpk', 'filmstrip', 'fits', 'flac', 'flv', 'framecrc', 'framehash', 'framemd5', 'g722', 'g723_1', 
    #         'g726', 'g726le', 'gif', 'gsm', 'gxf', 'h261', 'h263', 'h264', 'hash', 'hds', 'hevc', 'hls', 'ico', 'ilbc', 
    #         'image2', 'image2pipe', 'ipod', 'ircam', 'ismv', 'ivf', 'jacosub', 'kvag', 'latm', 'lrc', 'm4v', 'matroska', 
    #         'md5', 'microdvd', 'mjpeg', 'mkvtimestamp_v2', 'mlp', 'mmf', 'mov', 'mp2', 'mp3', 'mp4', 'mpeg', 'mpeg1video', 
    #         'mpeg2video', 'mpegts', 'mpjpeg', 'mulaw', 'mxf', 'mxf_d10', 'mxf_opatom', 'null', 'nut', 'oga', 'ogg', 'ogv', 
    #         'oma', 'opus', 'psp', 'rawvideo', 'rm', 'roq', 'rso', 'rtp', 'rtp_mpegts', 'rtsp', 's16be', 's16le', 's24be', 
    #         's24le', 's32be', 's32le', 's8', 'sap', 'sbc', 'scc', 'sdl,sdl2', 'segment', 'singlejpeg', 'smjpeg', 
    #         'smoothstreaming', 'sox', 'spdif', 'spx', 'srt', 'stream_segment,ssegment', 'streamhash', 'sup', 'svcd', 
    #         'swf', 'tee', 'truehd', 'tta', 'u16be', 'u16le', 'u24be', 'u24le', 'u32be', 'u32le', 'u8', 'uncodedframecrc', 
    #         'vc1', 'vc1test', 'vcd', 'vidc', 'vob', 'voc', 'w64', 'wav', 'webm', 'webm_chunk', 'webm_dash_manifest', 'webp', 
    #         'webvtt', 'wtv', 'wv', 'yuv4mpegpipe']
    #     for 可编码或可编解码格式 in 可编码或可编解码格式列表:
    #         if 格式转换请求.rfind(可编码或可编解码格式) != -1 or 格式转换请求.rfind(可编码或可编解码格式.upper()) != -1:
    #             转出文件 = 传入文件.rsplit( ".", 1 )[0] + '.' +  可编码或可编解码格式
    #             print(转出文件)
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
    elif '合并' in 指令表达式[0]:
        将ffmpeg注入临时环境变量()
        音视频文件列表 = 指令表达式[1:]
        # 所有音视频文件所在目录相同 = all(所处路径(音视频路径) == 所处路径(所有音视频路径[0]) for 音视频路径 in 所有音视频路径)
        # print(所有音视频所在目录相同)
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
        # 音视频顺序文件路径 = str(os.getcwd())+'\\音视频顺序文件.txt'
        # print(音视频顺序文件路径)
        志语合并的媒体文件名 = '志语合并的媒体文件1'
        该目录下的文件列表 = os.listdir(所处路径(音视频文件列表[0]))
        print(所处路径(音视频文件列表[0]))
        print(该目录下的文件列表)
        for 文件 in 该目录下的文件列表:
            if '志语合并的媒体文件10' in 文件:
                raise ValueError('当前文件夹下合并后未改名的文件太多啦，已经不方便整理了。')
            for 序号 in range(9, 0, -1):
                if '志语合并的媒体文件' + str(序号) in 文件:
                    志语合并的媒体文件名 = '志语合并的媒体文件' + str(序号 + 1)
                    break
        合并指令 = 'ffmpeg' + ' ' + '-f' + ' ' + 'concat' + ' ' + '-i' + ' ' + '音视频顺序文件.txt' + ' ' + '-c' + ' ' + 'copy' + ' ' + 志语合并的媒体文件名 + '.' + 后缀名(音视频文件列表[0]) 
        os.system(合并指令)
        print('合好的音视频文件在它们的所共同在的文件夹中，名字是'+'“'+志语合并的媒体文件名+'.'+后缀名(音视频文件列表[0])+'”'+':')
    elif "百度" in 指令表达式[0] and "语音" in 指令表达式[0]:
        语音识别代码 = 指令表达式[1:]
        print(语音识别代码)
        print(语音识别代码[0])
    elif "分辨率" in 指令表达式[0] or "画质" in 指令表达式[0]:
        常用分辨率字典 = {'4K':'3840:2160','2K':'2560:1440','1080P':'1920:1080','720P':'1280:720','480P':'640:480','360P':'' }
        for 分辨率 in 常用分辨率列表:
            if 分辨率 in 指令表达式[0] or 分辨率.lower() in 指令表达式[0]:
                pass



                # ffmpeg -i sept2018_trailer.m4v -vf scale=640:48o sept2018_trailer_64o_480.mp4




    # ———————————————————————————————————windows快捷键—————————————————————————————————————————-
    elif ('录屏' in 指令表达式[0]) or ('屏幕' in 指令表达式[0] and '录制' in 指令表达式[0]) or ('录课' in 指令表达式[0]):
        执行快捷键指令并给出温馨提示("alt+esc","")
        执行快捷键指令并给出温馨提示("windows+alt+g", '为你打开windows自带的录屏工具，开启快捷键为“win+g”，如日后常有需要，可以记一下喽~') 
    elif '截屏' in 指令表达式[0] or '截图' in 指令表达式[0]:
        执行快捷键指令并给出温馨提示("alt+esc","")
        执行快捷键指令并给出温馨提示("windows+shift+s", '为你打开windows自带的截图工具，开启快捷键为“Win+Shift+S”，如日后常有需要，可以记一下喽~')
    elif ('剪贴版' in 指令表达式[0] and '记录' in 指令表达式[0]) or ('复制' in 指令表达式[0] and ('记录' in 指令表达式[0] or '历史' in 指令表达式[0])) :
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
    
          