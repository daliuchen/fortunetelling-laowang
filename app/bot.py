import io
import os
import telebot
import requests
import urllib
import json
import asyncio
from voice import AzureVoiceService
import functools
import qrcode
from PIL import Image

API_TOKEN = os.getenv('API_TOKEN')

bot = telebot.TeleBot(API_TOKEN)

VOICE_API_KEY = os.getenv('VOICE_API_KEY')
VOICE_API_REGION = os.getenv('VOICE_API_REGION')
voice_service = AzureVoiceService(api_key=VOICE_API_KEY, region=VOICE_API_REGION)

menu_list = ['测手相(需要上传手部照片)', '摇一卦', '生辰八字测算', '周公解梦']

# 定义处理菜单选项的处理函数
@bot.message_handler(func=lambda message: message.text in menu_list)
def handle_menu_selection(message):
    # 在用户选择后隐藏键盘
    hide_markup = telebot.types.ReplyKeyboardRemove()
    text = f"你选择了：【{message.text}】，老朽这就为你准备一下。"
    bot.send_message(message.chat.id, text, reply_markup=hide_markup)
    send_audio_sync(message.chat.id, text)

    echo_all(message)

@bot.message_handler(commands=['start'])
def start_message(message):
  text = "老夫精通阴阳五行，能够算命、紫微斗数、姓名测算、占卜凶吉、看命运八字等。命里有时终须有，命里无时莫强求。你有什么问题需要老朽帮忙算一算吗？你也可以发送语音给我。"
  bot.reply_to(message, text)
  send_audio_sync(message.chat.id, text)

  markup = telebot.types.ReplyKeyboardMarkup(row_width=3)
  for menu in menu_list:
    item_btn = telebot.types.KeyboardButton(menu)
    markup.add(item_btn)
  text = "你想让老朽为你做些什么？"
  bot.send_message(message.chat.id, text, reply_markup=markup)
  send_audio_sync(message.chat.id, text)

@bot.message_handler(commands=['clear_history'])
def clear_history(message):
  requests.delete(f'http://localhost:8000/clear_history?session_id={message.chat.id}', timeout=100)
  bot.reply_to(message, '老朽已为你清除记忆，客官莫要担心')

@bot.message_handler(content_types=['voice', 'audio'])
def handle_docs_audio(message):
  try:
    # 获取文件 ID
    file_id = message.voice.file_id
    file_info = bot.get_file(file_id)
    
    # 构建文件的下载链接
    file_path = file_info.file_path
    file_url = f'https://api.telegram.org/file/bot{API_TOKEN}/{file_path}'


    print(f"voice url: {file_url}")
    # read url as bytes
    voice_resp = requests.get(file_url)
    if voice_resp.status_code != 200:
      raise Exception(f"Failed to download voice: {voice_resp.status_code} {voice_resp.reason}")
    voice_data = voice_resp.content
    print(f"voice bytes length: {len(voice_data)}")

    query_str = voice_service.stt(voice_data)
    response = requests.post(f'http://localhost:8000/chat?query={urllib.parse.quote(query_str)}&session_id={message.chat.id}', timeout=100)
    if response.status_code == 200:
      raw_data = json.loads(response.text)
      need_payment = raw_data['need_payment']

      if need_payment:
        payment_form_qrcode = generate_qrcode(f"https://jinshuju.net/f/LXULCC?x_field_1={message.chat.id}")
        text = '天机不可泄露太多，为了平衡阴阳之道，老朽需要收取一些费用，以安抚天地之间的能量。不知您是否方便现在进行支付？'
        bot.send_message(message.chat.id, text)
        send_audio_sync(message.chat.id, text)
        return bot.send_photo(message.chat.id, payment_form_qrcode)
      
      resp_text = raw_data['output']
      bot.reply_to(message, resp_text)
      send_audio_sync(message.chat.id, resp_text)
    else:
      bot.reply_to(message, "对不起, 我不知该如何回答你")

  except Exception as e:
    print(e)
    bot.reply_to(message, f"发生错误: {str(e)}")

@bot.message_handler(content_types=['photo'])
def handle_docs_image(message):
  print(message)
  try:
    file_id = message.photo[-1].file_id
    file_info  = bot.get_file(file_id)
    file_url = f'https://api.telegram.org/file/bot{API_TOKEN}/{file_info.file_path}'

    response = requests.post(f'http://localhost:8000/chat?query={file_url}&session_id={message.chat.id}', timeout=100)
    if response.status_code == 200:
      resp_text = json.loads(response.text)['output']
      bot.reply_to(message, resp_text)
      send_audio_sync(message.chat.id, resp_text)
    else:
      bot.reply_to(message, "对不起, 我不知该如何回答你")
  except Exception as e:
    bot.reply_to(message, f"发生错误: {str(e)}")

def generate_qrcode(url):
  qr = qrcode.QRCode(
    version=1,  # 控制二维码的大小（1到40）
    error_correction=qrcode.constants.ERROR_CORRECT_Q,  # 错误纠正级别，可以是L、M、Q、H
    box_size=10,  # 每个小方块的像素大小
    border=4,  # 二维码边框的厚度，以小方块为单位
  )

  # 添加数据到QRCode对象
  qr.add_data(url)
  qr.make(fit=True)

  stream = io.BytesIO()

  # 创建Image对象
  img = qr.make_image(fill_color="black", back_color="white").convert('RGBA')
  # 将二维码图像保存到BytesIO对象中
  img.save(stream, format='PNG')

  stream.seek(0)
  binary_data = stream.getvalue()
  stream.close()
  return binary_data

@bot.message_handler(func=lambda message: True)
def echo_all(message):
  try:
    encoded_text = urllib.parse.quote(message.text)
    response = requests.post(f'http://localhost:8000/chat?query={encoded_text}&session_id={message.chat.id}', timeout=100)
    if response.status_code == 200:
      raw_data = json.loads(response.text)
      need_payment = raw_data['need_payment']

      if need_payment:
        payment_form_qrcode = generate_qrcode(f"https://jinshuju.net/f/LXULCC?x_field_1={message.chat.id}")
        text = '天机不可泄露太多，为了平衡阴阳之道，老朽需要收取一些费用，以安抚天地之间的能量。不知您是否方便现在进行支付？'
        bot.send_message(message.chat.id, text)
        send_audio_sync(message.chat.id, text)
        return bot.send_photo(message.chat.id, payment_form_qrcode)
      
      resp_text = raw_data['output']
      bot.reply_to(message, resp_text)
      send_audio_sync(message.chat.id, resp_text)
    else:
      bot.reply_to(message, "对不起, 我不知该如何回答你")
  except requests.RequestException as e:
    bot.reply_to(message, f"发生错误: {str(e)}")

def send_audio_sync(chat_id, text):
  voice_bytes = voice_service.tts(text)
  if voice_bytes is None:
    print(f"tts failed: {text}")
    return
  bot.send_audio(chat_id, voice_bytes, title='老王算命')

async def _send_audio(chat_id, text):
  loop = asyncio.get_event_loop()

  voice_bytes = await loop.run_in_executor(None, voice_service.tts, text)
  if voice_bytes is None:
    print(f"tts failed: {text}")
    return

  await loop.run_in_executor(None, functools.partial(bot.send_audio, chat_id, voice_bytes, title='老王算命'))

def send_audio(chat_id, text):
  _send_audio(chat_id, text)

bot.infinity_polling()