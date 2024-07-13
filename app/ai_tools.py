import random
from typing import Callable, Any

import requests
from langchain_community.chat_models import ChatOpenAI
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import Qdrant
from langchain.agents import tool
from langchain.utilities import SerpAPIWrapper
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from qdrant_client import QdrantClient

from urllib.parse import urlparse

from app.payment_service import redis_client


def is_valid_url(url):
    parsed_url = urlparse(url)
    if parsed_url.scheme and parsed_url.netloc:
        return True
    else:
        return False


class RequestErrorInfoChat:
    @classmethod
    def invoke(cls, input):
        prompt = ChatPromptTemplate.from_template("""
        你是一个内容总结的小助手，用户输入内容，你需要提取总结内容中的报错信息"
        --------- 下面是用户输入的内容 ---------
           {input}
           """)
        chain = prompt | ChatOpenAI(temperature=0) | StrOutputParser()
        return chain.invoke({"input": input})


class HumanReaderInfoChat:
    @classmethod
    def invoke(cls, input):
        prompt = ChatPromptTemplate.from_template("""
你是一个内容总结的小助手，你需要总结用户输入的内容
# 规则
1. 总结出来的结果是人可以读懂的，并且语句通顺，否则你将受到惩罚。
2. 总结出来的内容不要包含链接，否则你将受到惩罚。
3. 总结出的内容中请使用摄氏度，否则你将受到惩罚。

--------- 下面是用户输入的内容 ---------
{input}
           """)
        chain = prompt | ChatOpenAI(temperature=0) | StrOutputParser()
        return chain.invoke({"input": input})


@tool
def search(query: str):
    """只有需要了解实时信息或不知道的事情的时候才会使用这个工具"""
    serp = SerpAPIWrapper()
    result = serp.run(query)
    print("实时搜索结果：", result)
    result = HumanReaderInfoChat.invoke(result)
    return result


@tool
def get_info_from_local_db(query: str):
    """只有回答与2024年运势或者龙年运势相关的问题的时候，会使用这个工具"""
    try:
        client = Qdrant(
            QdrantClient(path="storage"),
            "local_documents",
            OpenAIEmbeddings())
        retriever = client.as_retriever(search_type="mmr")
        return retriever.get_relevant_documents(query)
    except Exception:
        HumanReaderInfoChat.invoke("老夫技不如人，没有测算出来。请见谅")

@tool
def bazi_cesuan(query: str):
    """只有做八字测算的时候才会使用这个工具，需要输入用户姓名和出生年月日时，如果缺少用户姓名和出生年月日时则不可用."""
    url = "https://api.yuanfenju.com/index.php/v1/Bazi/cesuan"
    api_key = "3DpUrnduP7KsTX58DZZcgdtTv"
    prompt = ChatPromptTemplate.from_template("""
 你是一个参数查询助手，根据用户输入内容找出相关的参数并按JSON格式返回。
 JSON格式如下：
     - name：String,姓名
     - sex: Int,性别 0男生 1女生 (根据姓名判断)
     - type,Int,历类型 0农历 1公历
     - year: Int,出生年 例: 1988
     - month: Int,出生月 例: 1
     - day: Int,出生日 例: 1
     - hours: Int,出生时 例: 1 （默认为8点）
     - minute: Int,出生分 例: 1（默认为0）
 如果没有找到相关参数，则需要提醒用户告诉你这些内容，只返数据结构，不要有其他的评论，否则将会受到惩罚。
 --------- 下面是用户输入的内容 ---------
    {input}
    """)
    parser = JsonOutputParser()
    prompt = prompt.partial(format_instructions=parser.get_format_instructions())
    chain = prompt | ChatOpenAI(temperature=0) | parser

    request_data = chain.invoke({"input": query})
    request_data["api_key"] = api_key

    json_obj = None
    try:
        response = requests.post(url, data=request_data)
        if response.status_code == 200:
            print("返回数据", response.json())
            json_obj = response.json()
            if json_obj["errcode"] == 0:
                return "八字为：" + json_obj["data"]["bazi_info"]["bazi"]
    except Exception:
        return "老夫技不如人，没有测算出来。少侠请见谅"
    return RequestErrorInfoChat.invoke(json_obj)


@tool
def yaoyigua():
    """只有用户想要占卜抽签。摇卦的时候才会使用这个工具"""

    cache_key = "yaoyigua_cache_key"
    list_data = redis_client.lrange(cache_key, 0, -1)

    def inner_yaoyigua():
        url = "https://api.yuanfenju.com/index.php/v1/Zhanbu/yaogua"
        api_key = "3DpUrnduP7KsTX58DZZcgdtTv"

        request_data = {
            "api_key": api_key
        }
        json_obj = None
        try:
            response = requests.post(url, data=request_data)
            if response.status_code == 200:
                print("返回数据", response.json())
                json_obj = response.json()
                print(json_obj)
                if json_obj["errcode"] == 0:
                    return HumanReaderInfoChat.invoke(json_obj["data"]);

        except Exception:
            return "系统异常了，需要告诉用户稍后再试，或者再来一卦，并且对这次失败做一个和占卜相关的解释"

        return RequestErrorInfoChat.invoke(json_obj)

    if len(list_data) == 0:
        result = inner_yaoyigua()
        redis_client.lpush(cache_key, result)
        return result
    random_int = random.randint(0, 100) % 2
    print('-'*50,random_int)
    if random_int == 0:
        index = random.randint(0, len(list_data)-1)
        return str(list_data[index], 'utf-8')
    result = inner_yaoyigua()
    redis_client.lpush(cache_key, result)
    return result


@tool
def jiemeng(query: str):
    """只有用户想要解梦才会使用这个工具，需要输入用户梦境的内容，如果缺少用户的内容则不可用。"""

    url = "https://api.yuanfenju.com/index.php/v1/Gongju/zhougong"
    api_key = "3DpUrnduP7KsTX58DZZcgdtTv"

    prompt = ChatPromptTemplate.from_template("""
根据内容提取一个1个关键词，只返回关键词内容，不要有其他内容，否则将会受到惩罚。
--------- 下面是用户输入的内容 ---------
        {input}
        """)
    llm = prompt | ChatOpenAI(temperature=0) | StrOutputParser()
    keyword = llm.invoke({"input": query})
    print("关键词：", keyword)
    request_data = {
        "api_key": api_key,
        "title_zhougong": keyword
    }

    json_obj = None
    try:
        response = requests.post(url, data=request_data)
        if response.status_code == 200:
            print("返回数据", response.json())
            json_obj = response.json()
            print(json_obj)
            if json_obj["errcode"] == 0:
                return HumanReaderInfoChat.invoke(json_obj["data"])
    except Exception:
        return "系统异常了，需要告诉用户稍后再试,或者再来一次梦境，并且对这次失败做一个和解梦相关的解释"
    return RequestErrorInfoChat.invoke(json_obj)


@tool
def kan_shou_xiang(query: str):
    """当用户想要看手相才会使用这个工具，需要输入手相图片链接，如果缺少用户手相图片的链接则不可用"""

    if not is_valid_url(query):
        return "需要上传照片才可以看手相"

    url = "https://api.yuanfenju.com/index.php/v1/Dashuju/shouxiang"
    api_key = "3DpUrnduP7KsTX58DZZcgdtTv"

    request_data = {
        "api_key": api_key,
        "image_url": query
    }
    json_obj = None
    try:
        response = requests.post(url, data=request_data)
        if response.status_code == 200:
            print("返回数据", response.json())
            json_obj = response.json()
            print(json_obj)
            if json_obj["errcode"] == 0:
                return HumanReaderInfoChat.invoke(json_obj["data"])
    except Exception:
        return "系统异常了，需要告诉用户稍后再试,或者再看一次手相，并且对这次失败做一个和看手相相关的解释"
    return RequestErrorInfoChat.invoke(json_obj)
