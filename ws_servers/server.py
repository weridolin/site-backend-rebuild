import asyncio
import http
import http.cookies
import logging
import signal
import urllib.parse
import uuid,jwt,sys,os
from handler import GptWebsocketHandle
import websockets
import re
import argparse
from client.rabbitmq import start_rabbitmq,WebSocketNodeConsumer

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

async def create_handler(websocket):  
    if websocket.app == "gpt":
        handler = GptWebsocketHandle(websocket)
    else:
        raise NotImplementedError(f"App {websocket.app} handler not implemented")
    
    if hasattr(handler,"on_connect"):
        await handler.on_connect()
    await handler

class QueryParamProtocol(websockets.WebSocketServerProtocol):
    async def process_request(self, path, headers):
        token = get_query_param(path=path, key="token")
        print("token",token)
        try:
            payload = decode_token(token)
            self.token_payload = payload
            self.user_id = payload.get("user_id")
            self.websocket_id = payload.get("websocket_id")
        except jwt.DecodeError:
            return http.HTTPStatus.UNAUTHORIZED, [], b"Invalid token"
        
        if re.search(r"/ws-endpoint/api/v1/gpt/\?token=([\s\S])*", path):
            self.app = "gpt"
            self.conversation_id = payload.get("conversation_id")
        else:
            return http.HTTPStatus.NOT_FOUND, [], b"URL not found"


async def main():
    # Set the stop condition when receiving SIGINT or SIGTERM.
    loop = asyncio.get_running_loop()
    stop = loop.create_future()
    # loop.add_signal_handler(signal.SIGINT, stop.set_result, None)
    # loop.add_signal_handler(signal.SIGTERM, stop.set_result, None)
    async with websockets.serve(
        create_handler,
        host="0.0.0.0",
        port=8001,
        create_protocol=QueryParamProtocol,
    ):
        print("Running on http://0.0.0.0:8001/")
        await stop
        print("\rExiting")


if __name__ == "__main__":
    asyncio.run(main())