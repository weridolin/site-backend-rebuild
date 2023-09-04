import requests

token = None
repo_uri = None
commit_content =None
author=None
commit_id=None
finish_time = None

def get_token(username,password):
    global token
    url = "https://www.weridolin.cn/usercenter/api/v1/login"

    payload = {'count': username,'password': password}
    response = requests.request("POST", url, data=payload)
    if response.status_code == 200:
        print('登录成功')
        token = response.json().get('data').get('access_token')
    else:
        exit(1)

def create_update_log():
    import requests
    import json

    url = "http://www.weridolin.cn/home/api/v1/updatelog"

    payload = json.dumps({
    "repo_uri": repo_uri,
    "commit_content": commit_content,
    "author": author,
    "is_finish": True,
    "commit_id": commit_id,
    "finish_time":finish_time
    })
    headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json',
    }
    print(payload,">>>")

    response = requests.request("POST", url, headers=headers, data=payload)

    if 300 > response.status_code >= 200:
        print('更新日志创建成功')
    else:
        print(response.text,">>>")
        print('更新日志创建失败')
        exit(1)


if __name__ == '__main__':
    import sys
    print(sys.argv)
    if len(sys.argv) < 7:
        print('参数不足')
        exit(1)
    username = sys.argv[1]
    password = sys.argv[2]
    repo_uri = sys.argv[7]
    commit_content = sys.argv[3]
    author = sys.argv[6]
    commit_id = sys.argv[4]
    finish_time = sys.argv[5]
    get_token(username,password)
    create_update_log()