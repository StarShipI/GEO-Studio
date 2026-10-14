# -*- coding: utf-8 -*-
"""v3：用 value=6 切品牌后截账号视图（一次性脚本）"""
import os
from playwright.sync_api import sync_playwright

OUT = r'reports\AI对齐研究室\assets'
os.makedirs(OUT, exist_ok=True)


def main():
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={'width': 1440, 'height': 900})
        pg.goto('http://127.0.0.1:8000/account', wait_until='domcontentloaded', timeout=20000)
        pg.wait_for_timeout(2500)
        opts = pg.eval_on_selector('#brandSel', 'el => Array.from(el.options).map(o => o.value + ":" + o.text)')
        print('options:', opts)
        pg.evaluate('''() => {
          const sel = document.getElementById('brandSel');
          if (!Array.from(sel.options).some(o => o.value === '6')) {
            const o = document.createElement('option');
            o.value = '6'; o.text = 'AI对齐研究室';
            sel.appendChild(o);
          }
          sel.value = '6';
          sel.dispatchEvent(new Event('change'));
        }''')
        pg.wait_for_timeout(2500)
        pg.screenshot(path=os.path.join(OUT, 'ui_account.png'), full_page=True)
        print('ok ui_account(brand6)')
        pg.close()
        b.close()


if __name__ == '__main__':
    main()
