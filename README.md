# GEO Studio

GEO（生成引擎优化）服务型 MVP：自建工具 + 自己服务品牌的内部运营中台。
监控品牌在 AI 引擎（Kimi、豆包等）回答中的引用与提及，输出可见度指标、答案缺口、周报和告警。

技术栈：Python + FastAPI + SQLite + Playwright + LLM（OpenAI 兼容接口）+ APScheduler。
全程同步、单体、少依赖，专为 vibe coding 扩展设计。

## 目录结构

```
geo-studio/
├── app/
│   ├── main.py            # FastAPI 入口（uvicorn app.main:app --reload）
│   ├── api.py             # 全部 API 路由
│   ├── config.py          # .env 配置（前缀 GEO_）
│   ├── database.py        # SQLAlchemy 引擎与会话
│   ├── models.py          # 8 张表 ORM
│   ├── scheduler.py       # APScheduler：周期采样 + 周期告警
│   └── services/
│       ├── engines.py     # AI 引擎适配器（kimi / doubao / wenxin / yuanbao，选择器在此维护）
│       ├── scraper.py     # Playwright 采集主流程（问→存快照→立即解析）
│       ├── parser.py      # LLM 解析归因（回答 → citations + brand_mentions）
│       ├── metrics.py     # 可见度 / SOV / 答案缺口（按引擎）/ 内容引用 / 负面提及
│       ├── reporter.py    # 周报生成（Markdown，reports/ 目录 + reports 表）
│       ├── engine_report.py # 跨引擎对比 HTML 报告（浏览器直接打开）
│       └── notifier.py    # 飞书告警
├── sql/schema.sql         # 独立建表 SQL（与 ORM 等价）
├── scripts/init_db.py     # 建表 + 可选演示数据（品类词 + 内容监控）
├── scripts/migrate_v2.py  # v2 迁移：加列（keywords.type / brands.category / monitored_urls）
├── scripts/enrich_demo.py # 为已有品牌补品类词与内容监控配置
├── scripts/gen_report.py  # 生成跨引擎对比 HTML 报告
├── data/                  # SQLite 数据文件与浏览器 profile 目录（运行时生成）
├── .env.example           # 复制为 .env 后填写
└── requirements.txt
```

## 快速开始

```bash
cd geo-studio
pip install -r requirements.txt
playwright install chromium        # 下载采集用浏览器（约 150MB，一次性）

# 配置
copy .env.example .env             # 然后编辑 .env，至少填 GEO_LLM_API_KEY

# 初始化数据库（可选 --seed 插入演示品牌）
python scripts/init_db.py --seed

# 启动服务
uvicorn app.main:app --reload
```

浏览器访问 `http://127.0.0.1:8000/docs` 查看并调试全部 API。

## 可视化看板（不懂技术也能用）

启动服务后打开 **`http://127.0.0.1:8000/dashboard`** 即图形界面（也可直接双击
`web/dashboard.html` 文件打开，会自动连本机服务）：

- 顶部选品牌 + 刷新数据（首屏默认展示最新创建、有数据的品牌）；
- 大数字卡片：AI 可见度、引用份额 SOV、引用总数、负面提及、被提及查询数；
- 各引擎 AI 可见度柱状图、AI 引用 Top 域名图；
- 答案缺口（按引擎）、权威度建设（权威域引用 + 目标平台清单）、内容引用追踪（自媒体/RAG）；
- 一键操作：立即采样 / 生成周报 / 生成跨引擎报告 / 生成内容 Brief；
- 采样任务概览（总数/启用/出错，出错多为未登录或限流引擎）。

看板与 API 同源托管（无跨域问题），也支持 file:// 直接打开（服务已开 CORS）。
维护提示：uvicorn `--reload` 在本机某些环境下自动重载不可靠，改代码后若发现看板不更新，
重启服务即可（`python -m uvicorn app.main:app --port 8000`）。

## 操作控制台（新建品牌、采样、报告都在这里）

启动服务后打开 **`http://127.0.0.1:8000/console`**（也可直接双击 `web/console.html`），不需要懂命令行/Swagger：

- **品牌与词库**：表单创建品牌（名称、品类词、官网、竞品勾选、监控 URL、引擎、场景词，点"填入示例"预填瑞幸参数）；右侧点品牌看查询词明细，可追加查询词；
- **采样任务**：一键"采样全部品牌 / 采样当前品牌 / 重跑出错任务"，按引擎/状态筛选任务列表，直接看到每条任务的错误原因；
- **报告与优化**：一键生成周报、跨引擎报告、内容 Brief、检查 AI 收录；历史报告列表；
- **告警**：扫描告警、只看未解决、一键标记已解决。

顶部随时切换"操作品牌"，右上角可跳转看板。控制台负责操作（建品牌/采样/生成报告），看板负责看结果，两页视觉同源、配合使用。

## v3 新增（历史趋势 / 竞品对比 / 任务管理 / 导出 / 登录引导 / 告警阈值）

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

### 首次登录 AI 引擎（关键一步）

引擎网页版通常有登录/风控。把 `.env` 里的 `GEO_HEADLESS=false`，然后通过
`POST /api/sampling/run` 触发一次采样，浏览器会以**有头模式**弹出：
手动完成登录（或过验证码）后关掉窗口，之后 cookie 会保存在
`data/browser_profile/<引擎名>/`，后续无头采集即可复用。

遇到验证码不要硬闯：采集代码不会绕过验证码，一次手工登录 + 正常采集节奏是合规做法。

## API 速查

| 方法 | 路径 | 作用 |
| --- | --- | --- |
| POST | `/api/brands` | 创建品牌（自动展开品牌词×场景 + 品类词×通用问题 + 多引擎采样任务） |
| GET | `/api/brands` / `/api/brands/{id}` | 品牌列表 / 详情 |
| POST | `/api/brands/{id}/keywords` | 手动加一个查询词 |
| POST | `/api/sampling/run` | 手动触发采样（body: `{"brand_id": 1}` 或 `{"task_ids": [1,2]}`，后台执行） |
| GET | `/api/sampling/tasks` | 采样任务列表 |
| GET | `/api/analytics/visibility/{id}` | AI 可见度 / SOV / 负面提及 / Top 引用域名 / 按引擎拆分 |
| GET | `/api/analytics/gaps/{id}` | 答案缺口（含 `by_engine` 按引擎分组） |
| GET | `/api/analytics/content/{id}` | 自媒体内容引用追踪（RAG：`monitored_urls` 被引用明细） |
| GET | `/api/content/brief/{id}` | AI-ready 内容 Brief（缺口→选题/FAQ/结构化清单/权威度动作） |
| GET | `/api/content/authority/{id}` | 权威度建设：权威域引用统计 + 目标域动作清单 |
| POST | `/api/content/check-index/{id}` | 索引保障：对监控内容问 AI 验证收录（后台执行） |
| POST | `/api/reports/weekly/{id}` | 生成 Markdown 周报（落盘 `reports/<品牌名>/`） |
| POST | `/api/reports/engine/{id}` | 生成跨引擎对比 HTML 报告（浏览器直接打开） |
| GET | `/api/reports` | 报告列表 |
| POST | `/api/alerts/check` | 手动跑一次告警检查 |
| GET/POST | `/api/alerts`、`/api/alerts/{id}/resolve` | 告警查看与处理 |

## 选择器失效怎么办（最常见问题）

引擎页面改版后 `app/services/engines.py` 里的选择器会失效，报错通常是
`Timeout: 回答未在限时内稳定输出`。修复步骤：

1. 打开引擎网页，F12 打开开发者工具；
2. 输入框：点选输入框，右键 → 检查，复制一个稳定的 `placeholder` 属性；
3. 回答正文：等 AI 回答后，检查正文容器，挑一个稳定的 class 或属性选择器；
4. 只改对应适配器的 `input_selector` / `answer_selector`，其余不动。

## 新增引擎

1. 在 `engines.py` 里继承 `EngineAdapter`，填 url 与选择器；
2. 在 `REGISTRY` 加一行 `{name: 适配器实例}`；
3. 创建品牌或任务时 `engine` 字段填新名字即可。

## 多引擎监控（GEO 核心：同一品牌在各家 AI 的说法对比）

新品牌默认同时监控 **wenxin（免登录，最稳）、kimi、doubao、yuanbao** 四个引擎；
指标（可见度/SOV）按引擎拆分，`GET /api/analytics/visibility/{id}` 返回里的 `engine_breakdown`
就是每家 AI 的独立可见度，方便直接对比。

| 引擎 | 状态（2026-10 实测） | 说明 |
| --- | --- | --- |
| wenxin 文心一言 | ✅ 免登录可用 | 游客模式直接提问，目前最稳 |
| kimi | ⚠️ 需登录 + 高峰限流 | 登录一次即可，错峰跑 |
| doubao 豆包 | ⚠️ 需登录 | 登录一次即可，通常比 kimi 宽松 |
| yuanbao 腾讯元宝 | ⚠️ 需登录 | 登录一次即可 |

日常维护工具（都在 scripts/ 下）：

- `python scripts/test_engine.py <引擎名>` —— 单引擎端到端测试（改选择器后用它验证）；
- `python scripts/probe_engines.py` / `probe_ask_wenxin.py` —— 探测引擎页面结构，拿到真实选择器；
- `python scripts/expand_engines.py [引擎名...]` —— 新增引擎后，一键为所有品牌补建该引擎的采样任务；
- `python scripts/set_engine.py <引擎名> <品牌id>` —— 把某品牌全部任务切换到指定引擎；
- `python scripts/gen_report.py <品牌id>` —— 生成跨引擎对比 HTML 报告；
- `python scripts/enrich_demo.py <品牌id>` —— 为已建品牌补品类词与内容监控配置（v2 字段）。

新增引擎三步：在 `app/services/engines.py` 继承 `EngineAdapter` 填选择器 → 注册进 `REGISTRY` →
跑 `expand_engines.py` 补任务（或新品牌自动带上）。

## Prompt 库与两类客户（v2 核心）

创建品牌时自动展开两类查询，分别服务两种客户：

| 客户类型 | 查询类型（Keyword.type） | 自动展开 | 看什么指标 |
| --- | --- | --- | --- |
| 商品/服务品牌 | `brand`（品牌词×场景） | 品牌词 ×「是什么/怎么样/值得推荐吗/价格怎么样/和竞品比怎么样」 | 可见度、SOV、答案缺口 |
| 商品/服务品牌 | `category`（品类词×通用问题） | 品类词 ×「有哪些{品类}推荐/什么{品类}好/哪个牌子好/怎么选/推荐一个品牌/买{品类}注意什么」 | **推荐场景**：AI 推荐时有没有你 |
| 自媒体/内容客户 | `brand` + `monitored_urls` | 品牌词×场景 + 你发布的内容 URL（公众号/小红书/B站等） | **内容引用**：内容进入 AI 检索（RAG）并被引用的次数 |

- 品类词在创建品牌时填 `category`（如"咖啡"）自动展开，演示数据已配置；
- 自媒体内容追踪填 `monitored_urls`（URL 列表），指标接口
  `GET /api/analytics/content/{id}`，周报/HTML 报告都会输出"内容引用追踪"小节；
- 引用归因精确到 URL：`citations` 表存被引用链接、出现位置、所属回答，谁被引用、几次一目了然。

## 跨引擎对比报告（给客户看的交付物）

Markdown 周报之外，`POST /api/reports/engine/{id}` 或 `python scripts/gen_report.py <品牌id>`
会生成一份**自包含 HTML 对比报告**（浏览器直接打开，可转发给客户）：

- KPI 总览：AI 可见度、SOV、引用总数、负面提及；
- 各引擎 AI 可见度柱状图 + 各引擎答案缺口柱状图；
- 各引擎可见度明细表、答案缺口（按引擎）表；
- 被引用 Top 域名表（AI 在回答里引了哪些网站）；
- 内容引用追踪（自媒体/RAG 监控）小节；
- 内容优化动作卡片（缺口主题选题 + 权威域引用占比）。

## 内容优化工作台（GEO 第三层：从洞察到动作）

监控和报告回答"AI 现在怎么说你"，内容优化回答"下一步写什么、怎么写"。四件套全部基于库里
真实数据（缺口/引用/可见度）生成，入口 `GET /api/content/brief/{id}` 或 `python scripts/gen_brief.py <品牌id>`：

1. **AI-ready 内容生成**：缺口查询自动转成内容选题（知识型文章/推荐榜/对比评测/选购指南），
   附带 FAQ 候选、AI 当前引用格局表（你写的内容要超越谁）；
2. **结构化**：随 Brief 输出可直接粘贴的三件套模板——官网根目录 `llms.txt`、FAQPage JSON-LD Schema、
   论证结构清单（结论前置/小标题结论化/表格化数据，AI 摘取率最高）；
3. **权威度建设**：`GET /api/content/authority/{id}` 统计权威域（百科/知乎/小红书/公众号/行业媒体）
   被 AI 引用的占比（Authority Score），并给每个目标权威域一条具体动作（共建词条/开官方账号/发新闻稿）；
4. **索引保障**：`POST /api/content/check-index/{id}` 或 `python scripts/check_index.py <品牌id>`
   对品牌发布的内容 URL 直接问 AI"你是否了解这篇内容"，验证内容是否已进入 AI 检索（RAG 收录），
   并输出发布后 48h 检查清单（sitemap 提交、robots.txt 放行 GPTBot/ClaudeBot/Bytespider 等 AI 爬虫）。

周报和 HTML 对比报告都会带上"内容优化建议"小节，客户拿到报告直接知道本周该写哪几篇。

## v4 账号 GEO（自媒体/内容型客户：内容级 RAG 归因）

针对自媒体账号客户（推公众号/小红书/B站/抖音等内容），看的不再是"品牌被怎么说"，而是**我的内容有没有被 AI 引用、引用了哪篇、哪句话、发布后多久被收录**。

- **内容清单登记**：控制台"内容清单（账号 GEO）"登记内容 URL + 平台（自动识别）+ 发布时间；
  亦可通过 `POST /api/account/content-items`（品牌 id + URL + 平台 + 发布时间，双写监控 URL）。
- **账号视图页** `/account`（绿色主题 #059669）：5 KPI（监控内容/被引内容/内容被引率/引用总次数/平均收录时效）、
  **跨平台发布效果**柱状图（各平台内容数 vs 被引内容）、**同领域账号对比**（当前品牌 vs 竞品的内容被引率）、
  **内容被引 Top**（内容级 RAG 归因：AI 在哪个问题里引用了你的哪句话，含引擎/问题/引用原文/时间，逐行展开）、
  未收录内容列表（发布 N 天未收录）。
- **内容级 RAG 归因**：`citations.snippet` 由 LLM 解析器从 AI 回答中提取引用原文，
  归因精确到 URL + 原文句子；账号摘要 API 按内容聚合引用明细（query/engine/snippet/sampled_at）。
- **收录时效监测**：发布时间 → 首次被 AI 引用（采样发现），未收录内容显示"发布 N 天未收录"。
- **跨平台发布效果归因**：按内容 URL 域名识别平台（小红书/公众号/知乎/B站/抖音/微博/百家号/头条/掘金/CSDN/官网），可手动指定。
- **账号周报**：`POST /api/reports/account/{brand_id}` 生成"账号 GEO 周报"（默认近 7 天窗口），
  含核心指标/跨平台表/被引 Top + 引用明细（问什么 → 引用哪句话）/未收录/账号对比/下一步建议。
- **API**：`GET /api/account/summary/{id}`、`GET /api/account/compare?ids=`、`GET/POST /api/account/content-items`、`PATCH/DELETE /api/account/content-items/{id}`、`POST /api/reports/account/{id}`。
- **已实测**（2026-10-12 瑞幸咖啡真实采样）：监控 7 条内容（官网/新加坡官网/微博/抖音/36氪/行业媒体），
  被引 2 条（`luckincoffee.com` 被引 1 次、`luckincoffee.com.sg` 被引 1 次，均为 wenxin），内容被引率 28.6%。
- **数据库**：v4 迁移新增 `content_items` 表（幂等建表 + 从 brands.monitored_urls 回填）。

**生产排障（2026-10-12 实测修复）**：采样异常/崩溃路径会让 Playwright chromium 残留进程
锁住 profile（Windows"另一个程序正在使用此文件"），导致后续所有采样 launch 失败。
scraper 已内置自愈：`launch` 失败自动清理残留 chromium（按 profile 目录匹配）+ 删除锁文件后重试。

## 引擎限流与换引擎（2026-10 实测）

- **Kimi 高峰限流**：高峰时段（尤其节假日、白天）免费账号会弹「聊天的人太多」提示，回答长时间不生成导致超时失败。采集代码已自动关闭该弹窗，但排队严重时仍会失败。对策：**错峰采样**（清晨/深夜）或**换引擎**。
- **换豆包引擎**（豆包通常比 Kimi 宽松，但游客模式不回答，需登录一次）：
  1. 切换任务引擎：`python scripts/set_engine.py doubao 2`（2 换成你的品牌 id）；
  2. `.env` 设 `GEO_HEADLESS=false`，重启服务，触发一次采样（弹窗里手动登录豆包，登录后**不要关窗口**，等它自动继续）；
  3. 登录完成后把 `GEO_HEADLESS` 改回 `true`，重启服务，再次触发采样即可无人值守。
- **判断是不是限流**：看任务 `last_error`。若出现「回答未在 xxx s 内稳定输出」且页面截图停在首页，就是限流/未登录；若报「等待 locator」超时，才是选择器失效（按上一节修复）。

## 合规与边界（务必读）

- 本工具只做「观察 AI 怎么说你的品牌」的正当监控，不注入、不操纵 AI 输出；
- 采集保持合理节奏（默认每条间隔 3 秒），不绕过验证码、不撞反爬；
- 不做隐藏文本、Prompt 注入式「黑帽 GEO」，这类做法有内容安全与监管风险。

## 真实品牌端到端演示（2026-10-01 实测）

`python scripts/seed_real_brand.py` 会用真实品牌建全量演示（可重复执行）：

- 主品牌：**瑞幸咖啡**（官网 luckincoffee.com，品类=咖啡，内容监控=官网首页/关于页）
- 竞品：**星巴克中国**（starbucks.com.cn）、**库迪咖啡**（cotti.cn）
- 自动展开：品牌词×5 场景 + 品类词×6 通用问题，× 4 引擎 = 16 关键词 / 64 采样任务

实测结果（wenxin 引擎，6 条真实回答）：

| 指标 | 结果 |
| --- | --- |
| AI 可见度 | 83.3%（6 查询 5 被提及） |
| 引用份额 SOV | 100%（文心引用 luckincoffee.com 官网） |
| 内容引用追踪 | 官网首页被引用 1 次（查询"瑞幸咖啡 是什么"） |
| 索引检查 | 官网首页/关于页均**已收录**（文心了解页面内容） |

换你自己的客户品牌：改 `seed_real_brand.py` 里的品牌名/官网域名/竞品即可，流程全自动。
注意：kimi/doubao/yuanbao 的采样依赖登录（见上文"首次登录 AI 引擎"）；国庆等高峰时段
文心/豆包会排队限流，回答生成慢属正常，错峰跑即可。

## 索引检查的判定口径

`check_index` 向 AI 问"你是否了解这篇文章"验证内容是否进入 AI 检索（RAG 收录），判定规则：
- AI 回答含"我了解/这是……内容"等实质概述 → **已收录**；
- AI 明确说"我不知道/没看过" → **未收录**；
- 回答为空/排队未生成 → **需重试**（标为失败，建议错峰重跑）。
判定已处理页面 UI 残渣与提示词回显，不会把 AI 复述你的提问误判为"未收录"。

## SQLite 并发写（uvicorn 服务 + 采样脚本同时跑）

服务与采样脚本可能同时写库。已内置两层保护：
1. `app/database.py` 为每个 SQLite 连接开启 **WAL 模式 + busy_timeout=60s**（读写不互斥、写冲突自动等待重试）；
2. 采样落库改为"先提交快照再独立连接解析"的短事务，LLM 解析耗时不再持有写锁。
若仍遇 `database is locked`：停掉 uvicorn 释放锁、重新启动即可恢复（数据无丢失）。

## 已知简化（后续按需扩展）

- 只做最近一次回答快照的指标重算，未做历史趋势表（改 `metrics.py` 加快照即可）；
- 可见度骤降告警未实现（需要历史快照，当前只有负面提及告警）；
- 周报为 Markdown，转 PDF 可接 pandoc 或后续加 LibreOffice；
- 多引擎并行采集是串行的（每引擎一个浏览器上下文），任务量大时可拆到多进程。
