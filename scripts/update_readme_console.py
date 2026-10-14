# -*- coding: utf-8 -*-
"""在 README 中加入操作控制台章节（幂等）。"""
import io

p = "README.md"
s = io.open(p, encoding="utf-8").read()

anchor = "重启服务即可（`python -m uvicorn app.main:app --port 8000`）。\n\n### 首次登录 AI 引擎（关键一步）"
section = """重启服务即可（`python -m uvicorn app.main:app --port 8000`）。

## 操作控制台（新建品牌、采样、报告都在这里）

启动服务后打开 **`http://127.0.0.1:8000/console`**（也可直接双击 `web/console.html`），不需要懂命令行/Swagger：

- **品牌与词库**：表单创建品牌（名称、品类词、官网、竞品勾选、监控 URL、引擎、场景词，点"填入示例"预填瑞幸参数）；右侧点品牌看查询词明细，可追加查询词；
- **采样任务**：一键"采样全部品牌 / 采样当前品牌 / 重跑出错任务"，按引擎/状态筛选任务列表，直接看到每条任务的错误原因；
- **报告与优化**：一键生成周报、跨引擎报告、内容 Brief、检查 AI 收录；历史报告列表；
- **告警**：扫描告警、只看未解决、一键标记已解决。

顶部随时切换"操作品牌"，右上角可跳转看板。控制台负责操作（建品牌/采样/生成报告），看板负责看结果，两页视觉同源、配合使用。

### 首次登录 AI 引擎（关键一步）"""

if "## 操作控制台" in s:
    print("already present, skip")
else:
    assert anchor in s, "anchor not found"
    open(p, "w", encoding="utf-8").write(s.replace(anchor, section))
    print("README 已更新")
