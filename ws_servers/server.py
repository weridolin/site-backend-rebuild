import asyncio
import http
import http.cookies
import logging
import signal
import urllib.parse
import uuid,jwt,sys,os
from handler import GptWebsocketHandle,WebHookWebsocketHandle
import websockets
import re,functools
from manage import get_manager


LOG_FORMAT = ('%(levelname) -s %(asctime)s %(name) -s %(funcName) '
            '-s %(lineno) -d: %(message)s')
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

def decode_token(token):
    secret = os.environ.get("JWT_KEY","DEBUGJWTKEY")
    payload = jwt.decode(token,secret, algorithms=["HS256"])
    return payload

def get_query_param(path, key):
    query = urllib.parse.urlparse(path).query
    params = urllib.parse.parse_qs(query)
    values = params.get(key, [])
    if len(values) == 1:
        return values[0]

async def create_handler(websocket,manager):
    if websocket.app == "site.alinlab.gpt":
        handler = GptWebsocketHandle(websocket,manger=manager)

    elif websocket.app == "site.alinlab.webhook":
        handler = WebHookWebsocketHandle(websocket,manger=manager)
    elif websocket.app =="site.alinlab.datafaker":
        ...
    else:
        raise NotImplementedError(f"App {websocket.app} handler not implemented")
    
    if hasattr(handler,"on_connect"):
        await handler.on_connect()
    await handler

class QueryParamProtocol(websockets.WebSocketServerProtocol):
    async def process_request(self, path, headers):
        token = get_query_param(path=path, key="token")
        print("token",token)
        if not token:
            return http.HTTPStatus.UNAUTHORIZED, [], b"Token is missing"
        try:
            payload = decode_token(token)
            self.token_payload = payload
            self.user_id = payload.get("user_id",None)
            self.websocket_id = payload.get("websocket_id")
            self.app = payload.get("app")
            
            if self.app=="site.alinlab.gpt":
                self.conversation_id = payload.get("conversation_id")
            elif self.app=="site.alinlab.datafaker":
                # self.callback_url = payload.get("callback_url")
                self.record_key = payload.get("record_key")
                self.target_path = payload.get("target_path")
                self.data_count = payload.get("data_count")
                self.fields_info = payload.get("fields_info")
                self.callback_url_grpc = payload.get("callback_url_grpc")
        except jwt.DecodeError:
            return http.HTTPStatus.UNAUTHORIZED, [], b"Invalid token"
        
        # else:
            # return http.HTTPStatus.NOT_FOUND, [], b"URL not found"


async def main():
    # Set the stop condition when receiving SIGINT or SIGTERM.
    loop = asyncio.get_running_loop()
    stop = loop.create_future()
    # loop.add_signal_handler(signal.SIGINT, stop.set_result, None)
    # loop.add_signal_handler(signal.SIGTERM, stop.set_result, None)
    manager = get_manager()
    async with websockets.serve(
        functools.partial(create_handler,manager=manager),
        host="0.0.0.0",
        port=8001,
        create_protocol=QueryParamProtocol,
    ):
        print("Running on http://0.0.0.0:8001/")
        await stop
        print("\rExiting")


if __name__ == "__main__":
    asyncio.run(main())