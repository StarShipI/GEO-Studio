"""单独测试某个引擎适配器的端到端采集（新引擎/改选择器后用它验证）。

用法：python scripts/test_engine.py wenxin
"""
from __future__ import annotations

import os
import sys

from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.config import settings  # noqa: E402
from app.services import engines  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        print(f"用法: python scripts/test_engine.py <引擎名>；可用: {list(engines.REGISTRY)}")
        sys.exit(1)
    name = sys.argv[1]
    adapter = engines.get_adapter(name)
    profile = os.path.join(settings.browser_profile_dir, name)
    os.makedirs(profile, exist_ok=True)

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            profile, headless=settings.headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = ctx.new_page()
        try:
            text, sources = adapter.ask(page, "澄心咖啡怎么样")
            print(f"== {name} 采集成功 ==")
            print(f"回答长度: {len(text)}")
            print(f"回答开头: {text[:120]}")
            print(f"引用链接数: {len(sources)}")
        except Exception as exc:
            print(f"== {name} 采集失败 ==")
            print(str(exc)[:300])
            page.screenshot(path=f"test_{name}_fail.png")
            print(f"失败截图已保存 test_{name}_fail.png")
        finally:
            ctx.close()


if __name__ == "__main__":
    main()
