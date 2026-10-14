# -*- coding: utf-8 -*-
"""引擎探活：检查各 AI 引擎网页版当前是否可用（登录态/风控/改版）。"""
from __future__ import annotations

import os
import time

from playwright.sync_api import sync_playwright

from app.config import settings
from app.services import engines


def probe_engine(engine: str, timeout_seconds: int = 15) -> dict:
    """单引擎探活：打开页面检查输入框是否可达。

    返回 {"engine", "ok", "note"}。ok=False 的 note 说明原因（未登录/风控/改版）。
    """
    adapter = engines.get_adapter(engine)
    profile_dir = os.path.join(settings.browser_profile_dir, engine)
    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            page = context.new_page()
            page.goto(adapter.url, wait_until="domcontentloaded", timeout=timeout_seconds * 1000)
            deadline = time.time() + timeout_seconds
            found = False
            err = ""
            while time.time() < deadline:
                try:
                    if page.locator(adapter.input_selector).count() > 0:
                        found = True
                        break
                except Exception as e:
                    err = str(e)[:80]
                time.sleep(1.5)
            context.close()
        if found:
            return {"engine": engine, "ok": True,
                    "note": "页面可达，输入框可见（登录态以采样结果为准；未登录的引擎请先引导登录）"}
        return {"engine": engine, "ok": False,
                "note": f"输入框未出现（{err or '被登录页/风控/改版拦截'}）——先点「引导登录」"}
    except Exception as exc:
        return {"engine": engine, "ok": False, "note": f"打开失败：{str(exc)[:120]}"}


def probe_all() -> list[dict]:
    """逐个探测已注册引擎（每个最多约 15s，4 个引擎约 1 分钟内完成）。"""
    results = []
    for engine in engines.REGISTRY:
        try:
            results.append(probe_engine(engine))
        except Exception as exc:
            results.append({"engine": engine, "ok": False, "note": f"异常：{str(exc)[:100]}"})
    return results
