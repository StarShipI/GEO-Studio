# -*- coding: utf-8 -*-
"""查看 AI对齐研究室 采样的引用与回答（一次性脚本）"""
import sqlite3


def main():
    conn = sqlite3.connect('data/geo.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute('PRAGMA table_info(ai_responses)')
    print('resp cols:', [r[1] for r in cur.fetchall()])
    cur.execute('PRAGMA table_info(citations)')
    print('cit cols:', [r[1] for r in cur.fetchall()])
    cur.execute('''
        SELECT a.task_id, a.prompt_text, a.sampled_at,
               substr(a.response_text, 1, 160) AS head
        FROM ai_responses a
        WHERE a.task_id IN (91,92,93,94,95)
        ORDER BY a.sampled_at
    ''')
    rows = cur.fetchall()
    for r in rows:
        print('=' * 70)
        print('Q:', r['prompt_text'], '|', (r['sampled_at'] or '')[:19])
        print('head:', r['head'])
        cur.execute('SELECT url, substr(snippet,1,70) AS sn FROM citations WHERE response_id=?',
                    (r['task_id'],))
        for c in cur.fetchall():
            print('   cite:', c['url'], '|', c['sn'])
    conn.close()


if __name__ == '__main__':
    main()
