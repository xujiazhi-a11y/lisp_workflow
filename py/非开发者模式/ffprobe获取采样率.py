import subprocess
import shlex
import json

# function to find the resolution of the input video file
def ffprobe获取采样率(pathToInputVideo):
    cmd = "ffprobe -v quiet -print_format json -show_streams"
    args = shlex.split(cmd)
    args.append(pathToInputVideo)
    # run the ffprobe process, decode stdout into utf-8 & convert to JSON
    ffprobeOutput = subprocess.check_output(args,shell = True).decode('utf-8')
    ffprobeOutput = json.loads(ffprobeOutput)

    # for example, find height and width
    视频信息 = ffprobeOutput['streams'][0]
    音频信息 = ffprobeOutput['streams'][1]
    视频采样率 = 视频信息['time_base']
    音频采样率 = 音频信息['time_base']
    return(视频采样率, 音频采样率)
