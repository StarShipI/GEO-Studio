"""探测 AI 引擎页面结构：找出当前输入框/回答区选择器（引擎改版后用它修复 engines.py）。

用法：python scripts/probe_engine.py [kimi|doubao]
"""
from __future__ import annotations

import sys

from playwright.sync_api import sync_playwright

TARGETS = {
    "kimi": "https://www.kimi.com/",
    "doubao": "https://www.doubao.com/",
}


def probe(url: str) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(8000)
        print("== 当前 URL:", page.url)
        print("== 页面标题:", page.title())

        tas = page.eval_on_selector_all(
            "textarea",
            "els => els.map(e => ({ph: e.placeholder, cls: e.className.slice(0,60)}))",
        )
        print("== textarea 输入框:", tas[:5])

        eds = page.eval_on_selector_all(
            "[contenteditable='true']",
            "els => els.map(e => ({cls: e.className.slice(0,60), ph: e.getAttribute('data-placeholder')}))",
        )
        print("== contenteditable 输入框:", eds[:5])

        ins = page.eval_on_selector_all(
            "input:not([type='hidden'])",
            "els => els.map(e => ({ph: e.placeholder, type: e.type, cls: e.className.slice(0,40)}))",
        )
        print("== 可见 input:", ins[:10])

        # 常见回答容器
        for sel in ["div[class*='markdown']", "div[class*='answer']", "div[class*='response']", "[class*='message']"]:
            n = page.eval_on_selector_all(sel, "els => els.length")
            print(f"== 容器候选 {sel} 数量:", n)

        # 是否有登录/二维码相关元素
        login = page.eval_on_selector_all(
            "[class*='login'],[class*='scan'],[class*='qrcode'],[class*='verify'],[class*='captcha']",
            "els => els.map(e => e.className.toString().slice(0,60))",
        )
        print("== 登录/验证元素:", login[:5] if login else "无")

        page.screenshot(path="probe_shot.png", full_page=False)
        browser.close()
    print("== 页面截图已保存到 probe_shot.png（项目根目录）")


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "kimi"
    if name not in TARGETS:
        print(f"未知引擎: {name}，可选 {list(TARGETS)}")
        sys.exit(1)
    probe(TARGETS[name])
