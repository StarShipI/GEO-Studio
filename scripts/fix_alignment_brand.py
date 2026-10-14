# -*- coding: utf-8 -*-
"""AI对齐研究室：删抖音误登记内容 + 查品牌6任务（一次性维护脚本）"""
import json
import sqlite3
import urllib.request


def req(method, path):
    r = urllib.request.Request('http://127.0.0.1:8000' + path, data=b'', method=method)
    try:
        resp = urllib.request.urlopen(r, timeout=30)
        return json.loads(resp.read())
    except Exception as e:
        return {'ERR': str(e)}


def main():
    print('del16:', req('DELETE', '/api/account/content-items/16'))
    print('del17:', req('DELETE', '/api/account/content-items/17'))

    conn = sqlite3.connect('data/geo.db')
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    print('tables:', [r[0] for r in cur.fetchall()])
    cur.execute('PRAGMA table_info(sampling_tasks)')
    print('task cols:', [r[1] for r in cur.fetchall()])
    cur.execute('SELECT t.id, t.engine, t.status, k.query_text '
                'FROM sampling_tasks t JOIN keywords k ON t.keyword_id=k.id '
                'WHERE k.brand_id=6 ORDER BY t.id')
    print('--- brand6 all tasks ---')
    for r in cur.fetchall():
        print('task', r[0], '|', r[1], '|', r[2], '|', (r[3] or '')[:24])
    cur.execute('SELECT id, brand_id, url, platform FROM content_items WHERE brand_id=6')
    print('items b6:', cur.fetchall())
    conn.close()


if __name__ == '__main__':
    main()
