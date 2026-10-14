"""探测 Kimi 回答区结构：输入一个简单问题，等回答生成后 dump 页面元素。"""
from __future__ import annotations

import sys

from playwright.sync_api import sync_playwright

URL = "https://www.kimi.com/"


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(5000)

        editor = page.locator("div[class*='chat-input-editor']").first
        editor.click()
        page.keyboard.type("1+1等于几？", delay=50)
        page.keyboard.press("Enter")
        page.wait_for_timeout(18_000)

        print("== URL:", page.url)
        msgs = page.eval_on_selector_all(
            "[class*='message']",
            "els => els.map(e => ({cls: e.className.toString().slice(0,90), len: e.innerText.length, head: e.innerText.slice(0,50)}))",
        )
        print("== message 类元素:", msgs)

        big = page.eval_on_selector_all(
            "div[class]",
            "els => els.filter(e => e.innerText.length > 80).slice(0,12).map(e => ({cls: e.className.toString().slice(0,90), len: e.innerText.length}))",
        )
        print("== 含长文本的 div:", big)

        page.screenshot(path="probe_ask.png")
        browser.close()
    print("截图已保存 probe_ask.png")


if __name__ == "__main__":
    main()
