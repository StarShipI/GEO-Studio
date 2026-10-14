# -*- coding: utf-8 -*-
"""AI对齐研究室：生成账号周报（修正端点）（一次性脚本）"""
import json
import sqlite3
import urllib.request


def req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else b''
    r = urllib.request.Request('http://127.0.0.1:8000' + path, data=data, method=method,
                               headers={'Content-Type': 'application/json'})
    try:
        resp = urllib.request.urlopen(r, timeout=120)
        return json.loads(resp.read())
    except Exception as e:
        return {'ERR': str(e)}


def main():
    print('report:', req('POST', '/api/reports/account/6'))
    conn = sqlite3.connect('data/geo.db')
    cur = conn.cursor()
    cur.execute('PRAGMA table_info(reports)')
    print('reports cols:', [r[1] for r in cur.fetchall()])
    cur.execute("SELECT * FROM reports WHERE brand_id=6 ORDER BY id DESC LIMIT 2")
    for r in cur.fetchall():
        print('row:', r)
    conn.close()


if __name__ == '__main__':
    main()
