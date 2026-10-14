# -*- coding: utf-8 -*-
"""查看公众号语境采样的回答与引用（一次性脚本，修正游标）"""
import sqlite3


def main():
    conn = sqlite3.connect('data/geo.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute('''
        SELECT a.id, a.task_id, a.prompt_text, a.sampled_at, substr(a.response_text, 1, 600) AS head
        FROM ai_responses a
        WHERE a.task_id IN (91,92,93,94,95)
        ORDER BY a.sampled_at
    ''')
    rows = cur.fetchall()
    for r in rows:
        print('=' * 72)
        print('Q:', r['prompt_text'], '|', (r['sampled_at'] or '')[:19])
        print(r['head'])
        cur2 = conn.cursor()
        cur2.execute('SELECT url, substr(snippet,1,80) AS sn FROM citations WHERE response_id=?', (r['id'],))
        cites = cur2.fetchall()
        if not cites:
            print('  (回答中无引用链接)')
        for c in cites:
            print('  cite:', c['url'][:80], '|', c['sn'])
    conn.close()


if __name__ == '__main__':
    main()
