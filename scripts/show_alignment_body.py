# -*- coding: utf-8 -*-
"""看 91/92 公众号语境回答正文（一次性脚本）"""
import sqlite3


def main():
    conn = sqlite3.connect('data/geo.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute('SELECT id, task_id, prompt_text, response_text, sampled_at '
                'FROM ai_responses WHERE id IN (35,36) ORDER BY id')
    rows = cur.fetchall()
    print('rows:', len(rows))
    parts = []
    for r in rows:
        parts.append('=' * 72)
        parts.append('Q: %s | %s' % (r['prompt_text'], (r['sampled_at'] or '')[:19]))
        t = r['response_text'] or ''
        lines = [l.strip() for l in t.splitlines() if l.strip()]
        body = [l for l in lines if not l.startswith(('百度首页', '网页', '图片', '更多', '登录'))]
        parts.append('\n'.join(body[:40]))
    with open('body_out.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(parts))
    conn.close()


if __name__ == '__main__':
    main()
