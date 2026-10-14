"""探测文心一言提问后的回答区（验证游客模式是否可用）。"""
from __future__ import annotations

from playwright.sync_api import sync_playwright

URL = "https://wenxin.baidu.com/"


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(5000)

        box = page.locator("textarea.ci-textarea").first
        box.click()
        page.keyboard.type("澄心咖啡怎么样", delay=40)
        page.keyboard.press("Enter")
        page.wait_for_timeout(20_000)

        print("URL:", page.url)
        big = page.eval_on_selector_all(
            "div[class]",
            "els => els.filter(e => e.innerText.length > 40).slice(0, 12).map(e => ({cls: e.className.toString().slice(0, 80), len: e.innerText.length, head: e.innerText.slice(0, 40)}))",
        )
        print("含长文本 div:", big)
        page.screenshot(path="probe_wenxin.png")
        browser.close()
    print("截图已保存 probe_wenxin.png")


if __name__ == "__main__":
    main()
