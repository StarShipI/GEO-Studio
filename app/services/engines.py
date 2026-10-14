"""AI 引擎适配器。

核心思想：每个引擎一个类，把「打开页面 → 输入问题 → 等待回答稳定 → 取出正文和引用」封装起来。
选择器是初版占位，页面结构随时会变，失效时按 README「选择器失效怎么办」一节用 F12 调整即可，
只需改这一个文件，不用动采集主流程。

新增引擎三步：
1. 继承 EngineAdapter；
2. 填 url 与三个选择器（以及可选的引用选择器）；
3. 在 REGISTRY 里注册 name。
"""
from __future__ import annotations

import time


class EngineAdapter:
    """适配器基类。子类只负责页面结构与选择器，通用等待逻辑在这里。"""

    name: str = "base"
    url: str = ""
    input_selector: str = ""
    submit_selector: str = ""
    answer_selector: str = ""
    source_selector: str = ""   # 可空：引用链接列表的选择器

    def build_prompt(self, query: str) -> str:
        """返回真正输入给引擎的问题（默认原样；如需加指令可在子类改写）。"""
        return query

    def submit(self, page, question: str) -> None:
        """输入并提交问题。用「点击可见输入框 + 键盘输入 + 回车」，兼容 textarea 和 contenteditable。
        点击被遮罩挡住时自动滚动并强制点击。
        """
        box = self._visible_input(page)
        try:
            box.click(timeout=5000)
        except Exception:
            try:
                box.scroll_into_view_if_needed(timeout=3000)
            except Exception:
                pass
            box.click(force=True, timeout=5000)
        page.keyboard.type(question, delay=30)
        page.keyboard.press("Enter")

    def _visible_input(self, page):
        """输入框可能有多个匹配（如侧边栏搜索框），优先取可见的那个。"""
        for loc in page.locator(self.input_selector).all():
            try:
                if loc.is_visible():
                    return loc
            except Exception:
                continue
        return page.locator(self.input_selector).first

    def handle_modals(self, page) -> None:
        """关闭可能遮挡输入的弹窗（子类按需覆写）。"""
        pass

    def wait_for_input(self, page, wait_login_seconds: int = 180) -> None:
        """等待输入框出现。若 30s 内未出现，说明可能被登录页/验证码拦截：
        打印提示并在浏览器窗口等待用户手动登录，检测到输入框后自动继续。
        """
        first_deadline = time.time() + 30
        while time.time() < first_deadline:
            if page.locator(self.input_selector).count() > 0:
                return
            time.sleep(1)
        print(f"[{self.name}] 未检测到输入框，可能是登录/验证页——请在弹窗里手动登录，最长等待 {wait_login_seconds}s…")
        deadline = time.time() + wait_login_seconds
        while time.time() < deadline:
            try:
                if page.locator(self.input_selector).count() > 0:
                    print(f"[{self.name}] 检测到输入框，继续采集")
                    return
            except Exception:
                pass
            time.sleep(2)
        raise TimeoutError(f"[{self.name}] 等待输入框超时（被登录页/验证码拦截，请检查页面）")

    def wait_answer_stable(self, page, timeout_ms: int = 150_000) -> str:
        """轮询回答文本，直到长度连续两次不变（认为生成结束），返回最终文本。
        等待期间会顺带关闭限流/提示弹窗。
        """
        last_len = -1
        stable_rounds = 0
        deadline = time.time() + timeout_ms / 1000
        while time.time() < deadline:
            self.handle_modals(page)  # 弹窗可能随时出现
            try:
                text = page.inner_text(self.answer_selector)
            except Exception:
                time.sleep(2)
                continue
            if len(text) > 20 and len(text) == last_len:
                stable_rounds += 1
                if stable_rounds >= 2:
                    return text
            else:
                stable_rounds = 0
            last_len = len(text)
            time.sleep(2)
        raise TimeoutError(f"[{self.name}] 回答未在 {timeout_ms / 1000}s 内稳定输出")

    def extract_sources(self, page) -> list[str]:
        """从页面抓引用链接（可空实现）。"""
        if not self.source_selector:
            return []
        try:
            return page.eval_on_selector_all(
                self.source_selector,
                "els => els.map(e => e.href || e.innerText).filter(v => v && String(v).trim() !== '')",
            )
        except Exception:
            return []

    def ask(self, page, question: str) -> tuple[str, list[str]]:
        """完整一问：打开引擎首页、等待输入框（含登录等待）、关闭弹窗、提问、等回答、取正文与引用。"""
        page.goto(self.url, wait_until="domcontentloaded", timeout=60_000)
        self.wait_for_input(page)
        self.handle_modals(page)
        self.submit(page, self.build_prompt(question))
        text = self.wait_answer_stable(page)
        sources = self.extract_sources(page)
        return text, sources


class KimiAdapter(EngineAdapter):
    """Kimi（kimi.com 网页版）。

    2026-10 实测：输入框是 contenteditable 的 chat-input-editor（不是 textarea）；
    未登录会被登录弹窗拦截，需先在弹窗里手动登录（cookie 存于 profile，后续免登录）；
    高峰期非会员会弹「聊天的人太多」限流弹窗，handle_modals 会自动点掉。
    回答区取 message-list 对话容器（含提问+回答全文，解析层用 LLM 能容忍）。
    """
    name = "kimi"
    url = "https://www.kimi.com/"
    input_selector = "div[class*='chat-input-editor']"                     # contenteditable 输入区
    submit_selector = ""                                                    # 发送按钮选择器见 submit()
    answer_selector = "div[class*='message-list']"                          # 对话容器（登录后含回答）
    source_selector = "div[class*='message-list'] a[href^='http']"          # 只取回答区的引用链接

    def submit(self, page, question: str) -> None:
        """Kimi 网页版回车不发送，需点输入框右侧的圆形发送按钮。"""
        box = self._visible_input(page)
        box.click()
        page.keyboard.type(question, delay=30)
        time.sleep(1)
        for sel in (
            "button[class*='send']",
            "[class*='send-button']",
            "[class*='send-btn']",
            "button[title*='发送']",
            "button[aria-label*='发送']",
        ):
            try:
                btn = page.locator(sel)
                if btn.count() > 0:
                    btn.first.click(timeout=2500)
                    print("[kimi] 已点击发送按钮")
                    return
            except Exception:
                continue
        # 兜底：找不到发送按钮再按回车
        page.keyboard.press("Enter")

    def handle_modals(self, page) -> None:
        """关闭限流/提示弹窗（高峰期「聊天的人太多」会挡在页面上）。"""
        for sel in ("text=我知道了", "text=知道了"):
            try:
                btn = page.locator(sel)
                if btn.count() > 0:
                    btn.first.click(timeout=3000)
                    time.sleep(2)
                    print("[kimi] 已关闭限流提示弹窗")
                    return
            except Exception:
                continue


class DoubaoAdapter(EngineAdapter):
    """豆包（www.doubao.com/chat/）。

    2026-10 实测：输入框是 ProseMirror contenteditable（不是 textarea）；
    游客模式提问不生成回答，需先手动登录一次（流程同 Kimi，见 README）。
    回答区选择器为登录前探测的候选，登录后若失效需重新探测调整。
    """
    name = "doubao"
    url = "https://www.doubao.com/chat/"
    input_selector = "div[class*='ProseMirror']"
    submit_selector = ""                                                    # 回车发送
    answer_selector = "div[class*='markdown'], div[class*='message']"        # 登录后结构，失效需重探测
    source_selector = "a[href^='http']"


class WenxinAdapter(EngineAdapter):
    """百度文心一言（wenxin.baidu.com）。

    2026-10 实测：游客模式即可提问，无需登录（目前最好用的引擎）；
    输入框是 textarea.ci-textarea；回答区 class 带构建 hash，用子串匹配；
    首次打开会弹「全新上线任务模式」引导窗，handle_modals 自动关闭。
    失效时跑 scripts/probe_ask_wenxin.py 重新拿回答区选择器。
    """
    name = "wenxin"
    url = "https://wenxin.baidu.com/"
    input_selector = "textarea.ci-textarea, textarea[class*='ci-textarea']"
    submit_selector = ""                                                    # 回车发送
    answer_selector = "div[class*='_chat-container-main-wrapper_']"
    source_selector = "div[class*='_chat-container-main-wrapper_'] a[href^='http']"

    def handle_modals(self, page) -> None:
        """关闭「全新上线任务模式」等新功能引导弹窗（会遮挡输入框）。"""
        for sel in ("text=×", "[class*='modal'] [class*='close']", "[class*='dialog'] [class*='close']"):
            try:
                el = page.locator(sel)
                if el.count() > 0:
                    el.first.click(timeout=2000)
                    time.sleep(1)
                    print("[wenxin] 已关闭引导弹窗")
                    return
            except Exception:
                continue


class YuanbaoAdapter(EngineAdapter):
    """腾讯元宝（yuanbao.tencent.com/chat/）。

    2026-10 实测：输入框是 Quill 编辑器的 ql-editor（contenteditable）；
    游客提示「请登录后输入内容」，需先手动登录一次（扫码/QQ/微信）。
    回答区选择器为占位，登录后若失效需重新探测。
    """
    name = "yuanbao"
    url = "https://yuanbao.tencent.com/chat/"
    input_selector = "div[class*='ql-editor']"
    submit_selector = ""
    answer_selector = "div[class*='markdown'], div[class*='chat-message']"  # 登录后结构，失效需重探测
    source_selector = "a[href^='http']"


# 引擎注册表：新增引擎时把 {name: 适配器实例} 加进来
REGISTRY: dict[str, EngineAdapter] = {
    adapter.name: adapter for adapter in (
        KimiAdapter(), DoubaoAdapter(), WenxinAdapter(), YuanbaoAdapter()
    )
}


def get_adapter(engine: str) -> EngineAdapter:
    if engine not in REGISTRY:
        raise KeyError(f"未注册的引擎: {engine}，可用: {list(REGISTRY)}")
    return REGISTRY[engine]
