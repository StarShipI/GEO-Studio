# -*- coding: utf-8 -*-
"""把两张图解 HTML 截成 PNG（一次性脚本）"""
import os
from playwright.sync_api import sync_playwright

BASE = r'C:\Users\98525\DoubaoWork\chats\2026-10-01\new-chat\geo-studio\reports\AI对齐研究室\assets'
FILES = ['diagram_pipeline.html', 'diagram_views.html']


def main():
    with sync_playwright() as p:
        b = p.chromium.launch()
        for f in FILES:
            pg = b.new_page(viewport={'width': 1200, 'height': 500})
            pg.goto('file:///' + os.path.join(BASE, f).replace('\\', '/'))
            pg.wait_for_timeout(500)
            out = os.path.join(BASE, f.replace('.html', '.png'))
            pg.screenshot(path=out)
            print('ok', out)
            pg.close()
        b.close()


if __name__ == '__main__':
    main()
