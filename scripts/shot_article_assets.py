# -*- coding: utf-8 -*-
"""为公众号文章截配图 v2：账号视图切到品牌6 + 控制台（一次性脚本）"""
import os
from playwright.sync_api import sync_playwright

OUT = r'reports\AI对齐研究室\assets'
os.makedirs(OUT, exist_ok=True)


def main():
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={'width': 1440, 'height': 900})

        # 1. 账号视图：切到 AI对齐研究室
        try:
            pg.goto('http://127.0.0.1:8000/account', wait_until='domcontentloaded', timeout=20000)
            pg.wait_for_timeout(2500)
            try:
                pg.select_option('select', label='AI对齐研究室', timeout=3000)
                pg.wait_for_timeout(2000)
            except Exception as e:
                print('select skip:', e)
            pg.screenshot(path=os.path.join(OUT, 'ui_account.png'), full_page=True)
            print('ok ui_account')
        except Exception as e:
            print('fail account:', e)

        # 2. 控制台
        try:
            pg.goto('http://127.0.0.1:8000/console', wait_until='domcontentloaded', timeout=20000)
            pg.wait_for_timeout(2500)
            pg.screenshot(path=os.path.join(OUT, 'ui_console.png'), full_page=True)
            print('ok ui_console')
        except Exception as e:
            print('fail console:', e)

        pg.close()
        b.close()


if __name__ == '__main__':
    main()
