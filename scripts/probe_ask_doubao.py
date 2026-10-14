"""探测豆包回答区结构：输入问题，等回答生成后 dump 页面元素。"""
from __future__ import annotations

from playwright.sync_api import sync_playwright

URL = "https://www.doubao.com/chat/"


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(5000)

        ed = page.locator("div[class*='ProseMirror']").first
        ed.click()
        page.keyboard.type("澄心咖啡怎么样", delay=40)
        page.keyboard.press("Enter")
        page.wait_for_timeout(20_000)

        print("== URL:", page.url)
        big = page.eval_on_selector_all(
            "div[class]",
            "els => els.filter(e => e.innerText.length > 50).slice(0, 15).map(e => ({cls: e.className.toString().slice(0, 90), len: e.innerText.length, head: e.innerText.slice(0, 40)}))",
        )
        print("== 含长文本的 div:", big)
        page.screenshot(path="probe_doubao_ask.png")
        browser.close()
    print("截图已保存 probe_doubao_ask.png")


if __name__ == "__main__":
    main()
