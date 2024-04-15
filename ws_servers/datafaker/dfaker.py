"""
    WS收到开始任务信息 --> 根据条数分割产生任务()--> 开始执行 --> 每完成1%通过WS返回 
"""

import os,grpc,logging
import asyncio,os,csv,json
from datafaker import generator
from rpc import gpt_pb2,gpt_pb2_grpc

# threadsPool = ThreadPoolExecutor(max_workers=os.cpu_count()*3)

# def create_task(dataCount,filename):
#     with open(os.path.join(os.path.dirname(__file__),"select_options.json"),"rb") as f:
#         field_info = json.load(f)    
#     thehold = dataCount // 100
#     with open('1a.csv','wt') as f2:
#         cw = csv.writer(f2, lineterminator = '\n')
#         #采用writerow()方法
#         for item in FakerDataFactory(data_count=32000,fields_info=field_info):
#             cw.writerow(item) #将列表的每个元素写到csv文件的一行
#         #或采用writerows()方法
#         #cw.writerows(l) #将嵌套列表内容写入csv文件，每个外层元素为一行，每个内层元素为一个数据
import aiofiles
from aiocsv import AsyncWriter
from const import WSMessageType
import uuid

logger = logging.getLogger(__name__)

async def create_task_async(record_key=None,ws=None,target_path=None,count=None,fields_info=None,callback_url_grpc=None):
    logger.info(f"create task async, record_key -> {record_key}")

    if not os.path.exists(os.path.dirname(target_path)):
        os.makedirs(os.path.dirname(target_path))

    async with aiofiles.open(target_path, mode= 'w') as f:
        writer = AsyncWriter(f,lineterminator = '\n')
        index,threshold =0,count // 100
        data_iterator = FakerDataFactory(data_count=count,fields_info=fields_info)
        await writer.writerow(data_iterator.field_titles) 
        for item in data_iterator:  
            index+=1
            if index % threshold==0:
                # ws send progress
                payload = {
                    "type":WSMessageType.progress,
                    "data":{
                        "progress":int(index/count*100)
                    },
                    "record_key":record_key
                }   
                await ws.send(json.dumps(payload,ensure_ascii=False))
            await writer.writerow(item) #将列表的每个元素写到csv文件的一行
    download_code = uuid.uuid4().hex[:6]
    if callback_url_grpc:
        await callback_by_rpc(record_key,target_path,download_code,callback_url_grpc)
    await ws.send(json.dumps({
        "type":WSMessageType.finish,
        "record_key":record_key,
        "data":{
            "download_code":download_code}
        },ensure_ascii=False))
    return target_path,ws


async def callback_by_rpc(record_key,file_path,download_code,callback_url_grpc):
    print(f"ali gpt request update result back to DB by grpc, address -> {callback_url_grpc}")
    async with grpc.aio.insecure_channel(callback_url_grpc) as channel:
        stub = gpt_pb2_grpc.GptMessageStub(channel)
        response = await stub.UpdateDataFakerGenerateResult(gpt_pb2.UpdateDataFakerGenerateResultRequest(
            record_key=record_key,
            file_path=file_path,
            download_code=download_code
        ))
        if response.success:
            logger.info("ali gpt request update result back to DB success")
        else:
            logger.error("ali gpt request update result back to DB success error ")     

class FakerDataFactory():
    
    def __init__(self,data_count=None,fields_info=None) -> None:
        self.data_count = data_count
        self.fields_info:dict = fields_info or {}
        self.already_count = 1

    def __iter__(self):
        return self

    def __next__(self):
        if self.already_count > self.data_count:
            raise StopIteration
        data = self.create()
        self.already_count+=1
        return data

    @property
    def field_titles(self):
        return [item.get("name","undefined_field_name") for item in self.fields_info]

    def create(self)->list:
        if not self.fields_info:
            return ["please","set","fields","first","!","!","!"]
        else:
            res = []
            for item in self.fields_info:
                generator_str,condition = item.get("generator"),item.get("condition")
                generator_class=getattr(generator,generator_str)
                value = generator_class().generate(**self._convert_params2dict(condition=condition))
                res.append(value)
            return res

    @staticmethod
    def _convert_params2dict(condition:list):
        kwargs = dict()
        for con in condition:
            kwargs.update({
                con.get("type"):con.get("value")
            })
        return kwargs

if __name__ == "__main__":
    asyncio.run(create_task_async())