import dataclasses
from typing import List,Dict

import sys
from gpt.ali.config import AliChatConfig
from gpt.base import HttpMixins,EventStream
from rest_framework import status
import aiohttp
import json
import logging
import asyncio
from rpc import gpt_pb2,gpt_pb2_grpc
import grpc

logger = logging.getLogger(__name__)

@dataclasses.dataclass
class AliRequestInputParam:
    prompt:str=None
    messages:List[Dict]=None

@dataclasses.dataclass
class AliRequestParameters:
    seed:int=1234
    max_tokens:int=1500
    top_p:float=0.9
    top_k:int=40
    repetition_penalty:float=1.1
    temperature:float=0.9
    stop=None
    stream:bool=True
    enable_search:bool=False
    result_format:str="message"
    incremental_output:bool=True

@dataclasses.dataclass
class AliRequestBody:
    model:str
    input:AliRequestInputParam
    parameters:AliRequestParameters


class HttpRequest(HttpMixins):

    def __init__(self,query_message_uuid=None,callback_url=None,callback_url_grpc=None,conversation_id=None) -> None:
        super().__init__()
        self.query_message_uuid = query_message_uuid
        self.callback_url = callback_url
        self.callback_url_grpc = callback_url_grpc
        self.conversation_id = conversation_id

    async def request(
        self,
        model:str,
        messages:List[str]=None,
        prompt:str=None,
        stream:bool=True,
        enable_search:bool=False,
        incremental_output:bool=True,
        api_key = None,
        ws_conn = None
    ):
        self.ws_conn = ws_conn
        config = AliChatConfig.from_env()
        config.API_KEY = api_key
        header = {
            "Authorization": f"Bearer {config.API_KEY}",
            "Content-Type": "application/json",
        }
        if stream:
            header["Accept"] = "text/event-stream"
    
        body = dataclasses.asdict(AliRequestBody(
                model=model,
                input=AliRequestInputParam(messages=messages) if messages else AliRequestInputParam(prompt=prompt),
                parameters=AliRequestParameters(
                    stream=stream,
                    enable_search=enable_search,
                    incremental_output=incremental_output
                )
            )
        )
        # print(">>> message",messages)
        async with aiohttp.ClientSession() as session:
            async with session.post(url=config.URI,headers=header,json=body) as response:
                if response.status == 200:
                    async for res in response.content:
                        res = res.decode('utf8') 
                        res = res.rstrip('\n').rstrip('\r')
                        self.parse_raw(res)
                        if self.interrupt:
                            logger.info(f"ali gpt request was interrupt,update result back to DB")
                            break
                else:
                    res = json.loads(await response.text())
                    logger.error(f"ali gpt request error -> {res} ")
                    if res.get("code")=="InvalidApiKey":
                        self.error = True
                        self.error_code = res.get("code")
                        self.error_detail = res.get("message")
                        ### todo 发送错误消息到websocket
                        await self.ws_conn.send(json.dumps({"error":res.get("message")}))
        # logger.info(f"ali gpt request was interrupt,update result back to DB")
        await self.on_finish()

    def on_event(self,event:EventStream):
        if event.event_type == "result":
            ## 处理结果 
            try:
                data = json.loads(event.event_data)
                content = data["output"]["choices"][0]["message"]["content"]
                self.total_reply += content
                message = {
                    "conversation_id":self.conversation_id,
                    "message_id":self.query_message_uuid,
                    "content":content,
                    "content_type":"text",
                    "type":"message",
                }
                ## 发送推送消息到RQ供websocket推送服务消费
                if hasattr(self,"ws_conn") and self.ws_conn:
                    asyncio.create_task(self.ws_conn.send(json.dumps(message,ensure_ascii=False)))
            except json.JSONDecodeError:
                data = event.event_data
                self.total_reply += data

        elif event.event_type == "error":
            self.error = True
            data = json.loads(event.event_data)
            self.error_code = data.get("code")
            self.error_detail = data.get("message")
            
    async def on_finish(self):
        # print(self.total_reply)
        if self.error:
            logger.error(f"ali gpt request error -> {self.error_code} {self.error_detail}")
        
        if self.callback_url_grpc:
            try:
                await self.callback_by_rpc()
            except :
                logger.error("ali gpt request update result back to DB error by grpc",exc_info=True)

        ## 通过http回调更新结果
        elif self.callback_url:
            async with aiohttp.ClientSession() as session:
                async with session.post(url=self.callback_url,json={
                    "reply_content":self.total_reply,
                    "error":self.error,
                    "error_code":self.error_code,
                    "error_detail":self.error_detail,
                    "interrupt":self.interrupt,
                    "interrupt_reason":self.interrupt_reason,
                    "query_message_id":self.query_message_uuid
                },) as response:
                    if response.status == 200:
                        logger.info("ali gpt request update result back to DB success")
                    else:
                        logger.error(f"ali gpt request update result back to DB error -> {response.status} {await response.text()}")
        
        ## 通过WS发送结束消息
        if hasattr(self,"ws_conn") and self.ws_conn:
            logger.info(f"ali gpt request finish, conversation id -> {self.conversation_id}")
            await self.ws_conn.send(json.dumps({
                "type":"reply_finish",
                "conversation_id":self.conversation_id,
                "message_id":self.query_message_uuid,
                "content":"",
                "content_type":"",
            }))
    
    async def callback_by_rpc(self):
        logger.info(f"ali gpt request update result back to DB by grpc, address -> {self.callback_url_grpc}")
        async with grpc.aio.insecure_channel(self.callback_url_grpc) as channel:
            stub = gpt_pb2_grpc.GptMessageStub(channel)
            response = await stub.UpdateQueryResult(gpt_pb2.UpdateQueryResultRequest(
                    reply_content=self.total_reply,
                    error=self.error,
                    error_code=self.error_code,
                    error_detail=self.error_detail,
                    interrupt=self.interrupt,
                    interrupt_reason=self.interrupt_reason,
                    query_message_id=self.query_message_uuid
            ))
            if response.success:
                logger.info("ali gpt request update result back to DB success")
            else:
                logger.error("ali gpt request update result back to DB success error ")            
        
# if __name__ =="__main__":
    # import asyncio,os
    # loop = asyncio.get_event_loop()
    # # message =[
    
    # #     {'role': 'user', 'content': '你好，哪个公园距离我最近？'}, 
    # #     {
    # #         "role": "assistant",
    # #         "content": "如果你在中国，我推荐你去北京的颐和园 ... ... 适合散步和欣赏景色。",
    # #     },
    # #     {'role': 'user', 'content': '你好，哪个公园距离我最近？'}]
    # message = [
    # ]
    # loop.run_until_complete(HttpRequest().request("qwen-max",messages=message))
    # loop.close()
    ...