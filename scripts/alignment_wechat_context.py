# -*- coding: utf-8 -*-
"""AI对齐研究室：查询词加公众号语境 + 重采样（一次性脚本）"""
import json
import sqlite3
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
    conn = sqlite3.connect('data/geo.db')
    cur = conn.cursor()
    # 品牌主体查询词加"微信公众号"语境（品牌词 + 别名"对齐研究室"；"AI对齐"保留为话题查询）
    cur.execute("UPDATE keywords SET query_text = REPLACE(query_text, 'AI对齐研究室 ', '微信公众号「AI对齐研究室」 ') "
                "WHERE brand_id=6 AND type='brand' AND query_text LIKE 'AI对齐研究室 %'")
    cur.execute("UPDATE keywords SET query_text = REPLACE(query_text, '对齐研究室 ', '微信公众号「对齐研究室」 ') "
                "WHERE brand_id=6 AND type='brand' AND query_text LIKE '对齐研究室 %'")
    conn.commit()
    cur.execute("SELECT id, query_text FROM keywords WHERE brand_id=6 AND type='brand' ORDER BY id")
    for r in cur.fetchall():
        print('kw', r[0], '|', r[1])
    conn.close()

    print('run:', req('POST', '/api/sampling/run', {'task_ids': [91, 92, 93, 94, 95]}))
    time.sleep(115)
    tasks = req('GET', '/api/sampling/tasks?limit=500')
    for t in tasks:
        if t.get('id', 0) in range(91, 96):
            print('task', t['id'], t['status'], '|', (t.get('last_error') or '')[:70])


if __name__ == '__main__':
    main()
