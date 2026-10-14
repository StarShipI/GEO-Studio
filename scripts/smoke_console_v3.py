# -*- coding: utf-8 -*-
"""控制台 v3 冒烟：登录/探活按钮、任务操作列、导出、打开报告、告警阈值卡。"""
import json

from playwright.sync_api import sync_playwright

HTML = r"C:\Users\98525\DoubaoWork\chats\2026-10-01\new-chat\geo-studio\web\console.html"

out = {}
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    errs = []
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("file:///" + HTML.replace("\\", "/"))
    pg.wait_for_timeout(2500)

    # 采样任务 Tab
    pg.click('.tab[data-tab="tasks"]')
    pg.wait_for_timeout(1500)
    out["tasks"] = {
        "login_btns": pg.eval_on_selector_all("button[data-login]", "els => els.length"),
        "probe_btn": pg.eval_on_selector_all("button[data-probe]", "els => els.length"),
        "toggle_btns": pg.eval_on_selector_all("button[data-tg]", "els => els.length"),
        "freq_selects": pg.eval_on_selector_all("select[data-freq]", "els => els.length"),
        "sample_btn": pg.eval_on_selector_all("#tab-tasks .ops button[data-act]", "els => els.length"),
    }

    # 报告 Tab
    pg.click('.tab[data-tab="reports"]')
    pg.wait_for_timeout(1200)
    out["reports"] = {
        "export_btn": pg.eval_on_selector_all("button[data-act='export']", "els => els.length"),
        "open_links": pg.eval_on_selector_all("#repBox a[data-open]", "els => els.length"),
        "open_path0": pg.eval_on_selector_all("#repBox a[data-open]", "els => els.length ? els[0].getAttribute('data-open') : ''"),
    }

    # 告警 Tab
    pg.click('.tab[data-tab="alerts"]')
    pg.wait_for_timeout(1200)
    out["alerts"] = {
        "neg_input": pg.eval_on_selector_all("#aNeg", "els => els.length"),
        "drop_input": pg.eval_on_selector_all("#aDrop", "els => els.length"),
        "save_btn": pg.eval_on_selector_all("#btnAlertCfg", "els => els.length"),
        "neg_val": pg.eval_on_selector_all("#aNeg", "els => els.length ? els[0].value : ''"),
        "drop_val": pg.eval_on_selector_all("#aDrop", "els => els.length ? els[0].value : ''"),
    }

    b.close()

out["console_errors"] = errs[:6]
print(json.dumps(out, ensure_ascii=False, indent=1))
