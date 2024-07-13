import asyncio
import functools
import os
import telebot
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from langchain_community.vectorstores import Qdrant, Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.jina_reader import JinaReader
from app.laowang import LaoWang
from app.payment_service import PaymentService

from app.voice import AzureVoiceService

VOICE_API_KEY = os.getenv('VOICE_API_KEY')
VOICE_API_REGION = os.getenv('VOICE_API_REGION')
voice_service = AzureVoiceService(api_key=VOICE_API_KEY, region=VOICE_API_REGION)

app = FastAPI()

API_TOKEN = os.getenv('API_TOKEN')
bot = telebot.TeleBot(API_TOKEN)


@app.get("/")
def read_root():
    return {"data": "算命老王！！！！\n 知你所想"}


@app.post("/chat")
def chat(query: str, session_id: str):
    payment_service = PaymentService(session_id)
    lao_wang = LaoWang(session_id)
    if payment_service.is_exists_not_payment_white_list():
        res = lao_wang.run(query)
        res.update({"need_payment": False})
        return res

    if payment_service.is_payment():
        return {"need_payment": True}

    res = lao_wang.run(query)
    if lao_wang.is_need_payment():
        payment_service.payment()
        return {"need_payment": True}

    res.update({"need_payment": False})
    return res


@app.post("/payment")
async def payment(request: Request):
    session_id = (await request.json())["entry"]["x_field_1"]
    print(session_id)
    if session_id is None:
        return {}

    payment_service = PaymentService(session_id)
    payment_service.del_payment()
    payment_service.set_not_payment_white_list()
    lao_wang = LaoWang(session_id)
    last_message = lao_wang.get_memory_history().messages[-1]
    if last_message is None:
        return {}
    bot.send_message(session_id, last_message.content)
    send_audio_sync(session_id, last_message.content)
    return {}


@app.post("/add_urls")
def add_urls(url: str):
    jina_reader = JinaReader()
    text = jina_reader.read(url)
    splits = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200).split_text(text)

    Qdrant.from_texts(splits, OpenAIEmbeddings(model="text-embedding-3-small"),
                      path="storage", collection_name="local_documents")

    return {"ok": "添加成功"}


@app.delete("/clear_history")
def clear_history(session_id: str):
    lao_wang = LaoWang(session_id)
    lao_wang.clear_history()
    payment_service = PaymentService(session_id)
    payment_service.del_payment()
    payment_service.del_exists_not_payment_white_list()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    lao_wang = LaoWang()
    try:
        while True:
            data = await websocket.receive_text()
            res = lao_wang.run(data)
            await websocket.send_text(f"AI: {res.get('output')}")
    except WebSocketDisconnect:
        print("WebSocket closed")
        await websocket.close()

async def _send_audio(chat_id, text):
  loop = asyncio.get_event_loop()

  voice_bytes = await loop.run_in_executor(None, voice_service.tts, text)
  if voice_bytes is None:
    print(f"tts failed: {text}")
    return

  await loop.run_in_executor(None, functools.partial(bot.send_audio, chat_id, voice_bytes, title='老王算命'))

def send_audio(chat_id, text):
  asyncio.run(_send_audio(chat_id, text))

def send_audio_sync(chat_id, text):
  voice_bytes = voice_service.tts(text)
  if voice_bytes is None:
    print(f"tts failed: {text}")
    return
  bot.send_audio(chat_id, voice_bytes, title='老王算命')
