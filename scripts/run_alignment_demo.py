# -*- coding: utf-8 -*-
"""AI对齐研究室：删抖音内容 + 触发 wenxin 采样（一次性脚本）"""
import json
import time
import urllib.request


def req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else b''
    r = urllib.request.Request('http://127.0.0.1:8000' + path, data=data, method=method,
                               headers={'Content-Type': 'application/json'})
    try:
        resp = urllib.request.urlopen(r, timeout=60)
        return json.loads(resp.read())
    except Exception as e:
        return {'ERR': str(e)}


def main():
    print('del14:', req('DELETE', '/api/account/content-items/14'))
    print('del15:', req('DELETE', '/api/account/content-items/15'))
    print('run 91-95:', req('POST', '/api/sampling/run', {'task_ids': [91, 92, 93, 94, 95]}))
    time.sleep(110)
    tasks = req('GET', '/api/sampling/tasks?limit=500')
    for t in tasks:
        if t.get('id', 0) in range(91, 96):
            print('task', t['id'], t['status'], '|', (t.get('last_error') or '')[:70])
    s = req('GET', '/api/account/summary/6')
    print('summary6: content=%s cited=%s rate=%s total=%s' % (
        s.get('content_count'), s.get('cited_content_count'), s.get('citation_rate'), s.get('total_citations')))
    for it in s.get('items', []):
        print('  cited:', it['url'][:50], 'n:', it['citation_count'])
    print('uncited:', len(s.get('uncited', [])))


if __name__ == '__main__':
    main()
