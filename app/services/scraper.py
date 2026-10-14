"""Playwright 采集主流程。

流程：按引擎分组任务 → 每个引擎复用同一个浏览器上下文（持久化 profile，
首次运行请把 GEO_HEADLESS=false 手动登录一次，之后 cookie 会保留）→
逐条提问 → 存 AIResponse 快照 → 立即交给 parser 解析归因。

注意事项：
- 全程同步 API，保持最简单。
- 遇到验证码/登录墙不会硬闯：抛错并把任务标记为 error，同时提示手动登录。
"""
from __future__ import annotations

import os
import random
import time
from datetime import datetime, timedelta

from playwright.sync_api import sync_playwright

from app.config import settings
from app.database import SessionLocal
from app.models import AIResponse, Keyword, SamplingTask
from app.services import engines
from app.services.parser import parse_response
from app.services.snapshot import write_snapshots_for_brands


class ScraperService:
    def __init__(self, session_factory=SessionLocal):
        self.session_factory = session_factory

    # ---------- 对外入口 ----------

    def run_task_ids(self, task_ids: list[int]) -> dict:
        """手动触发：按给定任务 id 列表执行一轮采样。返回 {任务id: ok/错误信息}。"""
        db = self.session_factory()
        try:
            tasks = db.query(SamplingTask).filter(SamplingTask.id.in_(task_ids)).all()
            return self._run_tasks(db, tasks)
        finally:
            db.close()

    def run_brand(self, brand_id: int) -> dict:
        """手动触发：某品牌名下全部任务（含上次失败的 error 任务，自动重试）。"""
        db = self.session_factory()
        try:
            tasks = (
                db.query(SamplingTask)
                .join(Keyword, SamplingTask.keyword_id == Keyword.id)
                .filter(Keyword.brand_id == brand_id, SamplingTask.status.in_(("active", "error")))
                .all()
            )
            return self._run_tasks(db, tasks)
        finally:
            db.close()

    def open_login_page(self, engine_name: str, wait_minutes: int = 5) -> str:
        """引导登录：有头模式打开该引擎首页，用户手动登录/过验证码后关窗。

        cookie 自动保存到 data/browser_profile/<引擎名>/，后续无头采集复用。
        返回提示文本。
        """
        adapter = engines.get_adapter(engine_name)
        profile_dir = os.path.join(settings.browser_profile_dir, engine_name)
        os.makedirs(profile_dir, exist_ok=True)
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )
            page = context.new_page()
            page.goto(adapter.url, timeout=60000)
            deadline = time.time() + wait_minutes * 60
            while time.time() < deadline:
                if context.is_closed():
                    break
                # 检测到输入框说明已登录可提问，继续等待用户关窗
                try:
                    if page.locator(adapter.input_selector).count() > 0:
                        time.sleep(1)
                        continue
                except Exception:
                    pass
                time.sleep(2)
            try:
                if not context.is_closed():
                    context.close()
            except Exception:
                pass
        return (f"[{engine_name}] 引导登录结束：请在浏览器里完成登录/验证码后直接关闭窗口，"
                f"cookie 已保存，之后可无头采样。若 5 分钟内没操作则已自动关闭。")

    def run_due_tasks(self) -> dict:
        """调度器调用：执行所有到期的任务（含上次失败的 error 任务，无需手动重置）。"""
        db = self.session_factory()
        try:
            due = []
            for task in db.query(SamplingTask).filter(SamplingTask.status.in_(("active", "error"))).all():
                if task.last_run_at is None:
                    due.append(task)
                elif datetime.utcnow() - task.last_run_at >= timedelta(hours=task.frequency_hours):
                    due.append(task)
            if not due:
                return {}
            return self._run_tasks(db, due)
        finally:
            db.close()

    # ---------- 内部实现 ----------

    def _cleanup_profile(self, profile_dir: str) -> None:
        """清理残留的 Playwright chromium 进程与 profile 锁。

        根因：采样异常/崩溃路径可能让 chromium 进程残留并占用 profile 目录
        （Windows 文件独占锁），导致后续所有采样 launch 失败（"另一个程序正在
        使用此文件"）。launch 失败后调用本函数清场再重试。
        """
        import subprocess

        try:
            subprocess.run(
                [
                    "powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | "
                    "Where-Object { $_.ExecutablePath -like '*ms-playwright*' -and "
                    "$_.CommandLine -like '*browser_profile*" + os.path.basename(profile_dir) + "*' } | "
                    "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }",
                ],
                capture_output=True, timeout=40,
            )
        except Exception:
            pass
        time.sleep(1)
        for name in ("SingletonLock", "SingletonCookie", "SingletonSocket", "lockfile"):
            try:
                os.remove(os.path.join(profile_dir, name))
            except Exception:
                pass

    def _run_tasks(self, db, tasks: list[SamplingTask]) -> dict:
        """按引擎分组执行，每个引擎一个持久化上下文。

        容错设计：
        - 登录页/验证码：wait_for_input 会等用户手动登录，不立即失败；
        - 浏览器窗口被关闭（如用户手动关窗）：检测到后自动重启浏览器，对该任务重试一次；
        - error 任务会自动被下次调度重跑。
        """
        result: dict[int, str] = {}
        groups: dict[str, list[SamplingTask]] = {}
        for task in tasks:
            groups.setdefault(task.engine, []).append(task)
        brand_ids: set[int] = set()  # 采样结束后为这些品牌写可见度快照（趋势/环比）

        with sync_playwright() as p:
            for engine_name, engine_tasks in groups.items():
                adapter = engines.get_adapter(engine_name)
                profile_dir = os.path.join(settings.browser_profile_dir, engine_name)
                os.makedirs(profile_dir, exist_ok=True)

                context = None

                def launch_ctx():
                    try:
                        return p.chromium.launch_persistent_context(
                            user_data_dir=profile_dir,
                            headless=settings.headless,
                            args=["--disable-blink-features=AutomationControlled"],
                        )
                    except Exception:
                        # 首次 launch 失败（典型：上次采样异常残留的 chromium 锁住 profile，
                        # 或本引擎上下文刚被关闭后 profile 锁未释放）→ 清理残留进程与锁后重试
                        self._cleanup_profile(profile_dir)
                        return p.chromium.launch_persistent_context(
                            user_data_dir=profile_dir,
                            headless=settings.headless,
                            args=["--disable-blink-features=AutomationControlled"],
                        )

                def ensure_context():
                    nonlocal context
                    if context is None or context.is_closed():
                        context = launch_ctx()
                    return context

                try:
                    for task in engine_tasks:
                        keyword = db.get(Keyword, task.keyword_id)
                        if keyword is None:
                            result[task.id] = "关键词不存在"
                            task.status = "error"
                            db.commit()
                            continue
                        brand_ids.add(keyword.brand_id)

                        def do_one() -> tuple[str, list[str]]:
                            page = ensure_context().new_page()
                            return adapter.ask(page, keyword.query_text)

                        try:
                            text, sources = do_one()
                            self._store_response(db, task, keyword, engine_name, text)
                            result[task.id] = f"ok（{len(text)} 字，{len(sources)} 个引用）"
                            time.sleep(random.uniform(3, 7))  # 错峰节流，避免触发风控
                        except Exception as exc:
                            err = str(exc)
                            if "closed" in err.lower():
                                # 浏览器被关闭：重启后重试一次
                                try:
                                    text, sources = do_one()
                                    self._store_response(db, task, keyword, engine_name, text)
                                    result[task.id] = f"ok（浏览器重启后成功，{len(text)} 字）"
                                    time.sleep(random.uniform(3, 7))
                                except Exception as exc2:
                                    task.status = "error"
                                    task.last_error = str(exc2)[:500]
                                    result[task.id] = f"失败(重试): {exc2}"
                            else:
                                task.status = "error"
                                task.last_error = err[:500]
                                result[task.id] = f"失败: {exc}"
                        db.commit()
                finally:
                    if context is not None and not context.is_closed():
                        context.close()
        # 采样轮结束：为涉及品牌写可见度快照（趋势/环比数据源）
        try:
            write_snapshots_for_brands(db, list(brand_ids))
        except Exception:
            pass
        return result

    def _store_response(self, db, task: SamplingTask, keyword: Keyword,
                        engine_name: str, text: str) -> None:
        """保存 AIResponse 快照并立即解析归因，更新任务状态。

        事务纪律（避免 SQLite 锁库）：快照先 commit 释放写锁，LLM 解析用独立
        连接短事务执行，绝不在解析耗时期间持有写锁。
        """
        resp = AIResponse(
            task_id=task.id,
            engine=engine_name,
            model=engine_name,
            prompt_text=keyword.query_text,
            response_text=text,
            sampled_at=datetime.utcnow(),
        )
        db.add(resp)
        db.commit()  # 先提交快照，释放写锁
        db.refresh(resp)

        # LLM 解析用独立连接（写锁窗口只覆盖解析写入本身）
        parse_db = self.session_factory()
        try:
            parse_response(resp.id, parse_db)
        finally:
            parse_db.close()

        task.last_run_at = datetime.utcnow()
        task.last_error = None
        task.status = "active"


scraper_service = ScraperService()
