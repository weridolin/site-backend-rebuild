from client.rabbitmq import WebSocketNodeConsumer
import os,sys,json
import logging,datetime

logger = logging.getLogger(__name__)

class WsConnManager:

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            cls._instance = super(WsConnManager, cls).__new__(cls)
        return cls._instance
    

    def __init__(self) -> None:
        self.conn_map = dict({
            "site.alinlab.gpt":dict()
        })
        rabbit_mq_url= f"amqp://{os.environ.get('RABBITMQ_DEFAULT_USER1','werido')}:{os.environ.get('RABBITMQ_DEFAULT_PASS1','359066432')}@{os.environ.get('RABBITMQ_SVC_NAME1','43.128.110.230')}:{os.environ.get('RABBITMQ_PORT1','30003')}/"
        logger.info(f"rabbit mq url -> {rabbit_mq_url}")
        self.rabbitmq = WebSocketNodeConsumer(
            amqp_url=rabbit_mq_url,
            on_message_callback=self.on_rabbitmq_message
        )
        self.rabbitmq.run()

    def register_conn(self,app,uuid,conn):
        if app not in self.conn_map:
            self.conn_map[app] = dict()
        self.conn_map[app][uuid] = conn
        logger.info("register conn app -> %s uuid -> %s",app,uuid)


    def remove_conn(self,app,uuid):
        if app in self.conn_map and uuid in self.conn_map[app]:
            conn =  self.conn_map[app][uuid]
            if conn.open:
                conn.close()
            del self.conn_map[app][uuid]
        
    def get_conn(self,app,uuid):
        if app in self.conn_map and uuid in self.conn_map[app]:
            return self.conn_map[app][uuid]
        return None
    
    def broadcast(self,app,message):
        if app in self.conn_map:
            for conn in self.conn_map[app].values():
                conn.send(message)

    def on_rabbitmq_message(self,channel,basic_deliver, properties, body):
        logger.info('Received message # %s from %s: %s',basic_deliver.delivery_tag, properties.app_id, body)
        try:
            msg = json.loads(body)
            from_app = msg.get("from_app",None)
            # user_id = msg.get("user_id",None)
            websocket_id = msg.get("websocket_id",None)
            exp = msg.get("exp",None)
            if not websocket_id or not from_app:
                logger.error(f"websocket id or from_app not found in message")
                return
            if exp and datetime.datetime.now().timestamp() > exp:
                logger.error(f"message expired at {exp},now is {datetime.datetime.now().timestamp()}")
                return
            # if from_app == "site.alinlab.gpt":
            conn = self.get_conn(from_app,websocket_id)
            if conn:
                if hasattr(conn,"on_rabbitmq_message"):
                    conn.on_rabbitmq_message(msg)
                else:
                    logger.error(f"on_rabbitmq_message not implement for {from_app} {websocket_id}")
            else:
                logger.error(f"websocket not found for {from_app} {websocket_id}")
                logger.info(f"conn map -> {self.conn_map}")


        except Exception as exc:
            logger.error(f"mq message parse error: {exc}",exc_info=True)

__manager = None    

def get_manager():
    global __manager
    if __manager is None:
        __manager = WsConnManager()
    return __manager


