# -*- coding: utf-8 -*-
"""把两篇公众号文章登记进品牌6内容清单（一次性脚本）"""
import json
import urllib.request

URLS = [
    ('https://mp.weixin.qq.com/s/g36mTBc3uLK1qfZWdxUafw', 'ModelMix 模方：帮你选择最优模型'),
    ('https://mp.weixin.qq.com/s/RReFUwece0qqv_-09VuCNg', '如何分清真攻略还是假种草？'),
]


def post(url, title):
    body = {'brand_id': 6, 'url': url, 'platform': '微信公众号', 'title': title}
    r = urllib.request.Request('http://127.0.0.1:8000/api/account/content-items',
                               data=json.dumps(body).encode(), method='POST',
                               headers={'Content-Type': 'application/json'})
    try:
        resp = urllib.request.urlopen(r, timeout=30)
        return json.loads(resp.read())
    except Exception as e:
        return {'ERR': str(e)}


def get(path):
    try:
        resp = urllib.request.urlopen('http://127.0.0.1:8000' + path, timeout=30)
        return json.loads(resp.read())
    except Exception as e:
        return {'ERR': str(e)}


def main():
    for u, t in URLS:
        print(post(u, t))
    print('summary:', get('/api/account/summary/6'))


if __name__ == '__main__':
    main()
