# -*- coding: utf-8 -*-
"""控制台 Tab 冒烟测试：逐个点击 Tab，收集 console 错误并抽查关键元素。"""
import json, sys, time

from playwright.sync_api import sync_playwright

HTML = r"C:\Users\98525\DoubaoWork\chats\2026-10-01\new-chat\geo-studio\web\console.html"
TABS = ["brands", "tasks", "reports", "alerts"]
# 每个 Tab 的验收选择器
CHECKS = {
    "brands": "#brandList li, #detailBox, #fName",
    "tasks": "#taskBox table, #taskTotal",
    "reports": "#repBox, #tab-reports .ops button",
    "alerts": "#alertBox",
}

out = {}
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    errs = []
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("file:///" + HTML.replace("\\", "/"))
    pg.wait_for_timeout(2500)

    for tab in TABS:
        pg.click(f'.tab[data-tab="{tab}"]')
        pg.wait_for_timeout(1200)
        present = pg.eval_on_selector_all(CHECKS[tab], "els => els.length")
        txt = pg.evaluate(f"() => document.getElementById('tab-{tab}').innerText.slice(0, 120)")
        out[tab] = {"elements": present, "text": txt.replace("\n", " ")[:110]}

    b.close()

out["console_errors"] = errs[:8]
print(json.dumps(out, ensure_ascii=False, indent=1))
