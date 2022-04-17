# 音频文件转文字：采用百度的语音识别python-SDK  
# 百度语音识别API配置参数  
from aip import AipSpeech  
# 谷歌识别，这里用了它自动识别录音终止的功能
import speech_recognition as sr  
import os
  
# Use SpeechRecognition to record 使用语音识别包录制音频  
def 录音(rate=16000):  
    r = sr.Recognizer()  
    with sr.Microphone(sample_rate=rate) as source:    
        audio = r.listen(source)  
    wav_num = 0
    with open(f"00{wav_num}.wav", "wb") as f:  
        f.write(audio.get_wav_data())  
    # wav_num = wav_num + 1  
  
# 录音() 

APP_ID = '25989514'  
API_KEY = 'ZnLgb47K5NennuMXo7L7wzvK'  
SECRET_KEY = 'sYfFO7GMVKMnGLULw5Cih60a8NqqZbGX'  
client = AipSpeech(APP_ID, API_KEY, SECRET_KEY)  
path = '000.wav'  
  
def 返回说出的内容(APP_ID, API_KEY, SECRET_KEY):
    client = AipSpeech(APP_ID, API_KEY, SECRET_KEY)  
    path = '000.wav'
    录音()
    with open(path, 'rb') as fp:  
        voices = fp.read()  
        try:  
            # 参数dev_pid：1536普通话(支持简单的英文识别)、1537普通话(纯中文识别)、1737英语、1637粤语、1837四川话、1936普通话远场  
            result = client.asr(voices, 'wav', 16000, {'dev_pid': 1537, }) 
            # result = CLIENT.asr(get_file_content(path), 'wav', 16000, {'lan': 'zh', })  
            # print(result)  
            # print(result['result'][0])  
            # print(result)  
            print(result)
            result_text = result["result"][0]  
            print("you said: " + result_text)  
            return result_text  
        except KeyError:  
            print("KeyError")

# 听写()
