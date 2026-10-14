# -*- coding: utf-8 -*-
"""下载两篇公众号文章 + 提取标题正文（一次性脚本）"""
import html
import re
import urllib.request

URLS = {
    'a': 'https://mp.weixin.qq.com/s/g36mTBc3uLK1qfZWdxUafw',
    'b': 'https://mp.weixin.qq.com/s/RReFUwece0qqv_-09VuCNg',
}


def fetch(k, u):
    req = urllib.request.Request(u, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/120.0 Safari/537.36'})
    raw = urllib.request.urlopen(req, timeout=30).read().decode('utf-8', errors='ignore')
    open(f'data/wechat/{k}.html', 'w', encoding='utf-8').write(raw)
    t = re.search(r'<meta property="og:title" content="([^"]+)"', raw)
    desc = re.search(r'<meta property="og:description" content="([^"]+)"', raw)
    body = re.search(r'<div class="rich_media_content[^"]*"[^>]*>(.*?)</div>\s*<script', raw, re.S)
    text = ''
    if body:
        text = re.sub(r'<[^>]+>', '\n', body.group(1))
        text = html.unescape(text)
        text = '\n'.join(l.strip() for l in text.splitlines() if l.strip())
    return {
        'title': t.group(1) if t else '?',
        'desc': desc.group(1) if desc else '',
        'html_len': len(raw),
        'text': text,
    }


def main():
    for k, u in URLS.items():
        info = fetch(k, u)
        open(f'data/wechat/{k}.txt', 'w', encoding='utf-8').write(
            'TITLE: ' + info['title'] + '\nDESC: ' + info['desc'] + '\n\n' + info['text'])
        print(k, '|', info['title'], '| text len', len(info['text']))


if __name__ == '__main__':
    main()
