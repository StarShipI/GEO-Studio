"""批量探测 AI 引擎页面结构（加新引擎 / 引擎改版后用它拿到真实选择器）。

用法：python scripts/probe_engines.py [引擎名...]
不传参数则探测全部。
"""
from __future__ import annotations

import sys

from playwright.sync_api import sync_playwright

# 候选引擎清单：加新引擎时在这里加一行，然后跑本脚本看结构
TARGETS = {
    "deepseek": "https://chat.deepseek.com/",
    "yuanbao": "https://yuanbao.tencent.com/chat/",
    "wenxin": "https://yiyan.baidu.com/",
    "tongyi": "https://tongyi.aliyun.com/",
}


def probe(p: sync_playwright, name: str, url: str) -> None:
    print(f"\n===== {name} ({url}) =====")
    try:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(6000)
        print("当前 URL:", page.url)
        print("标题:", page.title())

        tas = page.eval_on_selector_all(
            "textarea",
            "els => els.map(e => ({ph: e.placeholder, cls: e.className.toString().slice(0,50)}))",
        )
        print("textarea 输入框:", tas[:4] if tas else "无")

        eds = page.eval_on_selector_all(
            "[contenteditable='true']",
            "els => els.map(e => ({cls: e.className.toString().slice(0,60), ph: e.getAttribute('data-placeholder')}))",
        )
        print("contenteditable:", eds[:4] if eds else "无")

        ins = page.eval_on_selector_all(
            "input:not([type='hidden'])",
            "els => els.map(e => ({ph: e.placeholder, cls: e.className.toString().slice(0,40)}))",
        )
        print("可见 input:", ins[:6] if ins else "无")

        for sel in ["div[class*='markdown']", "div[class*='message']", "div[class*='answer']", "div[class*='content']"]:
            n = page.eval_on_selector_all(sel, "els => els.length")
            print(f"回答区候选 {sel}: {n}")
        browser.close()
    except Exception as exc:
        print("探测失败:", str(exc)[:200])


def main() -> None:
    names = sys.argv[1:] or list(TARGETS)
    with sync_playwright() as p:
        for name in names:
            if name not in TARGETS:
                print(f"未知引擎 {name}，可选: {list(TARGETS)}")
                continue
            probe(p, name, TARGETS[name])


if __name__ == "__main__":
    main()
