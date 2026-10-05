# glm53_静态.md — 政务AI安全网关（gov-anon-gateway）逐组件静态盘点工作稿

- 盘点人：GLM-5.3-Flash 独立盘点组 · 静态盘点员
- 盘点日期：2026-10-03（本会话内完成）
- 工作区根：`D:/new-workspace/澄迈项目/政务AI安全`；主仓库：`gov-anon-gateway/`（下文相对路径均以此为基准）
- 盘点方式：只读走查（源码/配置/文档零改动；仅在 `盘点/` 目录写本稿）＋ 少量只读验证命令 + 6 个离线 eval 实跑复验（见 §6）
- 引用格式：`文件:行号`；行号为本会话实读时点。**红线遵守**：未把 `.env`、`MASK_KEY`、任何 key/token 的真实值写入本稿（`.env` 仅确认存在与 gitignore 状态，未读取内容）。

---

## 0. 盘点范围与总体结论

**范围**：`gov-anon-gateway/` 全部 14 个组件（common / gateway / recognizers / masking / routing / outguard / filechannel / audit / benchmark / webui / ops / evals / gpu / gpu-services），README 全部量化与能力声明逐条核对；工作区根 `_upstream/`、`wf_run.py`、`wf_env.py` 一句话带过；`out/public-export/`（导出镜像）按产物对待不逐文件走查。

**总体结论（一句话）**：主链路（识别→可逆脱敏→敏感度路由→输出防护→审计闸）**全部真实实装**且验收体系（19 个 eval 入口 + 8 个门脚本）完备、自述文档与代码一致性极高；已实装之外的「占位」均为**显式声明**的规划位（NER 适配器、输出复检 P0 空后端、m8_baselines、docker-compose 未实测、演示场景 1-3 脚本待补），无静默假实现；主要风险集中在**代码态未提交固化（33 个文件未提交）**、**收官整门 gate_final 在 S2 轮未取得 9/9**（环境面根因，留档自认）、以及三处文档滞后点（见 §5）。

**盘点期间环境注记**：工作区存在并行活动——`tmp/wf/` 最新日志为 2026-10-03 20:20 的 `evals.m10_e2e`（无结果行，进行中或被截断）、`data/bench/quality_report.json` mtime 2026-10-03 19:49（仅 `evals/m8_quality.py:93` 会写该文件，本盘点员未跑过 m8_quality），即盘点时点工作区并非静态快照。

---

## 1. 仓库与工作区总览

- 仓库身份：git 仓库 `HEAD = d6daffd`（`chore: import chenmai-gov-ai-gateway from feasy898/agentic-factory-projects@main (2026-10-01 snapshot)`，`git log` 实测）；**33 个文件被修改未提交**（`git status --short | wc -l` = 33，实测），比 `evidence/gate-final-20261002.md:38` 留档时的 28 个又多 5 个（S2 修复轮产物：`outguard/moderation.py`、`outguard/service.py`、`ops/name_lint.py`、`ops/export_public.py`、`.gitignore` 等）；`evidence/` 目录已被修改后的 `.gitignore` 追加排除（`git check-ignore evidence/` 命中；`git diff .gitignore` 显示新增第 48-49 行 `evidence/`）。
- 语言/依赖：Python ≥3.12（`pyproject.toml:10`），核心依赖 fastapi/uvicorn/httpx/pydantic/pyyaml/jinja2/python-multipart/python-docx/openpyxl/pypdfium2/pikepdf/PyMuPDF/faker（`pyproject.toml:14-28`）；冻结真相 `constraints.txt`（73 行 pip freeze）。可选组：dev/ocr/ml/bench（`pyproject.toml:30-48`）。
- 规模：约 2.6 万行 Python（`wc -l` 实测 26292 行，含 evals 与 ops）。
- 验收体系：`evals/` 19 个可执行入口（`python -m evals.*`，exit 0 = 通过）+ `ops/` 八个门脚本（gate_d0/b1..b6/final）+ `ops/name_lint.py` 名称守卫 + `ops/export_public.py` 公开导出。
- 运行态工件（gitignore，不入库）：`data/audit.db(+wal/shm)`、`data/session_map.db`（`git check-ignore` 实测命中）、`tmp/wf/` 115 份运行日志、`data/bench/quality_report.json`（实为受 git 管理面之外的本地工件；见 §5-6 关于其 git 跟踪状态的注记）。
- 工作区根附带物（一句话）：
  - `_upstream/` = 上游来源快照（`agentic-factory-projects-main/` 目录 + `repo.tar.gz`，即 git 提交信息所述的导入来源），非本项目实现代码，未逐文件走查；
  - `wf_run.py` / `wf_env.py` = 动态工作流的命令包装器（`wf_run.py:1-9` 自述「纯 argv 子进程，绝不经过 shell」，解决 Windows 双层 shell 问题），与仓库功能无关。

---

## 2. 组件清单（总表）

| # | 组件 | 目录 | 声明能力（README/docs 原话要点） | 实际实现（关键入口） | 对外接口 / 依赖 | 成熟度 |
|---|---|---|---|---|---|---|
| 1 | common 基础设施 | `common/`（272 行） | 「配置加载、结构化日志等跨模块基础设施」（README.md:21） | `common/config.py:108` `load_app_config`（YAML+env 覆盖，密钥字段豁免 `common/config.py:91,96-97`）；`common/logs.py:34` JsonFormatter（JSON 行/UTC/禁原文红线 `common/logs.py:5-7`）；`common/timeutil.py:15` `iso_utc` 定长 UTC 存储 | 被全仓 import；依赖 pydantic/yaml | **已实装** |
| 2 | gateway 网关主链 | `gateway/`（2371 行） | 「OpenAI 兼容网关与流式还原」（README.md:22）；「detect→mask→route→转发→还原→outguard→audit 主链，流式 SSE 三段管线」（docs/assets/manifest.md:23） | `gateway/app.py:202` `create_app`（端点全表 `gateway/app.py:3-47`）；主链 `gateway/pipeline.py:283` `GatewayService`（`handle_chat` :332 / `handle_chat_stream` :414 / `_prepare` :573）；SSE 组合管线 `gateway/sse.py`；上游适配 `gateway/provider.py:14`；管理面 `gateway/admin_api.py`；mock 上游 `gateway/mock_upstream.py` | `/v1/chat/completions`、`/v1/models`、`/v1/files/*`、`/admin/api/*`、`/internal/*`、`/healthz`、`/webui/*`（docs/assets/specs/gateway-main-chain.md §5） | **已实装** |
| 3 | recognizers 三层识别 | `recognizers/`（约 1230 行） | 「识别（规则 + 校验位 + 语义词表已实装）……NER（人名/住址模型化识别）为适配器预留位」（README.md:7） | 规则层 `recognizers/rule/detect.py`（561 行，`detect` :433 起检测全序，影子扫描 `detect.py:22-24`，校验位常量 `detect.py:108-117`）；白名单 `recognizers/rule/whitelist.py`；语义层 `recognizers/semantic/{patterns,adapter,judge}.py`（STRONG/EXFIL/WEAK 三档 + env 驱动 judge）；组合入口 `recognizers/pipeline.py:18` `detect_full` | `detect_full(text)->list[Finding]`，`moderate(text)->{verdict,categories}` | **已实装**（ner/ 适配器为**显式占位**，见 §4） |
| 4 | masking 可逆脱敏 | `masking/`（982 行） | 「会话稳定可逆脱敏：占位符按密钥哈希固定，多轮不变号；号码归一化；流式缓冲还原；工具调用参数还原」（README.md:8） | 冻结算法 `masking/mapper.py:186-220`（HMAC-SHA256+升位 (8,10,12) `mapper.py:36`）；容错改形还原 `mapper.py:78-164`（T8.4）；归一化 `masking/normalize.py:52-84`；流式状态机 `masking/remap.py`（缓冲上限 48 `remap.py:41`）；工具缓冲 `masking/toolbuf.py:50`（阀 1,000,000 字符）；双层存储 `masking/session_store.py` | `SessionMapper.mask/restore`、`StreamRestorer(lookup)`、`SessionStore`（SQLite masking_map + TTL） | **已实装** |
| 5 | routing 敏感度路由 | `routing/`（206 行） | 「敏感度路由：普通脱敏走互联网模型，敏感个人信息/工作秘密切政务云，命中密级标识直接拦截」（README.md:9）；R1–R6 矩阵（docs/assets/specs/routing-matrix.md:9-18） | 纯函数 `routing/engine.py:69` `decide`（优先级 BLOCK>GOVCLOUD>INTERNET `engine.py:3`；白名单不参与计数 `engine.py:83-89`；BLOCK 恒 null upstream `engine.py:139-143`）；模型 `routing/models.py`（RouteDecision `extra="forbid"`） | `decide(findings, upstream_for, batch_pii_min) -> RouteDecision` | **已实装** |
| 6 | outguard 输出侧 | `outguard/`（397 行） | 「输出侧：AI 生成标识（显式+隐式元数据）、代答/拒答库」（README.md:11） | AI 标识 `outguard/label.py:38` `apply_message_label`（尾注+annotations+响应头 `x-anongw-ai-label` :19，幂等 :47-51）；文案库 `outguard/fallback.py`（YAML+内置默认双份一致）；复检钩子 `outguard/moderation.py:36-55`（协议+`NullModerator` 恒 safe）；门面 `outguard/service.py:59` `moderate`（redact 承接+旧式后端兼容 `service.py:36-37,69-71`） | `OutguardService.block_reply/moderate` | **已实装**（复检后端 P0 为 NullModerator 占位，语义审核模型 P1 未接入——显式声明） |
| 7 | filechannel 文件通道 | `filechannel/`（1721 行） | 「文件通道：Word/Excel/PDF/扫描件"公开前体检"，一键导出彻底删除版」（README.md:10） | 体检 `filechannel/inspect.py:1-30`（50MB 闸→解析→detect 全套→装配→分级）；解析 `filechannel/parsers.py`（docx 全位面/xlsx 隐藏面/pdf charbox）；OCR `filechannel/ocr.py`（300dpi 渲染+纯 CPU OCR `config/filechannel.yaml:31-43`）；导出 `filechannel/sanitize.py`（docx 删 run / xlsx 删值+隐藏列整列删 / pdf 引擎链 / scan_pdf 重打码）；引擎链 `filechannel/pdf_engine.py`（涂删→内容流手术→栅格兜底，逐引擎 re-ingest 复核不净回退，链尽 `ExportBlockedError`） | `FileService.inspect_bytes/export_bytes`（`filechannel/service.py:85,97`）；端点 `/v1/files/inspect|export` | **已实装**（引擎名只进 config，importlib 动态加载；引擎缺失显式报错） |
| 8 | audit 审计 | `audit/`（912 行） | 「审计看板：按部门统计拦截，导出保密自查报告」（README.md:12）；「日志只存脱敏内容」（README.md:3） | 零明文双闸 `audit/store.py:57` `assert_no_raw_pii`（归一化+表面形式同查+截断边界守护 :75-83）、`store.py:131` `assert_db_no_raw_pii`（含 -wal/-shm/死信 `store.py:114-128`）；写队列 `audit/writer.py`（WAL+批量+死信文件）；查询 `audit/query.py` + `gateway/admin_api.py` | `AuditSink.append(event, normalized_values)`；`/admin/api/audit|metrics|report.csv` | **已实装** |
| 9 | benchmark 测评基准 | `benchmark/generator/`（2438 行） | 「测评基准：合成测评集（结构化号码召回 ≥99.5%，实测 100%；CPU 2000 字 <100ms）；多基线对比与人名/住址 NER 的 F1 验收门为规划项」（README.md:13） | 确定性生成器 `benchmark/generator/build.py:26` `build_all(seed,outdir)`（评测集+15 夹具+manifest sha256 凭据）；14 类政务模板 `templates.py`；自研校验位号码 `numbers.py`；质量评测 `evals/m8_quality.py`（已实现）；**基线对比 m8_baselines 未实现**（CONTRACTS.md:149 痛点#2、docs/assets/specs/benchmark-generator.md:49-55 如实登记） | `python -m benchmark.generator`；evals.m8_generator/m8_quality | **部分实装**（generator 与 m8_quality 已实装；m8_baselines 规划态，未入六门） |
| 10 | webui 演示前端 | `webui/`（550 行 + 5 模板） | 「webui/ 演示前端页面」（README.md:29） | 五页 `webui/pages.py:1-30`（首页/体检/演示控制/双屏聊天/看板）；看板聚合 `webui/dashboard.py`（手写 SVG，文本 `html.escape` 防注入 `dashboard.py:20`）；演示态 API `webui/demo_api.py`（seed/clear/state，走审计 sink+参数绑定 SQL `demo_api.py:22-27`） | `GET /webui`、`/webui/files|demo|chat|dashboard`、`/webui/demo/materials/*`、`POST /admin/api/demo/*` | **已实装** |
| 11 | ops 运维/验收 | `ops/`（约 4800 行） | 「ops/ 运维工具：名称守卫、克隆脚本、e2e 冒烟、公开导出」（README.md:30） | 门脚本 ×8（`gate_d0/b1..b6/final`，标准库任意 cwd 可跑 `gate_final.py:24-27`）；`e2e_smoke.py`（八用例 U1–U8 真端口拓扑）；`name_lint.py`（禁用词守卫，严格档扫 yaml/json）；`export_public.py`（git 跟踪面导出+_BY_DEPLOYER_ 置换+严格档终检）；`seed_demo.py`（三部门演示数据走生产同链路）；`tunnel_gpu.sh`、`clone_oss.sh`；`demo/` 场景脚本（scene4/5 就绪，**scene1-3 待补** `ops/demo/README.md:7-14`） | `python ops/gate_*.py`；`python -m ops.name_lint` | **已实装**（演示场景 1-3 成文脚本待补，如实标注） |
| 12 | evals 验收入口 | `evals/`（8218 行） | 「evals/ 可执行验收入口（python -m evals.*，exit 0 = 通过）」（README.md:31） | 19 个入口：m0_infra(20)/m2_recognizers(6)/m2_semantic(11)/m3_masking(9)/m4_routing(43)/m5_outguard(13)/m6_filesvc/m6_ocr/m7_audit(17)/m8_generator/m8_quality(6)/m9_webui/m10_e2e(八用例)/m11_robust(7)/t0_gateway/t0_stream/t0_labels/t0_mock_upstream/u8_repro；阈值单一来源 `evals/thresholds.py`（98 行常量） | `python -m evals.<name>` | **已实装**（**无 m8_baselines 文件**——与 CONTRACTS/规格「规划态」声明一致） |
| 13 | gpu 部署脚本 | `gpu/`（2 个 .sh） | 「部署/保活见 gpu/」（config/app.yaml:13） | `gpu/setup_llm_service.sh`（GPU 机一次性预置：权重经 `LLM_HF_REPO` 环境变量下载、模型名不入仓库 `setup_llm_service.sh:9-12`）；`gpu/llm_keepalive.sh`（:9004 保活循环，装载中不杀护栏 `llm_keepalive.sh:8-10`） | GPU 机侧 bash 脚本（部署侧，非库代码） | **已实装**（部署侧脚本形态；本机无 GPU，脚本逻辑未在本机执行验证——**未验证**） |
| 14 | gpu-services 真实上游服务 | `gpu-services/llm_openai/`（737 行 + run_gpu.sh） | 「GPU 机本地大模型 OpenAI 兼容服务（FastAPI，:9004；政务网关批次 6 上游）」（gpu-services/llm_openai/service.py:1）；「internet_real/govcloud_real profiles」（config/app.yaml:18-19） | `service.py`（/health、/v1/chat/completions 流/非流、请求 ring buffer 供脱敏断言、Authorization 只记 sha256 前 8 位指纹 `service.py:27-31`）；`run_gpu.sh`（start/stop/restart/status，幂等，fp16+sdpa 约束 `run_gpu.sh:2-5`） | OpenAI 兼容 :9004；经 `ops/tunnel_gpu.sh` 隧道访问 | **已实装**（服务代码在仓；运行依赖 GPU 机环境，本会话未起服——**未验证**） |

> 附：`out/public-export/` = `ops/export_public.py` 的导出产物镜像（159 文件量级，`README.public.md`、`DEPS.txt`、`_BY_DEPLOYER_` 置换后 config），按导出产物对待，未逐文件走查。`tmp/`（diag/probe 脚本与运行日志）、`gov_anon_gateway.egg-info/`（构建产物）均为本地工件。

---

## 3. 逐组件走查要点（声明 vs 实现）

### 3.1 common（已实装）
- 声明：「配置加载、结构化日志等跨模块基础设施」（README.md:21）；契约 C7「密钥不入配置文件：只写环境变量名，运行时 resolve_secret()」（docs/assets/CONTRACTS.md:140-141）。
- 实现：`load_app_config` 支持 `ANONGW_<K>` env 覆盖且**密钥变量名字段豁免覆盖**（`common/config.py:91` `_SECRET_ENV_FIELDS`，覆盖循环跳过 `:96-97`——防 `ANONGW_ADMIN_KEY_ENV=ATTACKER_VAR` 把硬闸改指到攻击者变量，fail-open 封死）；`resolve_secret`（`common/config.py:135-145`）缺失即抛错（required=True）；部门 key 只存 sha256 且 64 位 hex 校验（`common/config.py:127-129`）；`.env` 预载不覆盖已有环境变量（`common/config.py:148-166`）。日志红线「禁止记录任何未脱敏原文」（`common/logs.py:5-7`），JSON formatter 对业务 extra 全并入（`common/logs.py:44-51`）。
- 支撑：`evals/m0_infra.py` 20 项（本会话实跑 20/20 PASS，含 `config:env-override` 负例与 `contract:extra-forbid-negative` 9+3 模型）。

### 3.2 gateway（已实装）
- 声明：主链八步 + 流式三段管线 + 「出站全量检测面——messages/stream 之外无任何原样透传面」（`gateway/pipeline.py:19-23`）；端点全表（docs/assets/specs/gateway-main-chain.md §5）。
- 实现核对：
  - 主面/辅助面双检测：content 文本段 `_content_segments`（`gateway/pipeline.py:157-169`）；辅助面 `_aux_texts` 覆盖 tools、历史 tool_calls/function_call、消息级非 content 字段（含 `name` 与任意自定义字段）、非 text 多模态段、顶层标量与 dict/list 字段**及 dict 键**（`gateway/pipeline.py:195-239`，`include_keys=True` :220,231,238）；重建 `_apply_aux_masked` 键换名仅当键原文命中映射（`gateway/pipeline.py:242-257`）——S2 修复 1/2 条（evidence §7.1）已落在工作区。
  - 先校验后绑定：`handle_chat`/`handle_chat_stream` 均 `_validate_body` → `_bind_session`（`gateway/pipeline.py:340-341,419-420`），400 垃圾请求不留属主绑定；`_bind_session` 跨部门 403（`gateway/pipeline.py:314-329`）；`/internal/restore` 只认属主（`gateway/app.py:518-525`）。
  - 流式：BLOCK/上游不可达/协议错误开流前决出（`gateway/pipeline.py:439-484`）；开流后以 SSE 错误事件收尾（tool 溢出 :505-515、断流 :516-524）；流收尾对**还原后**全文复检「检测+留痕」语义（:528-550，delta 已放行不可追回——契约声明 `gateway/pipeline.py:27-31`）；SSE 收尾残片同进 `on_content`+`on_restored`（`gateway/sse.py:203-210`，S2 修复 #9）。
  - 审计：`_audit` 事件构造 + 硬闸（`gateway/pipeline.py:909-924`）；密级词/注入词在预览中以 `〔密级·已拦截〕/〔注入·已拦截〕` 占位（`gateway/pipeline.py:104-107,782-787`）；响应预览走 `_safe_response_preview`（检测+脱敏后再截断，`gateway/pipeline.py:791-815`——真实模型自由文本写出的 PII 不得明文入库）。
  - 鉴权：部门 key sha256 + `hmac.compare_digest` 常量时间比较（`gateway/deps.py:27-33`）；admin key 硬闸（`gateway/app.py:261-266`，配置后 `/admin/api/*` 只认 admin key）。
  - 有界读取：Content-Length 预检+流式累计+超限有界排空（`gateway/app.py:117-181`）；JSON 深度帽 64、单文本帽 200,000 字符（`evals/thresholds.py:91-92`）。
- 支撑：t0_gateway 15/15、t0_stream 14/14（evidence §7.3 记录 10-03 15:43–15:54 复跑全绿；本会话未复跑——见 §6）。

### 3.3 recognizers（已实装；ner 显式占位）
- 声明：19 类 EntityClass + 9 子类型（recognizers-rule spec §2）；检测 11 步全序 + token 分类序（熵串>证件>卡号>电话）；「NER 为适配器预留位」（README.md:7）。
- 实现：`recognizers/models.py` 枚举（19+9）；`detect.py` 影子扫描（全角→半角 1:1 span 对齐 `detect.py:22-24`）、GB11643/GB32174/Luhn 校验位（`detect.py:108-117`）、置信度 1.0/0.5 双轨（docstring `detect.py:25-27`）、DATE_BIRTH 出生上下文门控、机构名后缀抑制（`detect.py:104-106`）、PERSON 双轨（词表 1.0 + 姓氏启发式 0.5 + 停用词表 `detect.py:86-102`）；白名单四类（热线/单位座机段/公开文号/公开称谓钩子，`config/whitelist.yaml` + `recognizers/rule/whitelist.py`）。
- 语义层：三档词表 `config/injection_terms.txt`（49 行，STRONG/EXFIL/WEAK 行格式）+ 否定前缀守卫（8 字符窗）+ WEAK 位置佐证；judge env 三变量齐备才启用、故障降级不抛错（`recognizers/semantic/judge.py:1-12`）；judge 补判前先按规则层命中把 PII/密级词换中性占位（`recognizers/pipeline.py:21-24`——原文不在判定前出网）。
- **占位确认**：`recognizers/ner/adapter.py:29-31` `detect` 恒返回空列表；有 `model_path` 时仅记 debug 日志「显式声明未加载，而不是假装可用」（`adapter.py:8-10,26-27`）。
- 支撑：m2_recognizers 6/6（**本会话实跑**：structural micro=1.0000（618/618）、FPR=0/22、延迟 mean 3.21ms）、m2_semantic 11/11（**本会话实跑**：注入召回 1.0000×34、误拦 0/45、judge 降级路径）。

### 3.4 masking（已实装）
- 声明：§5.3.1 占位符算法一字不差 + DIGEST_WIDTHS(8,10,12) + T8.4 容错改形还原 + 流式 ≤48 字符缓冲 + 工具 hold-to-finish（docs/assets/CONTRACTS.md:68-78、manifest.md:25）。
- 实现：`_digest` HMAC-SHA256(key=MASK_KEY, msg=`session_id\x1f type\x1f normalized`)（`masking/mapper.py:47,186-188`）；插入期碰撞升位 8→10→12、12 位仍碰撞抛 RuntimeError、同值再到达复用升位条目（`mapper.py:196-220`）；`restore` 走 `restore_tolerant`（`mapper.py:233-240`）：开括号变体 5 种/闭 5 种/间隔号 8 种、噪声剥除、NFKC+易混字符兜底、查表命中才替换（`mapper.py:59-99`）；泄漏检测面 `tolerant_placeholder_hits`（`mapper.py:141-164`）；流式 `StreamRestorer` 缓冲恒 ≤48（`masking/remap.py:41`，与 `mapper.py:65` 同源）；工具缓冲阀 1,000,000 字符、超限抛 `ToolArgumentsOverflowError` 且状态保留（`masking/toolbuf.py:44-53`）；双层存储：LRU(1024)+SQLite masking_map(主键 (session_id,placeholder))+TTL 24h，与审计库**分文件**（`masking/session_store.py:1-27`、config/app.yaml:32-35）；属主绑定 `_owners` 有界（2×LRU 裁最老，`mapper.py:313-330`，S2 修复 #7）。
- 支撑：m3_masking 9/9（**本会话实跑**：稳定性 1000 值、流式 fuzz 500 条、改形 11 形态+4 负例、10 万值 0 最终碰撞、还原 0.437ms<20ms）。

### 3.5 routing（已实装）
- 声明：R1–R6 六行矩阵、43 格验收（docs/assets/specs/routing-matrix.md）。
- 实现：`routing/engine.py:69-144` 与 spec 逐条吻合——白名单不参与 R3/R4/R5 计数但 BLOCK_FLAG 照拦（`engine.py:61-66`）、reasons 有序第一条决定性、BLOCK 逐命中带表面形式（截断 ≤24 字 `engine.py:53-58`）、INTERNET 聚合单条、WHITELIST_HIT 留存条不含原文（`engine.py:122-133`）、BLOCK 恒 upstream=None（`engine.py:139-143`）；12 码值结构化 PII 名单（`engine.py:44-50`）。
- 支撑：m4_routing 43/43（**本会话实跑**，38 矩阵格+5 横切全过）。

### 3.6 outguard（已实装；复检后端 P0 占位）
- 声明：AI 标识三面（尾注+annotations+响应头，幂等）、按 reason code 拒答+关键词代答、复检钩子 P0 NullModerator（outguard spec §1-3）。
- 实现：`outguard/label.py:38-51` 幂等注入；`outguard/fallback.py` YAML 缺失回落内置默认（与 `config/outguard_texts.yaml` 内容一致，实读核对一致）；`outguard/moderation.py:48-55` `NullModerator.moderate` 恒 `safe`（redact 仅声明承接不调用）；`outguard/service.py:36-37` 按后端签名判定是否传 redact（旧式后端兼容）；**P1 语义审核模型后端未接入**（`moderation_model` 留空 `config/app.yaml:27`）——接口与调用点（非流式 `gateway/pipeline.py:400,870-896`、流式 :537-550）已接线。
- 支撑：m5_outguard 13/13（evidence §7.3 留档复跑 10-03；本会话未复跑）。

### 3.7 filechannel（已实装）
- 声明：FileReport/FileFinding §5.5 冻结形状、location/bbox 位置语义、风险分级、**导出零残留是管线内硬闸**（docs/assets/specs/filechannel-locations.md §6、REGENERATE.md:109-110）。
- 实现：50MB 闸→解析（docx 正文+表格嵌套+页眉页脚；xlsx 含隐藏表/隐藏行列/公式缓存/批注；pdf 逐字符 charbox；scan_pdf 整页零文本走 OCR）→detect 全套→装配→分级 HIGH/MID/LOW/NONE（`filechannel/inspect.py` docstring :1-30）；导出 `*_verified` 入口就地 re-ingest 复核、非白名单残留继续清理/回退、`SANITIZE_MAX_PASSES=3`、链尽报 `ExportBlockedError`（`filechannel/sanitize.py:1-23`）；pdf 三引擎链（涂删主引擎/内容流算子级删除/栅格兜底）惰性加载（`filechannel/pdf_engine.py:1-25`）；scan_pdf 重打码渲染版+再 OCR 复核（`service.py:106-109`）；报告登记表内存 LRU 128（`service.py:46,123-126`）。
- 引擎名只进 config：`config/app.yaml:31 pdf_engine_module: pymupdf`、`config/filechannel.yaml:6-27`（pypdfium2/pikepdf/PIL/rapidocr），源码 importlib 动态加载（铁律 E）。
- 支撑：m6_filesvc 12/12、m6_ocr 6/6（evidence §3 表 #8/#9 与 §7.3 留档；本会话未复跑）。

### 3.8 audit（已实装）
- 声明：AuditEvent §5.4 冻结（无 raw 字段）、零明文双闸、WAL、管理面查询模型（audit-schema spec）。
- 实现：`assert_no_raw_pii` 归一化+表面形式同查、500 字符截断边界守护（`audit/store.py:57-83`）；`safe_preview` 截断点回退到敏感串起点（`store.py:86-111`）；全库 bytes 级扫描覆盖主文件/-wal/-shm/死信文件（`store.py:29-34,114-128`，死信纳入是 S2 修复 #5）；写队列入队前过闸、队列饱和抛错拒写、INSERT 失败落死信文件（`audit/writer.py:1-22`）；查询面 `audit/query.py`（326 行）+ `gateway/admin_api.py`（分页 100/1000 钳位、CSV utf-8-sig）。
- 支撑：m7_audit 17/17（**本会话实跑**：WAL/schema/30 事件往返/重开直读/硬闸负控/死信入扫描集/管理面 20 请求聚合/CSV/鉴权负例/分页钳位全过）。

### 3.9 benchmark（部分实装）
- generator 已实装：`build_all(seed,outdir)` 三件套+manifest sha256 凭据、14 类模板（`benchmark/generator/__init__.py:6-24` 自述 10→14 类）、自研校验位号码（澄迈 469023 前缀 `geo.py`）、扰动器 6 类、夹具 seed 异或盐。
- m8_quality 已实现：`evals/m8_quality.py`（550 行，6 检查项，需 :9004 真实上游；离线=DEFERRED 不计失败 `m8_quality.py:6`）；落盘 `data/bench/quality_report.json`（实读：ratio=1.0、f1_masked_mean=0.9943、orig/masked p95=2438/2763ms、50 对——mtime 2026-10-03 19:49，最近一轮产物）。
- **m8_baselines 未实现**：evals/ 无该文件；`docs/assets/specs/benchmark-generator.md:49-55` 与 `docs/assets/CONTRACTS.md:149`（痛点#2）如实登记为规划态、未入六门。README.md:13 也如实声明「多基线对比……为规划项」。
- 支撑：m8_generator 4/4（evidence §3 #11 与 §7.3 留档；本会话未复跑）。

### 3.10 webui（已实装）
- 五页 + 双屏对照（右栏经 `/internal/anonymize` 取脱敏视图 `webui/pages.py:14-17`）+ 看板（服务端直读审计存储、分页在 Python 内存 `webui/dashboard.py:5-8`；SVG 文本 escape）+ 演示态 API（写路径走审计 sink+参数绑定 SQL，无拼接 `webui/demo_api.py:24-27`）；`/webui/dashboard` 仅回环渲染（`webui/pages.py:32` 注明审查加固）；页面不渲染 key 明文（`webui/pages.py:30-31`）。
- 支撑：m9_webui 16/16（evidence §7.1 #3 与 §7.3 留档；本会话未复跑）。

### 3.11 ops（已实装）
- 八门脚本结构：标准库、任意 cwd、chdir 仓库根+PYTHONUTF8、`.venv` 执行各项、摘要行抓取不重算判定（docs/assets/specs/gates.md §1）；超时预算 900/1200/1800/3600/5400s（gates spec §3、`ops/gate_final.py:44-46`）。
- `e2e_smoke.py`：八用例 U1–U8；U8 真实链路离线如实 DEFERRED；端口清理只碰本仓标识进程（`ops/e2e_smoke.py:24-40` 拓扑自述）。
- `name_lint.py`：豁免面收窄为仓库根固定坐标（`ops/name_lint.py:21-24`）；默认档不扫配置、严格档扫（公开导出终检用）。
- `export_public.py`：git ls-files 过滤→constraints.txt/clone_oss.sh 不分发→依赖行剔除/_BY_DEPLOYER_ 置换→严格档零命中才交付（`ops/export_public.py:1-30`）。
- `seed_demo.py`：演示数据走生产同链路（`_prepare`+`_audit` 镜像），仅 ts/latency 给定、跳过上游转发（`ops/seed_demo.py:19-25`）。
- 支撑：evidence/gate-final-20261002.md 全文即为 ops 门禁体系的运行留档（v3，2026-10-03 18:39 修订）。

### 3.12 evals（已实装）
- 19 入口 + thresholds 单一来源（`evals/thresholds.py` 全量实读，98 行常量与 spec §3 表一致）。
- **本会话实跑 6 个全绿**（§6）；其余 13 个未复跑，以 evidence §7.3（10-03 15:43–15:54 十份独立日志全绿）+ tmp/wf/ 留档为支撑。

### 3.13 gpu / 3.14 gpu-services（已实装，部署侧）
- `gpu/`：2 个部署脚本（权重预置+保活），**均非 Python 库代码**；模型真实名经 `LLM_HF_REPO` 环境变量注入、未设置即报错退出（`gpu/setup_llm_service.sh:12`），公开仓库卫生口径与 config/app.yaml:15 一致。
- `gpu-services/llm_openai/`：732 行 FastAPI 服务（OpenAI chat 子集+ring buffer+key 指纹）+ `run_gpu.sh`（幂等进程管理，可选 `forward_key` 文件注入最小鉴权 `run_gpu.sh:19-23`）。
- 本会话均未起服执行（无 GPU 环境）——功能面**未验证**，仅有代码级走查 + evidence §6③ 记录的 :9004 多次实际跑通（U8 真实 PASS、m8_quality 6/6 出数）。

---

## 4. README 量化/能力声明逐条核对

| # | 声明（出处） | 代码实现 | 测试支撑 | 判定 |
|---|---|---|---|---|
| 1 | 结构化号码校验位召回「实测 100%」（README.md:7）+「≥99.5%，实测 100%」（README.md:13） | `recognizers/rule/detect.py`（GB11643/GB32174/Luhn）；阈值 `evals/thresholds.py:12-13`（RECALL_STRUCTURAL=1.00 / RECALL_PATTERN=0.99） | `evals/m2_recognizers.py` `check_recall`（:128 起，归一化等价+span 保真）；**本会话实跑：structural micro=1.0000（618/618），6/6 PASS**；evidence §5 三次门内运行均 1.0000 | **有测试支撑（本会话复现）** |
| 2 | CPU 2000 字 <100ms（README.md:13） | `evals/thresholds.py:15` RULE_LATENCY_MS_2000CH=100 | `evals/m2_recognizers.py` latency 检查；**本会话实跑：2000ch ×10 mean 3.21ms (max 3.79ms)**；evidence §5 mean 1.91–9.63ms | **有测试支撑（本会话复现）** |
| 3 | 会话稳定可逆脱敏：占位符按密钥哈希固定，多轮不变号（README.md:8） | `masking/mapper.py:186-220`（HMAC+同值复用）；`session_store.py`（LRU+SQLite+TTL，重启 hydrate） | `evals/m3_masking.py` `step_stability`（:109，1000 值 repeat/replay 全等+跨 session 不同+round-trip）；**本会话实跑 PASS**；m7_audit 会话存储 C 节 17/17（**本会话实跑**） | **有测试支撑（本会话复现）** |
| 4 | 流式缓冲还原（README.md:8） | `masking/remap.py`（缓冲 ≤48 有界）；`gateway/sse.py` 组合管线 | `evals/m3_masking.py` `step_stream_fuzz`（:203，500 条 1–7 字符切块==整段还原+缓冲帽断言）+`step_mangled_forms`（11 改形形态）；**本会话实跑 PASS**；t0_stream 14/14（留档） | **有测试支撑（m3 本会话复现；t0_stream 留档）** |
| 5 | 工具调用参数还原（README.md:8） | `masking/toolbuf.py`（hold-to-finish+阀 1M）；`gateway/pipeline.py:841-853`（非流式 tool_calls/function_call 整体还原） | `evals/m3_masking.py` tool 三检查（:356,380,441：127 字符 29 片、全切分扫描+200 种子 fuzz、溢出阀响亮失败）；**本会话实跑 PASS** | **有测试支撑（本会话复现）** |
| 6 | 敏感度路由：密级标识直接拦截（README.md:9） | `routing/engine.py:61-66,93-99`（R1 BLOCK）；BLOCK_FLAG 不受白名单豁免；`gateway/pipeline.py:360-366`（403+文案库） | `evals/m4_routing.py` R1 8 格（**本会话实跑 43/43**）；`evals/m5_outguard.py` `e2e:block-classified`（留档 13/13）；t0_gateway 密级拦截项（留档 15/15） | **有测试支撑（m4 本会话复现；m5/t0 留档）** |
| 7 | AI 生成标识：显式+隐式元数据（README.md:11） | `outguard/label.py:28-51`（尾注+annotations+`x-anongw-ai-label` 头）；流式 `gateway/sse.py` finish delta.annotations；`gateway/pipeline.py:405-409,487-489` | `evals/m5_outguard.py` label/e2e 标识检查（留档 13/13，含流式/幂等/自定义文案/空文案零注入）；`evals/t0_stream.py` `stream:normal-restored-labeled`（evidence §3 #13 PASS） | **有测试支撑（留档；本会话未复跑）** |
| 8 | 彻底删除导出（README.md:10）；导出物零残留 | `filechannel/sanitize.py`（`*_verified` 管线内硬闸，`ExportBlockedError` 宁阻不漏）；三引擎+重打码 | `evals/m6_filesvc.py` 第 8 节（:570 起）「导出→re-inspect 零残留」+ `FILE_EXPORT_RESIDUAL_ALLOWED=0`（`evals/thresholds.py:52`）；m6_filesvc 12/12、m6_ocr 6/6（evidence §3 #8/#9 留档） | **有测试支撑（留档；本会话未复跑）** |
| 9 | 语义词表（越狱/注入）+ 注入拦截（README.md:7） | `recognizers/semantic/{patterns,adapter,judge}.py`；R2 → BLOCK | `evals/m2_semantic.py` 11 检查；**本会话实跑 11/11**（direct/indirect/tooldesc 召回 1.0000、误拦 0/45、judge 降级） | **有测试支撑（本会话复现）** |
| 10 | 审计「日志只存脱敏内容，全程可审计」（README.md:3,12） | `audit/store.py` 双闸 + `gateway/pipeline.py:791-815,909-924`（预览脱敏+硬闸） | `evals/m7_audit.py` 17/17（**本会话实跑**，含负控毒行+全库 bytes 扫描）；e2e U5 三重扫描 0 命中（evidence §5：65,536/77,824/90,112 字节均 0 命中，留档） | **有测试支撑（m7 本会话复现；e2e 留档）** |
| 11 | NER（人名/住址模型化识别）为适配器预留位（README.md:7） | `recognizers/ner/adapter.py:29-31` 恒空 + 显式 debug 日志 | 无（声明本身即「未实装」） | **如实声明的占位（非缺陷）** |
| 12 | 多基线对比为规划项（README.md:13） | evals/ 无 m8_baselines | CONTRACTS.md:149 痛点#2、benchmark-generator.md §4 登记 | **如实声明的规划项** |
| 13 | 「评测集（结构化号码召回 ≥99.5%，实测 100%）」（README.md:13）评测基准可用 | `benchmark/generator/build.py` 确定性生成 372 例 | `evals/m2_recognizers.py` case-scale（372 cases：detect=300/whitelist=46/reject=26，**本会话实跑 PASS**）；m8_generator 4/4（留档） | **有测试支撑（m2 侧本会话复现；m8_generator 留档）** |
| 14 | 会话与部门绑定、跨部门还原 403（README.public.md:115-117） | `gateway/app.py:477-483,518-525`；`gateway/pipeline.py:314-341` | `evals/t0_gateway.py` `session:owner-binding`（evidence §7.1 #3 留档 PASS）；`masking/mapper.py:313-335` 属主有界（tmp/probe_owner_bounds.py 留档 PROBE PASS） | **有测试支撑（留档；本会话未复跑）** |
| 15 | 管理面 admin key 硬闸 / dashboard 回环闸（README.public.md:118-121） | `gateway/app.py:261-266`；`webui/pages.py`（回环判定） | `evals/m9_webui.py` `check_admin_key_hard_gate`(:496)/`check_webui_dashboard_loopback_only`(:477)（evidence §7.1 #3 留档 PASS） | **有测试支撑（留档；本会话未复跑）** |
| 16 | 「本地模式全离线可跑」（README.public.md:13-14） | mock 上游回显+ring buffer（`gateway/mock_upstream.py:1-25`）；eval 全本地 | m10_e2e 8 PASS/0 FAIL/0 DEFERRED（evidence §7.3 留档 1791013906656）；本会话未复跑 | **有测试支撑（留档）** |
| 17 | docker compose（README.public.md §4） | `docker-compose.yml` | 文件头 :6-7 **自报未实测**（构建环境无 Docker，文档级交付物） | **如实声明的未实测项** |
| 18 | 质量比 ≥0.95（thresholds QUALITY_RATIO_MIN）——README 未直接引用数字，属 spec 承诺 | `evals/m8_quality.py`；落盘 `data/bench/quality_report.json`（实读 ratio=1.0、50 对、F1 orig=1.0/masked=0.9943、p95 2438/2763ms） | m8_quality 6/6（evidence §5/§7.1-S2A 留档出数）；依赖 :9004 | **有测试支撑（留档+落盘报告；本会话未复跑）** |

---

## 5. 占位/未实装、文档-代码不一致、配置与密钥隐患、脆弱点

### 5.1 占位与未实装（全部有显式声明，无静默假实现）
1. **NER 适配器**：`recognizers/ner/adapter.py:29-31` 恒空（预留 ONNX 路径）。开放域人名/住址识别依赖人名词表（4 个演示名 `config/person_names.txt:5-8`）+ 姓氏启发式（0.5 置信度、右边界约束、静态停用词表 `detect.py:86-102`）——`docs/assets/feedback.md:91-95`（R1）自认「演示人名现场穿帮」风险，缓解=预置输入纪律。
2. **输出复检后端 NullModerator**：`outguard/moderation.py:48-55` 恒 safe；`config/app.yaml:27 moderation_model: ""` 未配置。真实审核模型 P1 未接入（接口/调用点/redact 承接已就绪）。
3. **m8_baselines 三基线对比**：未实现（见 §3.9）。
4. **preserve_semantic 字段无消费方**：已入契约但恒 False（CONTRACTS.md:150 痛点#3 自认「形同虚设」，语义保留替换为 P1 规划）。
5. **docker-compose.yml 未实测**：文件头自报（:6-7）；README.public.md §4 同步如实声明。
6. **演示场景 1-3 脚本待补**：`ops/demo/README.md:7-14` 场景表标注「页面就绪/脚本待补」，仅 scene4/5 成文。
7. **公开导出面的 `_BY_DEPLOYER_` 功能缺失**：公开版 config 中 PDF 清理引擎/OCR 引擎/合成语料库坐标为占位，未配置前显式失败（README.public.md:103-106）——属导出语义设计，非缺陷。
8. **gpu/gpu-services**：代码在仓，但本会话无 GPU 环境未起服——运行面**未验证**（仅代码走查+留档佐证）。

### 5.2 文档与代码不一致（本盘点实测）
1. **CONTRACTS.md 痛点#1 已过时**：`docs/assets/CONTRACTS.md:148` 仍称「`_iter_string_leaves` 只递归 dict 的 values，字符串键不进检测面」为待批变更候选；但代码已实现键检测/换名（`gateway/pipeline.py:172-192` `include_keys` 参数、:220/:231/:238 调用、:242-257 键换名），S2 修复 #2 亦声明「保留，行为有 eval 佐证」（evidence §7.1）。CONTRACTS 痛点表未回填裁决——按其自身变更流程（CONTRACTS.md:153-162）应更新。
2. **labels.md 流式缓冲字长滞后**：`docs/contracts/labels.md:149` 写「流式还原状态机……≤32 字符缓冲」；代码与 masking spec 均为 48（T8.4 起 32→48：`masking/mapper.py:63-65`、`masking/remap.py:39-41`、`docs/assets/REGENERATE.md:106-108`）。labels.md 未同步。
3. **REGENERATE.md 旧仓库路径**：`docs/assets/REGENERATE.md:17,55,61-63` 写 `D:/workspace/澄迈8项目/政务AI脱敏网关/repo`；当前实际路径为 `D:/new-workspace/澄迈项目/政务AI安全/gov-anon-gateway`。命令需换路径执行。
4. **pyproject 的 tests 痕迹**：`pyproject.toml:65`（packages.find include `"tests*"`）与 `:77`（`testpaths = ["tests"]`）指向不存在的 `tests/` 目录（实测无该目录）；实际验收体系为 `evals/`（pytest 仅 `evals.m0_infra` 以 `-m pytest evals/m0_infra` 形态被 README.public.md:45 引用）。轻微不一致，不影响运行。
5. **README.md:15「仓库结构（建设中）」措辞**与 manifest.md 各模块全部 `frozen` 的状态表述存在时态差（README 头部未随进度更新；属陈旧措辞非错误声明）。
6. **quality_report.json 与 evidence 数值差异（不同轮次产物）**：`evidence/gate-final-20261002.md:197` 记 9/9 认证运行 f1_masked=0.9971、S2-A 记 1.0；在盘文件实读 `f1_masked_mean=0.9943`（mtime 10-03 19:49，最近一次 m8_quality 运行刷新）。属「该文件随每次运行刷新」的设计（`evals/m8_quality.py:93`），非错误，但引用数字时必须注轮次。

### 5.3 配置与密钥处理（合规面）
- **合规项（实测核对）**：密钥不入配置文件——`config/app.yaml` 只存环境变量名（`mask_key_env`/`api_key_env`，app.yaml:1-4）；`config/dept_keys.yaml` 只存 sha256（dept_keys.yaml:1-2，格式校验 `common/config.py:127-129`）；`.env` 已 gitignore（`git check-ignore .env` 命中）且本盘点未读取其内容；mock 上游「缓冲只记 Authorization 是否存在，不记录其值」（`gateway/mock_upstream.py:20-21`）；GPU 服务「Authorization 只记 sha256 前 8 位指纹」（`gpu-services/llm_openai/service.py:29-31`）；judge key 只经 env（`.env.example:26-32`）；日志禁原文红线（`common/logs.py:5-7`）；页面不渲染 key 明文（`webui/pages.py:30-31`）。
- **隐患 1（演示凭据入仓）**：三个演示部门 key 明文写在 `.env.example:21-24` 注释（`dk_1a2b3c4d`/`dk_5e6f7a8b`/`dk_9c0d1e2f`），并以常量存在于仓内 evals/ops 脚本。属**公开演示夹具凭据**，README.public.md:122-128（S2 修复 #8）已如实声明「生产部署必须更换哈希」——风险成立与否取决于部署纪律，留档在案。
- **隐患 2（会话库明文原值）**：`data/session_map.db` 按设计必须存归一化原值（`masking/session_store.py:14-17`），落盘为**未加密 SQLite**；该文件泄露=占位符全量反查。缓解=与审计库分文件（审计库可零明文扫描）、跨部门还原 403、TTL 24h；但静态看该库无静态加密（at-rest），物理/文件级泄露面如实记为残余风险。
- **隐患 3（`.env.example` 的 MASK_KEY 全零占位）**：`MASK_KEY=0000…0`（`.env.example:7`）——若部署者忘改且未显式报错（`resolve_secret` 只查存在性 `common/config.py:140-144`，全零值合法），占位符密钥即退化为可预测值。属「在位性校验」设计边界，静态记录。
- **隐患 4（/v1/files/* 无部门 Key 鉴权）**：`gateway/app.py:285-364` 两个文件端点不鉴权（设计口径：报告 raw 是上传者自带文件回显，`filechannel/service.py:19-22` 自述），但端点同时向任意调用方提供**检测能力**（findings 明细含 raw 回显）与导出能力。README.public.md 与 gateway-main-chain.md §5 均注明「生产部署仍应置于管理面/内网」——若按 README.public.md §2 直接 `--host 127.0.0.1` 监听则风险受控；若绑外网地址即为暴露面。
- **隐患 5（/internal/* 含还原原文）**：已做部门 Key+属主绑定+形态闸（`gateway/app.py:101-104` SESSION_ID_RE），且 README.md:38-41 明示「不得直接暴露公网」——设计内风险，依赖部署纪律。

### 5.4 明显脆弱点 / 工程风险
1. **代码态未提交固化（最高优先）**：33 文件未提交（`git status` 实测），含 S2 全部安全修复（`gateway/pipeline.py`、`masking/mapper.py`、`audit/store.py`、`common/config.py` 等）与 GPU 服务脚本；`evidence/gate-final-20261002.md:268` 自认漂移风险并催促提交。工作区一次误操作即丢失已验收代码态。
2. **整门 gate_final 未在 S2 后取得 9/9**：S2-A 1/9 FAIL（瞬时 U1 ConnectTimeout+U5 KeyError）、S2-B 2/9 FAIL（:9004 隧道中途掉线→DEFERRED 政策连环）（evidence §7.3 表）。11 条修复的逐模块 eval 全绿，但「9/9 整门+四项质量指标写入验收 JSON」的遗留动作未完成（evidence §7.3 本轮结论自认「未全绿」）。
3. **真实链路单点依赖 :9004 隧道**：config/app.yaml:18-19 两 real profiles 绑 127.0.0.1:9004；隧道掉线已两次导致整门 FAIL（evidence §6③/§7.3）；`docs/assets/feedback.md:63-70`（F4）自认并给出 mock 主口径+预录兜底缓解。
4. **JSON 键位之外的检测边界**：值面/键面已全覆盖（`_iter_string_leaves`+`_aux_texts`），但 WEAK 语义注入靠位置启发、词面类为静态词表（密级 6 词、人名 4 词），词表外新词漏检属规则层固有边界（labels.md §9-6 自认「密级词表仅 6 词」）。
5. **端口竞争约束**：9000/8901/8902 独占，多批次并行跑门会冲突（REGENERATE.md §4 坑 3）；本盘点期间工作区确有并行 eval 活动（tmp/wf 20:20 m10_e2e），佐证该约束的现实性。
6. **工作区根 `nul` 文件**：51 字节、内容为一条报错输出（`dir: cannot access '/b'`），Oct 3 18:47 生成——误操作残留工件，无害，建议清理（本盘点未删）。

---

## 6. 本会话实测记录（只读验证 + eval 复跑）

| 命令 | 结果 |
|---|---|
| `git log --oneline` / `git status --short` / `git status --short \| wc -l` | HEAD `d6daffd`；33 个修改未提交 |
| `git check-ignore evidence/ .env data/audit.db data/session_map.db` | 全部命中（evidence/ 经修改后 .gitignore 排除；.env/两库文件本被忽略） |
| `git diff .gitignore` | 新增 `evidence/` 忽略行（第 48-49 行） |
| `PYTHONUTF8=1 ./.venv/Scripts/python.exe -m evals.m3_masking` | **9/9 PASS，exit 0**（本会话实跑） |
| `PYTHONUTF8=1 ./.venv/Scripts/python.exe -m evals.m2_recognizers` | **6/6 PASS，exit 0**；structural micro=1.0000（618/618）；2000ch mean 3.21ms（本会话实跑） |
| `PYTHONUTF8=1 ./.venv/Scripts/python.exe -m evals.m4_routing` | **43/43 PASS，exit 0**（本会话实跑） |
| `PYTHONUTF8=1 ./.venv/Scripts/python.exe -m evals.m2_semantic` | **11/11 PASS，exit 0**（injection×34、normal×45；mean 1.36ms）（本会话实跑） |
| `PYTHONUTF8=1 ./.venv/Scripts/python.exe -m evals.m0_infra` | **20/20 PASS，exit 0**（后台实跑，输出 tmp/glm53_m0_out.txt） |
| `PYTHONUTF8=1 ./.venv/Scripts/python.exe -m evals.m7_audit` | **17/17 PASS，exit 0**（后台实跑，输出 tmp/glm53_m7_out.txt） |
| `ls tmp/wf/ \| wc -l` 等 | 115 份运行留档；最新 20:20 `evals.m10_e2e`（并行活动佐证） |

以上 eval 运行仅写 `tmp/`/`data/` 运行态工件与日志，未触碰任何源码/配置/文档（红线遵守）。

### 未验证项（如实标注）
- **未复跑**：t0_gateway、t0_stream、m5_outguard、m6_filesvc、m6_ocr、m8_generator、m9_webui、m10_e2e、m11_robust、t0_labels、m8_quality（共 11 个；均需端口拓扑/较长墙钟或 :9004 真实上游）。其支撑以 `evidence/gate-final-20261002.md` §3/§7.3 的留档日志（tmp/wf/ 可回查）为准。
- **未执行**：docker compose（环境无 Docker，项目自身亦声明未实测）；gpu/gpu-services 脚本与 :9004 服务（无 GPU 机）；`ops/gate_final.py` 整门（小时级墙钟，且明示勿在窄窗口启动）。
- **未读取**：`.env` 内容（红线：真实密钥值不入报告）；`_upstream/` 逐文件；`out/public-export/` 逐文件。

---

## 7. 结论

1. **实装度**：14 组件中 12 个「已实装」、benchmark「部分实装」（m8_baselines 规划态）、gpu/gpu-services 为「已实装的部署侧件（本机未验证运行）」。所有未实装/占位处均在代码或文档中**显式声明**（NER 恒空+debug 日志、NullModerator 自述「接口占位」、docker-compose「未实测」、demo 场景「待补」），未发现静默假实现或「为通过而写」的桩。
2. **声明可信度**：README 的量化声明全部有 eval 阈值+检查项支撑；其中召回 100%/延迟/会话稳定/流式还原/工具还原/注入拦截/审计零明文/路由矩阵 8 项经本会话实跑复现，其余有 10-03 留档日志可回查。README 对不实装项（NER、基线对比、compose）的表述与代码状态一致。
3. **最需要处置的三件事**：① 33 个未提交文件按主题固化（含全部 S2 安全修复）；② 保持 :9004 稳定后重跑 `ops/gate_final.py` 取得 S2 后首个 9/9 整门判定（evidence §7.3 遗留动作）；③ 回填三处文档滞后（CONTRACTS 痛点#1、labels.md 缓冲字长、REGENERATE 路径）。
