# 农智链 AgriAgent

北方大田智能植保与生产管理智能体平台 —— 基于大语言模型智能体的农业植保辅助决策系统。

## 目录结构

```
AgriAgent/
├── app.py                    # 入口：角色路由（农户端 / 农技员端）+ 空库自动初始化演示数据
├── config.py                 # 全局配置：读取 .env → 云端 Secrets 两级回退，模型/密码
├── timeutil.py               # 统一北京时间工具（云端容器为 UTC，避免时间偏移 8 小时）
├── generate_demo_data.py     # 演示数据生成（4 农户 / 6 地块 / 34 诊断 / 93 日志 / 6 工单）
├── requirements.txt          # 依赖清单
├── .env.example              # 配置模板（复制为 .env 后填写）
├── agent/                    # 自研轻量智能体框架：Planner（确定性规则规划）+ Executor（六步流水线）
│   ├── planner.py            #   任务规划：按输入条件生成步骤序列
│   ├── executor.py           #   步骤执行：知识检索→视觉分析→历史召回→LLM 诊断→安全审核→归档
│   ├── knowledge.py          #   知识检索服务（RAG 加权打分）
│   ├── memory.py             #   地块长期记忆服务（历史诊断召回）
│   └── safety.py             #   安全审核服务（三级可信的第一级：规则闸门）
├── services/                 # 业务服务层
│   ├── ai_service.py         #   大模型调用（多模态诊断 / 视觉描述 / 长期管理建议）+ 示例模式兜底
│   ├── crop_plan.py          #   30 天农事计划生成（真实模型 / 规则模板兜底）
│   ├── stats.py              #   统计分析（病害分布、风险等级、趋势）
│   ├── reporting.py          #   报告导出（PDF / Word / 纯文本）
│   └── plan_export.py        #   方案文档导出（reportlab / python-docx）
├── database/                 # 数据层：SQLite 连接、建表、仓储、JSON→SQLite 迁移
├── memory/                   # 地块档案与工单存储
│   ├── history.py            #   诊断记录 / 工单读写
│   ├── profiles.py           #   地块档案（土壤、面积、农事日志）
│   └── store/                #   初始 JSON 数据 + 演示工单图片
├── knowledge/                # 内置病害/农药知识条目
├── knowledge_center/         # 农业知识中心
│   ├── loader.py             #   知识加载（data/*.json 合并）
│   ├── retriever.py          #   加权打分检索 + 作物别名识别
│   ├── registration.py       #   农药登记核验（1171 条公告数据）
│   ├── data/                 #   24 种作物病害 JSON + 农药登记库
│   └── _cropdata/            #   16 个作物数据模块（知识构建用）
├── safety/                   # 安全审核规则（禁限用农药、高风险内容拦截）
├── views/                    # 界面：农户端 + 农技员端 9 个功能页面
├── components/               # 界面组件：布局、主题、图表、Markdown/HTML 渲染
├── tools/                    # 知识库构建与农药登记数据采集脚本（离线使用）
├── tests/                    # 自动化测试（119 项）
└── data/agragent.db          # 演示数据库（首次启动若为空会自动生成）
```

> 模块职责与设计细节见《软件创意设计文档》；测试命令见文末「测试」章节。

## 启动方式

```bash
pip install -r requirements.txt
streamlit run app.py --server.port=8505
```

首次启动时自动创建 SQLite 数据库（`data/agragent.db`）。

**依赖说明**：`requirements.txt` 已覆盖运行全部依赖（streamlit / Pillow / python-dotenv /
requests / reportlab / python-docx）。另有**可选依赖** `xlrd`：仅当运行
`tools/harvest_registration.py` 解析旧版 `.xls` 登记公告时才需要
（`pip install xlrd`），不影响主程序运行。

## 登录方式与账号

| 端 | 登录方式 | 账号 / 密码 |
|---|---|---|
| 农户端 | 左侧选择「农户端 · 智能生产管理」 | **无需登录**，直接使用 |
| 农技员端 | 左侧选择「农技员端 · 监测后台」，输入管理密码 | **默认密码 `admin123`** |

修改管理密码：在 `.env` 中设置 `ADMIN_PASSWORD=你的密码`（云端部署则改 Streamlit Secrets 的
`ADMIN_PASSWORD`），保存后重启应用生效。密码只用于农技员端登录，农户端不受影响。

## 模型配置（重要）

诊断质量高度依赖模型是否为**多模态**。请检查 `.env`：

```
AI_API_URL=https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
AI_MODEL=qwen3-vl-plus
AI_API_KEY=sk-...
```

- `qwen3-vl-plus` 支持图片输入，上传照片才会真正参与诊断（已实测可用）。
- 若配置为纯文本模型（`deepseek-chat` / `qwen-plus` 等），上传的图片会被忽略并
  降级为纯文字诊断；请把 `AI_MODEL_SUPPORTS_VISION` 设为 `0`，让程序直接走
  文字模式，避免每次白跑一次注定失败的视觉请求。
- `qwen-vl-plus` 这个旧模型名已下线（接口返回 404 Model not exist），请勿使用。
- **未配置 `AI_API_KEY` 时，系统会返回「示例诊断」占位内容**，仅用于演示，
  不可当作真实结论。

## 农药登记合规核验（法律底线）

农药登记数据来源分两层：

| 文件 | 性质 | 含什么 |
|---|---|---|
| `knowledge_center/data/pesticide.json` | **人工逐条核验**的小型权威条目 | 登记作物/防治对象 + 剂量 + 安全间隔期 + 登记号 + 来源链接 |
| `knowledge_center/data/pesticide_registry.json` | **官方公告批量导入**（1172 个产品） | 登记证号、持有人、农药名称、剂型、毒性、有效成分、农药类别、作物/场所、防治对象 |

批量登记库由 `tools/harvest_registration.py` 从官方公开数据采集生成：

```bash
python tools/harvest_registration.py --import    # 采集 + 归一化 + 写登记库
```

数据链路（中国农药信息网 → 农业农村部种植业管理司附件）：

```
中国农药信息网「登记信息发布」
  → POST http://219.141.234.8/zgnyxxw/zwb/getPage  (id=753 分页)
  → /zwb/detail/{id} → https://zzys.moa.gov.cn/gzdt/...htm
  → 附件 P020xxxxxxxx.xls（官方 XLS，每期一张表）
```

> 域名 `www.icama.cn` 在部分网络环境连接超时，同站点 IP 入口 `219.141.234.8`
> 可访问；附件在 `zzys.moa.gov.cn`，下载需带 Referer。解析 `.xls` 需 `xlrd`。

**已知边界**（务必知悉）：

1. 公告只覆盖 **2021–2026** 的登记新增/延续/变更。更早登记且此后未延续的
   品种（如甲霜灵、腐霉利）查不到，会保持"未收录"状态 → 判为不可推荐。
2. 公告 XLS **不含用药量与安全间隔期**，这两项只出现在农药登记标签上。
   界面与配药换算会如实显示"按标签"，不会虚构。

病害条目 `data/*.json` 里的 `registered` / `chemical_control` 是**历史资料，未经过
登记核验**，与官方数据存在冲突。最典型的一例：玉米大斑病条目把「苯醚甲环唑」
列为登记药剂，且剂量写着已被废止的「2000 倍液」——而官方登记中该药在玉米上
登记的是「叶斑病」泛称、剂量表述也已改为克/亩。把这类药剂当"已登记"推荐给
农户属于**超范围用药**。

因此 `knowledge_center/registration.py` 提供独立的核验层，**只核验、不生成农业事实**：

| 判定 | 含义 | 处理 |
|---|---|---|
| `registered` | 权威数据确认该作物 + 该防治对象均已登记 | 允许推荐 |
| `registered_crop_only` | 该作物已登记，但防治对象不同（含"泛称覆盖细分"） | 提示核对标签 |
| `out_of_scope` / `unregistered` | 未登记该作物 | **禁止推荐** |
| `unverified` | 登记库未收录该品种 | **禁止当作已登记推荐** |
| `mixture` | 复配剂（名称含「·」） | 不做单剂推断，提示复核 |

**两道独立防线**（都实现在 Agent 链路里）：

1. **事前白名单**（`agent/executor.py::_registration_constraints`）：
   把超范围药剂从交给 LLM 的候选里剔除，并在 Prompt 里明确禁止，同时给出
   权威剂量与安全间隔期。
2. **事后闸门**（`safety/reviewer.py::_registration_issues` + `sanitize_pesticide_mentions`）：
   实测即使 Prompt 明确禁止，通用大模型仍会写出未登记药剂。因此审核判为高危，
   并把药剂名**从最终报告正文中剔除**（替换为 `〔已移除〕`），报告开头附一段
   可追溯说明。仅仅"标记问题"不够 —— 农户会照着正文用药，所以必须从内容层面清除。

**药剂名识别**（`extract_candidate_names`）采用"候选位置 + 位置消解"：长片段优先，
与登记产品名重叠的片段丢弃。这样「吡唑醚菌酯」不会被拆成「吡唑 + 醚菌酯」，
而独立出现的「醚菌酯」仍会被保留并可被正确核验。

全库审计（维护用，可随时检出数据冲突）：

```python
from knowledge_center.registration import audit_all
for r in audit_all():
    if r["blocked"]:
        print(r["crop"], r["disease"], "→ 需拦截:", r["blocked"])
```

**维护约定**：新增病害条目时，`pesticide_reference.registered` 只能填登记库中
已收录的药名；新增药剂时必须在 `pesticide.json` 里补上 `registered_crops` 与
`registered_targets`，否则会被判为 `unverified` 而无法推荐。

## 数据存储

当前版本采用 SQLite 作为业务数据持久化数据库（Python 标准库 `sqlite3`，无重型框架依赖）。

数据库文件：

```
data/agragent.db
```

主要保存：

- 农户信息（farmers）
- 地块档案（plots）
- AI 诊断记录（diagnosis_records）
- 农事记录（farming_logs）
- 农技任务 / 工单（tasks）

图片等非结构化文件继续使用文件系统保存（`memory/store/task_images/`），数据库仅存路径引用。

数据库访问分层：`views / services / agent → memory 服务层 → database/repository → SQLite`，业务层不直接执行 SQL。

历史 JSON 数据迁移：

```bash
python database/migrate.py
```

迁移幂等可重复执行，原 JSON 文件保留作为备份。

未来随着平台规模扩大，可以进一步迁移至 MySQL 等服务器型数据库（repository 层隔离了具体 SQL 方言差异的主要部分）。

## 农户端交互

农户端为**完整表单版**（按用户要求保留原始交互）：

- 表单：上传作物图片（上传/拍照共用一个卡片，两种输入互斥）→ 作物与地块信息
  （作物/生长阶段/土壤/面积/位置/异常现象描述）→ 姓名与联系方式（可选）
- 「异常现象描述」下方提供**常用词下拉区**（默认收起、列内换行无横向滚动），
  点选即并入描述；标签是农户口语（如「水渍纹」），检索用词另行映射为知识库用词
  （如「水渍状」），映射表见 `components/symptom_chips.py`
- **作物选择「其他」时会展开一个文本框**，农户填写具体作物名；
  系统用 `knowledge_center/crop_aliases.py` 把俗称解析为规范作物名
  （「土豆」→马铃薯、「苞米」→玉米、「小米」→谷子、「莜麦」→燕麦…），
  再按该作物的知识条目针对性诊断；无法识别时明确提示"未收录、按通用知识诊断"
- 诊断结果页包含完整板块：报告头、病害判断、处理建议、智能体执行流程、
  诊断依据、可信度评分、完整诊断报告、安全审核记录、免责声明
- 另有两处**合规与便利增强**（均为增量，不影响上述版式）：
  - 「算算要买多少药、兑多少水」配药计算器（把亩用量换算成整块地用量）
  - 「农药登记核验」折叠区（列出已核验可用药剂 + 已为你排除的药剂及原因）

## 知识库与作物覆盖

知识库覆盖 **24 种北方大田作物、118 条病虫害知识**（每作物 2–8 条）。

作物清单：玉米、小麦、水稻、马铃薯、谷子、糜子、燕麦、荞麦、大麦、高粱、
大豆、绿豆、豌豆、蚕豆、红小豆、花生、油菜、向日葵、芝麻、亚麻、蓖麻、
棉花、甜菜、苜蓿。

### 数据管线（重要）

`knowledge_center/data/*.json` 是运行时唯一数据源。为避免手写大段 JSON 出错，
每个作物的内容维护在 `knowledge_center/_cropdata/<crop>.py`（可写注释、可注明来源），
再由脚本渲染为 JSON：

```bash
python tools/build_crop_data.py --check   # 只校验（字段完整性/枚举合法性/作物一致性）
python tools/build_crop_data.py           # 校验并生成 data/*.json
```

新增作物需三处同步（缺一处就会出现"选了作物却检索不到"）：

1. `config.py` 的 `CROPS`（农户端下拉列表）
2. `knowledge_center/crop_aliases.py`（别名表，决定俗称能否被识别）
3. `knowledge_center/loader.py` 的 `_crop_to_filename` 与
   `tools/build_crop_data.py` 的 `_FILENAMES`（数据文件映射）

`tests/test_knowledge.py` 已加入不变量断言：**农户端可选的每种作物都必须有知识条目**，
漏建数据会在测试阶段直接失败。

知识来源：农业农村部及全国农技推广服务中心的生产技术指导意见、中国科协科普中国
（省级农科院专家审核）、中国农科院农业信息研究所、内蒙古/陕西等地方标准。
每条目均记录 `source` / `source_title` / `source_url`，可溯源。

## 农技员端统计图表

病害统计与风险统计使用 `components/charts.py::hbar_html` **自绘横向条形图**，
不使用 `st.bar_chart`。原因：内置柱状图在分类轴放不下「玉米大斑病」这类长中文
标签，会自动旋转成竖排，既难读也显得排版凌乱。自绘条形图标签始终水平完整显示，
并与主题的 `.ag-adm-bar-*` 风格统一。

## 测试

```bash
python tests/test_database.py     # SQLite / repository / 迁移
python tests/test_knowledge.py    # 知识库检索与打分回归
python tests/test_registration.py # 农药登记核验 / 事前白名单 / 事后剔除
python tests/test_pages.py        # 页面渲染（Streamlit AppTest）
python tests/test_farmer_flow.py  # 农户端链路冒烟：章节提取 / 行动步骤 / 检索闸门
python tests/test_mock_notice.py  # 无密钥/调用失败时必须明确提示（不得伪装成大模型输出）
```

> 前 4 个模块共 105 个用例；`test_mock_notice.py` 另含 14 个用例（合计 119）。
> 说明：`test_mock_notice.py` 断言"未配置密钥或接口不可用"时，诊断/建议/生产计划的正文
> 必须出现提示，且报告不得声称"已结合视觉分析结果"（示例模式下图片并未参与分析）。
