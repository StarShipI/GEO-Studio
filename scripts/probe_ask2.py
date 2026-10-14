"""端到端探测：直接用引擎适配器问一次 Kimi，验证完整采集链路。"""
from __future__ import annotations

import os
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.config import settings  # noqa: E402
from app.services import engines  # noqa: E402


def main() -> None:
    adapter = engines.get_adapter("kimi")
    profile = os.path.join(settings.browser_profile_dir, "kimi")
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            profile, headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = ctx.new_page()
        try:
            text, sources = adapter.ask(page, "澄心咖啡怎么样")
            print("== 采集成功 ==")
            print("回答长度:", len(text))
            print("回答开头:", text[:150])
            print("引用链接数:", len(sources))
            print("引用:", sources[:5])
        except Exception as exc:
            print("== 采集失败 ==")
            print(str(exc))
            page.screenshot(path="probe_fail.png")
            print("失败截图已保存 probe_fail.png")
        finally:
            ctx.close()


if __name__ == "__main__":
    main()
