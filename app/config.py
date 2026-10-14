"""全局配置：从环境变量 / .env 读取，前缀为 GEO_。"""
from pathlib import Path

from pydantic_settings import BaseSettings
from pydantic import model_validator

# 项目根目录（geo-studio/），用于把相对 sqlite 路径固定到项目内，避免 cwd 影响
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # 数据库（默认 SQLite，后期单机扛不住再改 postgresql://...）
    database_url: str = "sqlite:///./data/geo.db"

    # LLM 解析用（OpenAI 兼容接口）
    llm_api_base: str = "https://api.deepseek.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"

    # 告警推送（飞书机器人 webhook，留空则不推送）
    feishu_webhook: str = ""

    # 采集参数
    headless: bool = True
    browser_profile_dir: str = "./data/browser_profile"

    # 调度参数
    sampling_interval_minutes: int = 60     # 调度器多久扫一次到期任务
    default_task_frequency_hours: int = 24  # 新建采样任务的默认重采间隔

    model_config = {
        "env_file": ".env",
        "env_prefix": "GEO_",
        "extra": "ignore",
    }

    @model_validator(mode="after")
    def _pin_sqlite_to_project(self) -> "Settings":
        """sqlite:///./data/xx.db 这类相对路径固定到项目根，任何 cwd 下启动都不丢库。"""
        prefix = "sqlite:///./"
        if self.database_url.startswith(prefix):
            rel = self.database_url[len(prefix):]
            self.database_url = f"sqlite:///{(BASE_DIR / rel).as_posix()}"
        return self


settings = Settings()
