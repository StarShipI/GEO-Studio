# -*- coding: utf-8 -*-
"""查 ai_responses 最新记录（一次性脚本）"""
import sqlite3


def main():
    conn = sqlite3.connect('data/geo.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute('SELECT id, task_id, engine, prompt_text, sampled_at, length(response_text) AS ln '
                'FROM ai_responses ORDER BY id DESC LIMIT 12')
    for r in cur.fetchall():
        print(r['id'], '| task', r['task_id'], '|', r['engine'], '|', (r['prompt_text'] or '')[:30],
              '|', (r['sampled_at'] or '')[:19], '| len', r['ln'])
    conn.close()


if __name__ == '__main__':
    main()
