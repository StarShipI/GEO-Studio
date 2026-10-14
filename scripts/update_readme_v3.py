# -*- coding: utf-8 -*-
"""README 补充 v3 功能章节（幂等）。"""
import io

p = "README.md"
s = io.open(p, encoding="utf-8").read()

anchor = "### 首次登录 AI 引擎（关键一步）"
section = """## v3 新增（历史趋势 / 竞品对比 / 任务管理 / 导出 / 登录引导 / 告警阈值）

- **可见度趋势**：每轮采样结束自动为品牌写快照（snapshots 表），看板新增趋势折线图，
  周报新增"可见度环比"；`GET /api/analytics/trend/{brand_id}`。
- **竞品对比**：看板新增竞品对比模块（当前品牌 vs 竞品的可见度/SOV/引用并列），
  `GET /api/analytics/compare?ids=5,3,4`。
- **SOV 失真防护**：引用总数 < 5 条时 SOV 显示"数据不足"，不再出现"1 条自引用 = 100%"假象。
- **任务启停与频率**：控制台任务表可停用/启用单条任务、改采样频率（12/24/48/72/168h），
  `PATCH /api/sampling/tasks/{id}`（paused 任务调度器会跳过）。
- **引用明细 CSV 导出**：控制台"导出引用明细 CSV"，`GET /api/export/citations/{brand_id}`（Excel 直接打开）。
- **引擎登录引导**：控制台可一键弹出浏览器登录各引擎（cookie 自动保存），
  `POST /api/engines/login/{engine}`；`POST /api/engines/probe` 探活全部引擎（输入框可达性）。
- **告警阈值按品牌配置**：控制台告警 Tab 设置"负面提及条数 / 可见度下降百分点"，
  `PATCH /api/brands/{id}/alerts`；notifier 按品牌阈值判定（缺省 1 条 / 20%）。
- **报告一键打开**：控制台历史报告带"打开"链接（本地浏览器直接打开生成文件），
  周报与跨引擎报告生成时把文件路径登记入库。

### 首次登录 AI 引擎（关键一步）"""

if "## v3 新增" in s:
    print("already present, skip")
else:
    assert anchor in s, "anchor not found"
    open(p, "w", encoding="utf-8").write(s.replace(anchor, section, 1))
    print("README v3 章节已加入")
