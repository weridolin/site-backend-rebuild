import asyncio,json
from manage import get_manager
from gpt.ali.request import HttpRequest as AliHttpRequest
from websockets import server
from websockets import exceptions as WsExceptions


import logging
logger = logging.getLogger(__name__)

class BaseHandle:
    
    def __init__(self, websocket,manger=None):
        self.websocket = websocket
        self.close = False
        self.manager = manger or get_manager()
        self.manager.register_conn(self.websocket.app,self.websocket.websocket_id,self)
        self.req_map = dict() ## 储存当前正在进行中的对话 conversation_id:(req,task)

    async def on_connect(self) -> None:
        logger.info("new websocket client connect,websocket id -> %s",self.websocket.websocket_id)
        self.manager.rabbitmq.add_subscribe(f"gpt.wsmessage.{self.websocket.websocket_id}")
        await asyncio.sleep(0)

    async def on_disconnect(self) -> None:
        logger.info("websocket client disconnect")
    #     self.manager.remove_conn(self.websocket.app,self.websocket.websocket_id)
    #     self.manager.rabbitmq.remove_subscribe(f"gpt.wsmessage.{self.websocket.websocket_id}")

    async def on_error(self, exc: Exception) -> None:
        if not isinstance(exc, WsExceptions.ConnectionClosedOK):
            logger.error(f"websocket handle error -> {exc} ",exc_info=True)
        else:
            logger.info(f"websocket conn closed, id: {self.websocket.websocket_id}")
        self.manager.remove_conn(self.websocket.app,self.websocket.websocket_id)
        self.manager.rabbitmq.remove_subscribe(f"gpt.wsmessage.{self.websocket.websocket_id}")


    async def on_close(self,code,reason) -> None:
        logger.info(f"websocket handle close -> {code} {reason}")
        self.manager.remove_conn(self.websocket.app,self.websocket.websocket_id)
        self.manager.rabbitmq.remove_subscribe(f"gpt.wsmessage.{self.websocket.websocket_id}")

    async def dispatch(self) -> None:
        raise NotImplementedError

    async def send(self, message: str) -> None:
        await self.websocket.send(message)

    def __await__(self):
        task = asyncio.create_task(self.dispatch())
        yield from task

    async def close(self,code,reason) -> None:
        self.close = True
        await self.websocket.close(code,reason)
        await self.on_close(code,reason)

    @property
    def open(self):
        return self.websocket.state == server.State.OPEN
    
    def cancel_task(self,conversation_id,interrupt_reason="interrupt by new message"):
        try:
            old_req,old_task = self.req_map[conversation_id]
            old_req.interrupt = True
            old_req.interrupt_reason = interrupt_reason
            old_task.cancel()
        except Exception as exc:
            logger.error(f"cancel task error -> {exc}")

    def on_rabbitmq_message(self,msg):
        raise NotImplementedError

    def on_ws_message(self,msg):
        raise NotImplementedError



class GptWebsocketHandle(BaseHandle):

    async def dispatch(self):
        while not self.close:
            try:
                message = await self.websocket.recv()
                self.on_ws_message(message)
            except Exception as exc:
                await self.on_error(exc)
                break

    def on_rabbitmq_message(self,msg:dict):
        """
            {   "user_id":1,
                "uuid":"2d7e4e1e-5e2a-4f4d-8e4b-5f5a5f5a5f5a",
                "conversation_id":5,
                "role":"user",
                "content":"hello world",
                "content_type":"text",
                "parent_message_uuid":2,
                "children_message_uuid":3,
                "websocket_id":"747c432d-d51e-4511-bffd-3182ccdba689",
                "platform":"ali",
                "model":"Qwen",
                "history":[
                        {
                            "role": "system",
                            "content": "You are a helpful assistant."
                        },
                        {
                            "role": "user",
                            "content": "你好，哪个公园距离我最近？"
                        }
                ],
                "api_key":"123456",
            }
        """
        print(f"get message from rabbitmq -> {msg}")
        platform,model = msg.get("platform"),msg.get("model")
        if platform=="通义千问":
            message = msg.get("history",[])
            query_message_uuid  = msg.get("uuid",None)
            conversation_id = msg.get("conversation_id",None)
            api_key = msg.get("api_key",None)
            if not api_key:
                logger.error(f"api key not found in message -> {msg}")
                return
            if not query_message_uuid:
                logger.error(f"message uuid not found in message -> {msg}")
                return
            req = AliHttpRequest(
                query_message_uuid=query_message_uuid,
                callback_url=msg.get("callback_url"),
                callback_url_grpc=msg.get("callback_url_grpc"),
                conversation_id=conversation_id
            )
            task = asyncio.create_task(req.request(
                model=model,
                messages=message,
                ws_conn=self,
                api_key=api_key
            ))
            if self.req_map.get(msg["conversation_id"]):
                logger.info(f"interrupt by new message, conversation id -> {msg['conversation_id']}")
                self.cancel_task(msg["conversation_id"])
            self.req_map.update({msg["conversation_id"]:(req,task)})


    def on_ws_message(self, msg):
        if isinstance(msg,bytes):
            msg = msg.decode("utf-8")
        if isinstance(msg,str):
            try:
                msg = json.loads(msg)
                if msg.get("type")=="stop":
                    conversation_id = msg.get("conversation_id")
                    # message_id = msg.get("message_id")
                    if conversation_id and self.req_map.get(conversation_id):
                        logger.info(f"interrupt by user, conversation id -> {conversation_id}")
                        self.cancel_task(conversation_id,interrupt_reason="interrupt by user")
                        return
            except json.JSONDecodeError:
                logger.error(f"message is not a valid json format -> {msg}")
                return
        logger.info(f"get message from client, websocket id -> {self.websocket.websocket_id}  message -> {msg}")