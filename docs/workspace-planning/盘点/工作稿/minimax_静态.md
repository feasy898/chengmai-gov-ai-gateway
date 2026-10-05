# 政务 AI 安全网关 · 逐组件静态盘点工作稿（独立盘点组 · MiniMax-M3.1-Flash）

> 盘点人：静态盘点员（minimax 组）。**只读走查**，未修改任何源码/配置/文档。
> 仓库根：`gov-anon-gateway/`（下文相对路径均以此为基准）。
> 盘点时点工作区代码态：`git log -1` = `d6daffd chore: import chenmai-gov-ai-gateway from
> feasy898/agentic-factory-projects@main (2026-10-01 snapshot)`；`git status --short` 实测
> **37 个文件被修改（M）全部未提交**（清单见 §7.1）。即本稿对应「HEAD + 未提交工作区」，
> 非单一可复现快照。
>
> **本文档中所有实测值均为本次亲自执行**，命令与输出一并给出；未跑的一律标「未验证」。

---

## 0. 一句话结论

这是一份**工程完成度相当高、契约与验收纪律异常扎实**的实现：主链（识别→脱敏→路由→输出防护→审计）逐层实装，
规则层结构化号码召回实测 1.0000、2000 字 detect 4.53ms，六道门 + 可执行 eval 体系齐备；
**主要风险不在代码而在三处**：①README/docs 相对代码有多处过时断言（尤其 `docs/assets/specs/` 的行号与形态计数），
②NER 适配器恒空、人名/住址识别实质未落地（README 已如实改口，但 docs/assets 仍留旧口径），
③演示部门 Key 明文以常量形式散落 `evals/`、`ops/`，生产部署前必须换哈希（README.public §6 已声明）。

---

## 1. 走查范围与方法

### 1.1 本次亲自运行并通过的检查（命令 + 原始输出摘录）

全部在 `gov-anon-gateway/` 下、`PYTHONUTF8=1 ./.venv/Scripts/python.exe`（Python 3.12.10）执行：

| 命令 | exit | 关键输出 |
|---|---|---|
| `python -m evals.m0_infra` | 0 | `M0 INFRA: 20/20 checks passed`；末行 `contract:extra-forbid-negative — extra-field rejected on 9 contract + 3 config models` |
| `python -m evals.m2_recognizers` | 0 | `M2 RECOGNIZERS: 6/6`；`structural micro=1.0000 (618/618)`；`FPR=0/22=0.0000`；`2000ch detect ×10 mean 4.53ms (max 11.47ms) < 100ms` |
| `python -m evals.m3_masking` | 0 | `M3 MASKING: 9/9`；`15 known mangle forms restored`；`6 negatives passthrough`；`100000 inserts → 0 final collisions`；`restore mean 0.763ms < 20ms` |
| `python -m evals.m4_routing` | 0 | `M4 ROUTING: 43/43 checks passed` |
| `python -m evals.m2_semantic` | 0 | `M2 SEMANTIC: 11/11 checks passed (injection×34, normal×45)`；三类召回均 1.0000；`normal FP=0/45`；`2000ch mean 0.55ms < 50ms` |
| `python -m evals.m6_filesvc` | 0 | `M6 FILESVC(text-layer+export): 12/12`；`export-pdf 引擎链三实现零残留+回退` |
| `python -m ops.name_lint`（标准档） | 0 | `name_lint: scanned 146 files, 0 violation(s)` |
| `python -m ops.name_lint --strict` | **1** | `scanned 193 files, 19 violation(s)`——命中全在 `config/`（详见 §5.2） |
| `python -m pytest evals/m0_infra` | **4** | `collected 0 items / no tests ran`——README.public §2 的冒烟命令实为**空跑**（详见 §4-⑪） |
| `python -m pytest`（无参数） | **5** | `testpaths = ["tests"]` 但 `tests/` 目录不存在 |

### 1.2 未运行的检查（如实标注「未验证」）

以下均**未在本次执行**，结论只来自代码走查 + `evidence/gate-final-20261002.md` 的留档转述，
不构成本次独立验证：`evals.m5_outguard`（需占 :8901/:8902）、`evals.m7_audit`（占端口 + 写库）、
`evals.m9_webui`、`evals.t0_gateway`、`evals.t0_stream`、`evals.m10_e2e`（e2e 需 9000/8901/8902 + 真实上游）、
`evals.m11_robust`、`evals.m8_generator`（会重写 `data/`）、`evals.m6_ocr`（需 OCR 引擎）、
`evals.t0_labels`、`evals.m8_quality`（需 :9004 真实上游）、`ops/gate_d0..gate_final.py`（整门，小时级）、
`ops/export_public.py`（会写 `out/`）。**U8 真实大模型腿、m8_quality 质量比、docker compose 三项一律未验证。**

### 1.3 关于工作区根的另两项（一句话带过，按任务单要求）

- `_upstream/`：**上游导入源的原始快照**（`agentic-factory-projects-main/` + `repo.tar.gz`），是本仓
  `HEAD d6daffd` 提交信息所指的来源；本稿不逐文件走查它。
- `wf_run.py` / `wf_env.py`：**工作流包装器**（把 `python -m evals.x` 之类命令包成带日志 slug、
  退出码记录的子进程执行器），非本仓业务代码。`evidence/gate-final-20261002.md` 中大量
  `tmp/wf/<unix_ms>_<slug>.log` 引用即由它产生。

---

## 2. 组件清单（14 个）

成熟度口径：**已实装** = 声明能力在代码中有对应实现且有 eval 断言；**部分实装** = 主干实装但存在
规划态子面/占位实现；**占位** = 接口在位、恒空或恒降级。

| # | 组件 | 声明能力（README/docs 原话要点） | 实际实现（关键入口 文件:行号） | 对外接口 / 依赖 | 成熟度 |
|---|---|---|---|---|---|
| 1 | `common/` | 「配置加载、结构化日志等跨模块基础设施」（README.md:20）；C7 契约「字段即契约、密钥不入配置」（CONTRACTS.md:134-142） | `common/config.py:52-83` `AppConfig`（`extra="forbid"`）；`:91` `_SECRET_ENV_FIELDS={admin_key_env, mask_key_env}` 覆盖豁免；`:94-105` `_override_from_env`；`:108-116` `load_app_config`；`:119-132` `load_dept_keys`（只存 sha256）；`:135-145` `resolve_secret`；`:148-166` `load_env_file`；`common/logs.py:34-54` `JsonFormatter`；`common/timeutil.py`（UTC ISO8601） | 被全模块 import；`evals.m0_infra` 20/20 覆盖 | **已实装** |
| 2 | `gateway/` | 「OpenAI 兼容网关与流式还原」（README.md:21）；主链 8 步序（specs/gateway-main-chain.md:9-14）；出站全量检测面（`pipeline.py` 模块 docstring:19-23） | `gateway/pipeline.py:332` `handle_chat`（非流式）、`:414` `handle_chat_stream`、`:573` `_prepare`（detect+mask+route）、`:195-239` `_aux_texts`（出站辅助面）、`:172-192` `_iter_string_leaves(include_keys=True)`、`:242-257` `_apply_aux_masked`、`:315-329` `_bind_session`（会话属主）、`:791-815` `_safe_response_preview`、`gateway/app.py:202` `create_app`（端点全表 app.py:271-537）、`gateway/sse.py:61` `iter_sse_data_lines` / `:149` `compose_chat_stream`、`gateway/provider.py:33` `forward_chat`、`gateway/deps.py:30-38` `authenticate`（`hmac.compare_digest` 常量时间）、`gateway/admin_api.py:135` `mount`、`gateway/mock_upstream.py` 回显 mock | FastAPI app；`/v1/chat/completions`、`/v1/models`、`/v1/files/*`、`/admin/api/*`、`/internal/*`、`/healthz`、`/webui*` | **已实装** |
| 3 | `recognizers/` | 「三层识别引擎」（README.md:22）；README.md:7「规则 + 校验位 + 语义词表已实装…NER 为适配器预留位」 | `recognizers/rule/detect.py:433-561` `detect`（11 步全序）；`:402-427` `_scan_tokens`；`:365-399` `_classify_token`（熵串>证件>卡号>电话）；`recognizers/pipeline.py:18-29` `detect_full`（规则+语义合并）；`recognizers/models.py:19-48` `EntityClass` 19 值、`:52-55` 9 子类型；`recognizers/rule/whitelist.py` 四类白名单 | 被 gateway / filechannel / routing 消费 | **部分实装**：规则层+语义层已实装；**NER 适配器 `ner/adapter.py:29-31` `detect` 恒返回 `[]`（占位）** |
| 4 | `masking/` | 「可逆脱敏」（README.md:23）；「会话稳定可逆脱敏：占位符按密钥哈希固定…号码归一化；流式缓冲还原；工具调用参数还原」（README.md:8） | `masking/mapper.py:222-224` HMAC 摘要、`:226-256` `placeholder_for`（`(8,10,12)` 升位）、`:110-135` `canonical_placeholder`（容错改形四步）、`:138-174` `restore_tolerant`、`:177-200` `tolerant_placeholder_hits`、`:312-386` `SessionRegistry`（LRU + `_owners` 有界）；`masking/normalize.py:52-84` `normalize_value`；`masking/remap.py:50-119` `StreamRestorer`（≤48 字符有界缓冲）；`masking/toolbuf.py:99-123` `feed`（hold-to-finish）、`:130-145` `finalize`、`:64-75` `restore_arguments`；`masking/session_store.py:91-248` `SessionStore`（SQLite `masking_map`+`session_owner`、TTL） | `evals.m3_masking` 9/9 覆盖 | **已实装** |
| 5 | `routing/` | 「敏感度路由策略」（README.md:24）；R1–R6 矩阵「BLOCK > GOVCLOUD > INTERNET」（specs/routing-matrix.md:9-18） | `routing/engine.py:69-144` `decide`（纯函数）；`:36-50` 四个类别集合常量；`:61-66` `_bucket_block`（白名单不豁免拦截）；`routing/models.py:20-32` `RouteReason` code 词表、`:47-49` BLOCK 恒 null 校验 | 被 `gateway/pipeline.py:644` 调用 | **已实装**（43/43） |
| 6 | `outguard/` | 「输出侧防护（AI 标识、拦截文案、代答）」（README.md:25）；AI 标识三面（specs/outguard.md:8-13） | `outguard/label.py:38-51` `apply_message_label`（尾注+annotations+幂等）；`outguard/fallback.py:62-115`（YAML 文案库 + 关键词代答）；`outguard/service.py:24-71` 门面（`:36-37` 按后端签名决定是否传 `redact`）；`outguard/moderation.py:48-55` `NullModerator` **恒 safe**、`:58-75` `verdict_of` | `gateway/pipeline.py:400/539` 调用 | **部分实装**：AI 标识/文案/代答已实装；**输出复检后端为 P0 空实现（`NullModerator`），`config.app.yaml:27 moderation_model: ""`** |
| 7 | `filechannel/` | 「文档解析与彻底删除导出」（README.md:26）；「Word/Excel/PDF/扫描件公开前体检，一键导出彻底删除版」（README.md:10） | `filechannel/inspect.py:82-116` `inspect_bytes`（FileReport）、`:64-79` `risk_level_of`（HIGH/MID/LOW/NONE）；`filechannel/parsers.py`（docx 四位面 / xlsx 隐藏行列+公式缓存+批注 / pdf charbox）；`filechannel/ocr.py:158-202` OCR 路线（引擎名经 config importlib）；`filechannel/sanitize.py`（docx 删 run / xlsx 删值+整列删 / pdf 引擎链）；`filechannel/pdf_engine.py:500-520` `load_engine_chain`（涂删→内容流→栅格三引擎自动回退）；`filechannel/service.py:97-119` `export_bytes` | `/v1/files/inspect`、`/v1/files/export`（**无鉴权**，见 §5.4） | **已实装**（`m6_filesvc` 12/12；OCR 面 `m6_ocr` **未验证**） |
| 8 | `audit/` | 「审计日志与看板」（README.md:27）；「日志只存脱敏内容，全程可审计」（README.md:3） | `audit/store.py:57-83` `assert_no_raw_pii`（归一化值+表面形式同查 + 截断边界守护）、`:86-111` `safe_preview`、`:114-141` `assert_db_no_raw_pii`（含 `-wal`/`-shm`/死信文件）、`audit/writer.py:39-58` `audit_events` schema、后台队列批量写、`audit/query.py` 分页/聚合/CSV（`evals/m7_audit` **未验证**）、`audit/models.py:22-45` `AuditEvent`（**无 raw 字段**） | `gateway/pipeline.py:909-924` `_audit` | **已实装** |
| 9 | `benchmark/` | 「合成测评集与基线对比」（README.md:28）；「结构化号码召回 ≥99.5%，实测 100%；CPU 2000 字 <100ms」（README.md:13） | `benchmark/generator/build.py:31` `build_all`；`cases.py`/`fixtures.py`/`numbers.py`（自研 GB11643/GB32174/Luhn 校验位生成）/`templates.py`（14 类政务文书）/`geo.py`（澄迈 469023）；`config/synthetic_corpus.yaml` 经 importlib 加载语料库 | `python -m benchmark.generator`；产出 `data/`（gitignored） | **已实装（生成器）**；**`m8_baselines` 基线对比为规划态、文件不存在**（CONTRACTS.md:149 如实登记） |
| 10 | `webui/` | 「演示前端页面」（README.md:29） | `webui/pages.py:152` `mount`：`/webui`、`/webui/files`、`/webui/demo`、`/webui/chat`、`/webui/dashboard`、`/webui/demo/materials/{f}[/text]`；`webui/pages.py:191-208` 看板**回环闸**（`_LOCAL_CLIENT_HOSTS={127.0.0.1,::1}`，非回环 403）；`webui/dashboard.py`（纯函数聚合 + 手写 SVG，`html.escape` 防注入）；`webui/demo_api.py:69-101` `/admin/api/demo/*`（admin key 硬闸 `:52-62`）；`webui/templates/*.html` 五页 | **无鉴权**（`/webui/*`），`evals.m9_webui` **未验证** | **已实装** |
| 11 | `ops/` | 「运维工具：名称守卫、克隆脚本、e2e 冒烟、公开导出」（README.md:30） | `ops/name_lint.py:44-50` 后缀与排除目录；`ops/e2e_smoke.py:1-70` 八用例 U1–U8；`ops/gate_d0.py` + `gate_b1..b6.py` + `gate_final.py`（九项）；`ops/export_public.py:73` `DEPLOYER_PLACEHOLDER="_BY_DEPLOYER_"`、`:315` 导出树 strict lint；`ops/seed_demo.py`；`ops/tunnel_gpu.sh` | 系统 python 任意 cwd 可跑（纯标准库） | **已实装**（**本次只跑通 name_lint；整门未跑**） |
| 12 | `evals/` | 「可执行验收入口（`python -m evals.*`，exit 0 = 通过）」（README.md:31） | 19 个 eval 模块 + `evals/thresholds.py`（阈值单一来源，98 行） | 命令行 | **已实装**（本次实跑 6 个全绿） |
| 13 | `gpu/` | 不在 README 组件表内；`docs/assets/manifest.md` 未列 | 仅 2 个 shell 脚本：`gpu/setup_llm_service.sh`（权重下载，`LLM_HF_REPO` **必须经环境变量提供、不入仓库**）、`gpu/llm_keepalive.sh`（GPU 机侧保活循环） | GPU 机侧运维 | **辅助脚本（非 Python 组件）**，无 Python 入口 |
| 14 | `gpu-services/` | 同上，不在 README 组件表内 | `gpu-services/llm_openai/service.py`（732 行 FastAPI，OpenAI 兼容子集，`:1-40` 模块 docstring 写明接口口径）、`run_gpu.sh`；模型真实名不入仓库（经 `LLM_HF_REPO`/`LLM_MODEL_DIR` 注入） | 部署到 GPU 机 :9004；本机经 `ops/tunnel_gpu.sh` 访问 | **已实装**（本机侧 `/health` 联通性 **未验证**） |

---

## 3. 逐条核对 README 的量化与能力声明

标注三档：**有测试支撑**（本次实跑或代码+eval 双证）、**部分支撑**、**仅声明**。

| # | 声明（README 出处） | 实现证据 | 测试支撑 | 判定 |
|---|---|---|---|---|
| ① | 「结构化证件/号码校验位（身份证/统一社会信用代码/银行卡/车牌/密级标识…，**召回实测 100%**）」（README.md:7） | `recognizers/rule/detect.py:365-399` 独立实现 GB11643/GB32174/Luhn 三校验位 | **本次实跑**：`structural micro=1.0000 (618/618)`，12 个类别逐类 recall 全 1.0000 | **有测试支撑** |
| ② | 「**CPU 2000 字 <100ms**」（README.md:13） | 阈值 `evals/thresholds.py:15 RULE_LATENCY_MS_2000CH=100`；`evals/m2_recognizers.py:260-274` 取 2000 字 ×10 均值 | **本次实跑**：`mean 4.53ms (max 11.47ms) < 100ms` | **有测试支撑** |
| ③ | 「会话稳定可逆脱敏：占位符按密钥哈希固定，多轮不变号」（README.md:8） | `masking/mapper.py:222-224` HMAC-SHA256(key=MASK_KEY, msg=`session_id\x1f type\x1f normalized`) | **本次实跑**：`mask:stability-1000 — 1000 values × repeat/replay identical; 3 cross-sessions all differ` | **有测试支撑** |
| ④ | 「号码归一化」（README.md:8） | `masking/normalize.py:52-84` | **本次实跑**：`normalization-equivalence — 6 classes / 18 variants → one placeholder each` | **有测试支撑** |
| ⑤ | 「**流式缓冲还原**」（README.md:8） | `masking/remap.py:70-110` `feed`（≤48 字符有界 `_pending`） | **本次实跑**：`remap:stream-fuzz-500 — 500 chunked cases (1–7 chars) == whole-restore; buffer stayed ≤48` | **有测试支撑** |
| ⑥ | 「**工具调用参数还原**」（README.md:8） | `masking/toolbuf.py:99-145` hold-to-finish + `restore_arguments:64-75`；`gateway/pipeline.py:828-853` 非流式整体还原 | **本次实跑**：`tool:hold-to-finish-core`、`tool:cross-chunk-sweep-fuzz-multi`、`tool:overflow-valve-nonstream` 三项全过 | **有测试支撑** |
| ⑦ | 「敏感度路由：普通脱敏走互联网模型，敏感个人信息/工作秘密切政务云，**命中密级标识直接拦截**」（README.md:9） | `routing/engine.py:93-137` R1/R3/R4 分支；`routing/models.py` BLOCK 恒 null | **本次实跑**：`M4 ROUTING: 43/43`（R1 密级词单命中→BLOCK 等 38 矩阵格） | **有测试支撑** |
| ⑧ | 「**AI 生成标识**（显式 + 隐式元数据）」（README.md:11） | `outguard/label.py:38-51` 尾注 + annotations；`gateway/pipeline.py:407-409` 响应头 `x-anongw-ai-label:1`；`gateway/sse.py:227-231/275-276` 流式尾注 delta + finish annotations | `evals.m5_outguard` 4 项 e2e 标识断言存在（`evals/m5_outguard.py:474-477`）；**本次未跑** | **部分支撑**（eval 存在，未独立验证） |
| ⑨ | 「内容风控与代答拒答」（README.md:3、11） | `outguard/moderation.py:48-55` **`NullModerator` 恒 safe（占位）**；`outguard/fallback.py:93-115` 代答/拒答已实装 | `evals/m5_outguard.py:480` `e2e:moderation-hook` 用注入的假后端断言 flagged→403；**本次未跑** | **部分支撑**：代答/拒答=实装；**「内容风控」=P0 空后端占位**，真实审核模型未接（`config/app.yaml:27 moderation_model: ""`） |
| ⑩ | 「**彻底删除导出**」（README.md:10） | `filechannel/sanitize.py` 三条删除式重写 + re-ingest 零残留**管线内硬闸**（非仅验收断言）；`filechannel/pdf_engine.py:500-520` 三引擎自动回退 | **本次实跑**：`export-docx 四位面删值+白名单保留+零残留`、`export-xlsx 隐藏列整列删+零隐藏维度+零残留`、`export-pdf 引擎链三实现零残留+回退` | **有测试支撑** |
| ⑪ | 「NER（人名/住址模型化识别）为**适配器预留位**，属后续规划」（README.md:7） | `recognizers/ner/adapter.py:29-31` `detect` 恒 `return []`；`:23-27` 有 model_path 只记不加载 | `evals/m2_recognizers.py:145-147` 把 `rule_detectable=false` 的人名/住址**排除出规则层召回分母**（本次输出 `NER-layer sample=714`） | **有测试支撑**（口径为「预留位」——声明与实现一致）；但**须注意**：`docs/assets/specs/benchmark-generator.md:49-51` 仍把 NER F1 列为待落地验收门 |
| ⑫ | 「审计看板：按部门统计拦截，导出保密自查报告」（README.md:12） | `gateway/admin_api.py:135-208`；`webui/dashboard.py` | `evals.m7_audit.py:831-848` 5 项 admin 断言（`admin:audit-page-filters`/`pagination`/`metrics-aggregation`/`report-csv`/`admin-api-auth-negatives`）；**本次未跑** | **部分支撑**（eval 存在，未独立验证） |
| ⑬ | 「多基线对比与人名/住址 NER 的 F1 验收门为**规划项**」（README.md:13） | `evals/` 下**无 `m8_baselines.py`**（实测 `ls evals/ \| grep -i baseline` 为空）；`evals/thresholds.py` 无 F1 阈值 | 无（规划态） | **有测试支撑**（声明为规划项，与实现一致） |
| ⑭ | 「`/v1/chat/completions` 与 `/internal/*` 均需部门 Key」（README.md:38、README.public:112） | `gateway/app.py:369-373`（chat）、`:441-444/:459-463/:500-504`（internal 三端点） | `evals/t0_gateway.py:531 auth:401-and-dept-key`；**本次未跑** | **部分支撑** |
| ⑮ | 「`python -m evals.*`，exit 0 = 通过」（README.md:31） | 19 个 eval 模块 | **本次实跑 6 个全 exit 0** | **有测试支撑** |

### 3.1 声明侧的两个「诚实加分项」

- `docs/contracts/labels.md:36-44` **主动声明**「GB/T 45574-2025 标准全文未逐字核对」，并把每条内容标注
  「已核实（摘要）/推断/项目自定义」；`evals/t0_labels.py:167` 有 `labels:uncertainty-marked` 断言把这条
  纪律本身钉进 eval。这是少见的「把不确定性写进验收」的做法。
- `README.public.md:82-89` 对 docker compose 明写「**⚠ 未实测声明**」，`docker-compose.yml:3-5` 同样标注。
  **本次同样未实测，不冲突。**

---

## 4. 占位与未实装部分

1. **NER 适配器恒空**（`recognizers/ner/adapter.py:29-31`）。人名仅靠规则层双轨兜底：
   4 个演示名词表（`config/person_names.txt` 实测非注释行 **4 行**）+ 前 100 姓启发式
   （`recognizers/rule/detect.py:89-91`，confidence=0.5）+ 静态停用词表（`:95-102`）。
   **住址（ADDRESS）规则层完全不产出**（实测 `grep "EntityClass.ADDRESS" recognizers/rule/detect.py` 零命中），
   仅作为枚举值与路由名单存在。README.md:7 已如实改口，**但 `docs/assets/specs/benchmark-generator.md:49-51`
   与 `docs/assets/manifest.md:24` 仍沿用「人名/住址（NER 层计分）」的旧口径**。
2. **`outguard/moderation.py:48-55` `NullModerator` 恒 safe**——README.md:3 的「内容风控」目前是接口位，
   真实语义审核模型未接（`config/app.yaml:27 moderation_model: ""`，留空即不加载任何模型）。
3. **`evals/m8_baselines.py` 不存在**（实测目录列举）——三基线对比为规划态，
   `CONTRACTS.md:149`、`specs/benchmark-generator.md:52-55` 已如实登记。
4. **`preserve_semantic` 字段无消费方**（实测全仓 grep：仅出现在模型定义 `masking/models.py:28`、
   SQLite 列 `masking/session_store.py:46/62/66/87/183` 与 eval 断言，**无任何读取该标志改变替换行为的代码**）。
   `CONTRACTS.md:150` 已自认「字段形同虚设」。
5. **`Whitelist.public_title_before()` 为休眠路径**（`recognizers/rule/whitelist.py:1-17` 模块 docstring
   自陈「规则层不产出 PERSON，本钩子在 NER 接入前为休眠路径」）。
6. **`masking.normalize` 对 PERSON/ADDRESS 不做串级归一化**（`masking/normalize.py:11`、`:84` 仅半角化+strip），
   与 §5.3.2 保守口径一致，但意味着开放域人名/住址一旦接入 NER，归一化等价面需重新设计。
7. **`_BY_DEPLOYER_` 占位**：公开导出后 `config/app.yaml:31 pdf_engine_module`、OCR 引擎、合成语料库
   坐标被替换为占位符（实测 `out/public-export/config/app.yaml:32 pdf_engine_module: _BY_DEPLOYER_`），
   **未配置前 PDF 导出/OCR/夹具生成显式失败**。README.public.md:100-106 已如实声明。
8. **整体代码态未固化**：37 个文件 M 未提交（含 `gateway/pipeline.py`、`masking/mapper.py`、
   `gpu-services/llm_openai/*` 等安全关键面），存在与 `evidence/gate-final-20261002.md:38-70` 留档清单漂移。

---

## 5. 文档与代码不一致 / 隐患

### 5.1 文档过时（`docs/assets/` 相对当前代码）

| # | 位置 | 文档写的 | 实际 | 影响 |
|---|---|---|---|---|
| D1 | `specs/masking-placeholder.md:131`、`:249` | 「冻结 **11 形态 + 4 负例**」 | `evals/m3_masking.py:255-273` 实际 **15 形态**（多出 `prefix-merged`/`prefix-ascii-colon`/`prefix-multi-segment`/`prefix-combo-noise` 四种「前缀文案并入括号内」形态）+ 6 负例；**本次实跑输出即 `15 known mangle forms ... 6 negatives`** | 文档描述的形态目录缺 U8 实锤新增的 4 种；`manifest.md:25` 同样写「改形 11 形态」 |
| D2 | `specs/masking-placeholder.md:91-99` | `canonical_placeholder`「规范化**三步**，顺序固定」 | `masking/mapper.py:110-135` 实际**四步**（多出第 ④ 步 `_strip_prefix_segments` 前缀段剥离，`:97-107`） | 复刻者按三步实现会漏 U8 前缀并入形态 |
| D3 | `specs/masking-placeholder.md:86` 冻结常量表 | 列 4 个常量 | 缺 `PLACEHOLDER_PREFIX_COLONS`（`mapper.py:74`）、`KNOWN_LABELS`（`:94`）两个 U8 新增常量 | 同上 |
| D4 | `specs/gateway-main-chain.md:22/26/32/34/44` | 行号 `pipeline.py:144-158 / 131-141 / 161-191 / 194-202` | 实测 `_iter_string_leaves` 在 **172**、`_content_segments` 在 **157**、`_aux_texts` 在 **195**、`_apply_aux_masked` 在 **242** | 全部偏移约 28–48 行，按行号导航会落空 |
| D5 | `CONTRACTS.md:148` 痛点 #1 | 「`_iter_string_leaves` 只递归 dict 的 **values**，字符串键不进检测面 → PII 藏 JSON 键位时漏检漏替换」 | **该痛点已被修复**：`pipeline.py:172-192` 已有 `include_keys` 形参，`:220/:231/:238` 三处调用均传 `include_keys=True`；`evals/t0_gateway.py:540 outbound:full-detection-face` 有对应断言 | 契约痛点表未回填「已销项」，读者会误判仍有泄漏面 |
| D6 | `CONTRACTS.md:148` 的行号 `pipeline.py:144-158` | — | 同 D4，指向已漂移的位置 | — |
| D7 | `specs/gateway-main-chain.md:34-42` §2.2 | 辅助面只列 3 类覆盖（tools / 历史 tool_calls / 非 text 多模态段） | 代码已扩到**顶层其余全部字段 + dict 键 + 消息级非 content 字段**（`pipeline.py:195-239` docstring + 实现） | 出站检测面描述不完整，安全评审会低估覆盖面 |
| D8 | `manifest.md:8` | 「t0_gateway 13/13、t0_stream 11/11、m9_webui 14/14、m7_audit 16/16、m8_generator 4/4」 | `evals/t0_gateway.py:528-544` **15 项**；`evals/t0_stream.py:810-825` **14 项**；`evals/m7_audit.py:831-848` **17 项** | 冻结于 2026-09-29 基线，与后续 S2 修复后的项数不符 |
| D9 | `manifest.md:32` `GATES` 行 | 「标准库 Python 门脚本 **×6**（gate_d0 + gate_b1..b5）」 | 实际存在 **7 个门 + 1 个终检门**：`gate_d0/b1/b2/b3/b4/b5/b6` + `gate_final`（实测目录列举；`gate_final.py:64-77` 明确含 ⑦ gate_b6） | 门清单不全 |
| D10 | `specs/gates.md:19-26` §2 门项表 | 只列 G0 + G-B1…G-B5 | 同 D9，无 G-B6 行 | 门策略表落后一门 |
| D11 | `specs/gates.md:55`、`REGENERATE.md:17/61-63` | 整门命令写死 `python D:/workspace/澄迈8项目/政务AI脱敏网关/repo/ops/gate_b5.py` | 仓库已迁至 `D:/new-workspace/澄迈项目/政务AI安全/gov-anon-gateway/` | 按文档复制粘贴的路径不存在 |
| D12 | `docs/assets/feedback.md:14-16` | 引 `README.md:7` 「三层识别…NER（人名/住址/敏感身份）」与 `README.md:13` 「F1 ≥95%」 | README 已改口（现行 README.md:7 明确「NER 为适配器预留位」、:13 已删 F1） | feedback 台账引的是旧 README 行，读者会以为 README 仍在承诺 F1 |
| D13 | `evidence/gate-final-20261002.md:38-70` | 「28 个文件被修改」 | `git status --short` 实测 **37 个 M** | 留档为时点快照（非错误），但已明显漂移，§6⑤ 自己也提示了漂移问题 |

### 5.2 配置与密钥处理

- **✅ 做对的**：`config/app.yaml` 只存环境变量**名**（`mask_key_env`/`api_key_env`），运行时
  `resolve_secret` 解析（`common/config.py:135-145`）；`config/dept_keys.yaml` **只存 sha256**
  （实测三个 64 位小写十六进制）；`.env` 已被 `.gitignore:17` 忽略（实测 `git check-ignore -v .env` 命中
  `.gitignore:17`，`git ls-files | grep '^\.env$'` 为空）；`common/config.py:91` 把
  `admin_key_env`/`mask_key_env` 移出 `ANONGW_<K>` 覆盖命名空间（防 fail-open 改指），
  `evals/m0_infra.py:187-212` 有负例断言（本次实跑 PASS）。
- **⚠ 隐患 1：`--strict` 档当前 19 处命中**（本次实跑 `exit 1`）。全部集中在 `config/`：
  `config/app.yaml:31 pymupdf`、`config/filechannel.yaml:5/10/12/19/20`（pypdfium2/pikepdf/rapidocr）、
  `config/install_check.json:13-16/21`、`config/synthetic_corpus.yaml:5/6/9`（faker/fitz）。
  这**符合**设计（`ops/name_lint.py:33-35` 注释：配置文件默认不扫，库名只许在 `config/`；严格档只用于
  **导出树**终检，`ops/export_public.py:315` 对导出树跑 strict）。但任何开发者在本仓直接跑
  `python -m ops.name_lint --strict` 都会拿到 19 命中 exit 1，**与 `CONTRACTS.md:161`
  「`python -m ops.name_lint --strict` 零命中」的措辞存在字面冲突**。
- **⚠ 隐患 2：演示部门 Key 明文以常量形式散落源码**。实测 12 处 `dk_` 明文常量：
  `evals/m10_e2e.py:54`、`evals/m11_robust.py:100`、`evals/m5_outguard.py:71`、`evals/m7_audit.py:492/613`、
  `evals/m8_quality.py:79`、`evals/m9_webui.py:499/534`、`evals/t0_gateway.py:64/65/178`、
  `evals/t0_stream.py:84`、`evals/u8_repro.py:197`、`ops/e2e_smoke.py:135`。
  这些明文的 sha256 **就在 `config/dept_keys.yaml:4-6`**，即**任何人拿到本仓即可通过鉴权**。
  README.public.md:122-129 已如实声明并要求「生产部署必须更换哈希」——属**已知且已披露**的演示凭据，
  但若交付对象未逐字读 §6，这是实打实的横向访问面。
- **⚠ 隐患 3：`.env.example:20-22` 的注释里含演示 key 形态说明**，`.env` 实存 8 个变量
  （MASK_KEY / MOCK_KEY / UPSTREAM_BIGMODEL_KEY / REAL_LLM_KEY / GOVCLOUD_LLM_KEY /
  SEMANTIC_JUDGE_BASE_URL / SEMANTIC_JUDGE_KEY / SEMANTIC_JUDGE_MODEL，**值本次一律未读取、未记录**）。
  其中 **`UPSTREAM_BIGMODEL_KEY` 是孤儿变量**：实测全仓 grep 该变量名在 `.py/.yaml/.json` 中**零命中**，
  `config/app.yaml` 的 `api_key_env` 只有 `MOCK_KEY`/`REAL_LLM_KEY`/`GOVCLOUD_LLM_KEY` 三个。
  无害，但属配置面噪声。
- **✅ `.env` 不入库**：`git ls-files` 实测 161 个跟踪文件中无 `.env`；`data/`、`tmp/`、`out/`、
  `evidence/` 均被 `.gitignore` 覆盖（实测 `git check-ignore` 四项全部命中）。

### 5.3 脆弱点（代码面）

| # | 位置 | 脆弱点 | 现有防线 |
|---|---|---|---|
| F1 | `gateway/pipeline.py:336-341`、`:418-420` | 「先校验后绑定」是**后加的加固**：`_validate_body` 失败前若已 `_bind_session`，垃圾请求可按先到先得抢占任意 `session_id` | 已修（先校验后绑定）+ `masking/mapper.py:363-364` `_owners` 按 2×LRU 容量裁剪；`evals/t0_gateway.py:541 session:owner-binding` 断言 |
| F2 | `gateway/pipeline.py:792-802` | 审计 `response_preview` 对**真实大模型自由文本**做规则层再脱敏；docstring 自陈「人名等 NER 层实体规则层不可见，属 open-vocabulary 残余，由 U8 的命中宿主裁定兜底」 | 已接 `_safe_response_preview`；残余靠 e2e U8 裁定（本次未跑） |
| F3 | `masking/toolbuf.py:47` | hold-to-finish 是流式路径**唯一无上界缓冲点**，上限 1,000,000 字符 | 绊线式抛 `ToolArgumentsOverflowError`（非静默截断）；`gateway/pipeline.py:505-515` 以 SSE 错误事件收尾 |
| F4 | `gateway/sse.py:79/93-108` | 上游畸形 SSE「无换行的超长行」会撑内存 | `GATEWAY_SSE_LINE_MAX_BYTES=8MB` 超限丢弃 + WARNING（`evals/t0_stream.py:823` 有断言） |
| F5 | `masking/mapper.py:363-364` | `_owners` dict 的裁剪是 O(n) 的 `next(iter(...))` + `pop`；且它与 LRU 是**两套**淘汰口径 | 有界（2×capacity）；`evidence` §7.1 第 7 条记录了独立探针验证 |
| F6 | `gateway/app.py:385-388` | 客户端可自带 `x-anongw-session-id`，直作存储键 | 形态闸 `SESSION_ID_RE`（`app.py:104`）限 `[A-Za-z0-9._-]{1,128}`；但**仍允许任意持证部门预占**（F1 同源，靠先到先得语义） |
| F7 | `docker-compose.yml:39/53` | mock 上游以 `--host 0.0.0.0` 起、端口 `"8901:8901"` 对外发布（**无 127.0.0.1 前缀**），而网关是 `"127.0.0.1:9000:9000"` | mock 只回显收到的 prompt，不含真实数据；compose 整体标注**未实测**（`:3-5`） |
| F8 | 验收基础设施 | `evals/m5_outguard.py` / `m7_audit.py` 等需独占 9000/8901/8902；`REGENERATE.md:90-95` 自陈「并行跑门会端口冲突」 | 已知项，写在 REGENERATE 坑清单第 3 条 |

### 5.4 鉴权面的不一致（需在交付前澄清）

`specs/gateway-main-chain.md:72-73` 如实标注 `/v1/files/inspect` 与 `/v1/files/export` **无鉴权**
（`gateway/app.py:285-364` 确认：只有体积/种类闸，无 `authenticate`），
`filechannel/service.py:20-22` 给了理由（「报告 raw 是上传者自带文件内容回显，不构成服务端持有信息的泄露」）。
但**README.md:38-41 与 README.public.md:112-114 的安全注记只提 `/v1/chat/completions` 与 `/internal/*`，
未提 `/v1/files/*` 与 `/webui/*` 同样无鉴权**。而 `/v1/files/export` 会**返回处理后的文件字节流**、
`/webui/dashboard` 会**渲染审计元数据**（后者有回环闸，`webui/pages.py:202`）。
这是一个**文档层面的安全面缺口**，代码行为本身有 spec 支撑。

---

## 6. 明显脆弱点小结（给交付决策用）

1. **代码态未固化是当前最大的工程风险**：37 个未提交修改覆盖了全部安全关键面
   （`gateway/pipeline.py` 出站检测面、`masking/mapper.py` 容错还原、`common/config.py` 覆盖豁免、
   `outguard/moderation.py` redact 承接、`gpu-services/llm_openai/*`）。任何「按 git 复现」的动作
   拿到的都是 HEAD `d6daffd` 的**旧且不安全**的代码。
2. **`docs/assets/` 已落后于代码一轮以上**（D1–D13 共 13 处），且这些文档在项目内被定位为
   「**spec+eval 驱动开发**」的唯一权威（README.md:43）。按现文档复刻会得到行为不同的系统。
3. **两处「诚实但未兑现」的能力**：NER（人名/住址）与输出侧内容风控，都是接口位。
   README 已改口，但验收层面没有对应的门（F1/F1 阈值、`m8_baselines` 都不存在）。
4. **演示凭据的处置依赖部署方读文档**：`config/dept_keys.yaml` 的 sha256 对应的明文就在同仓 `evals/` 里。
   建议在部署清单里把「更换 dept_keys.yaml 哈希」列为**阻断项**而非建议项。

---

## 7. 附录

### 7.1 `git status --short` 实测（37 个 M，无未跟踪新目录）

```
 M .gitignore              M evals/m9_webui.py          M masking/session_store.py
 M README.public.md        M evals/t0_gateway.py        M ops/e2e_smoke.py
 M audit/store.py          M evals/t0_stream.py         M ops/export_public.py
 M audit/writer.py         M gateway/__main__.py        M ops/name_lint.py
 M common/config.py        M gateway/admin_api.py       M outguard/moderation.py
 M docker-compose.yml      M gateway/app.py             M outguard/service.py
 M evals/m0_infra.py       M gateway/mock_upstream.py   M recognizers/pipeline.py
 M evals/m3_masking.py     M gateway/pipeline.py        M recognizers/semantic/adapter.py
 M evals/m7_audit.py       M gateway/sse.py             M webui/demo_api.py
 M evals/m8_quality.py     M gpu-services/llm_openai/run_gpu.sh  M webui/pages.py
                           M gpu-services/llm_openai/service.py  M webui/templates/chat.html
                                                            M webui/templates/dashboard.html
```
（`evidence/` 目录亦为未跟踪，与留档一致。）

### 7.2 词表规模实测

| 文件 | 总行 | 非注释内容行 |
|---|---|---|
| `config/person_names.txt` | 8 | **4**（张三/李四/王五/赵六） |
| `config/sensitive_terms.txt` | 32 | 覆盖 9 子类型（`m2_recognizers` 实测 `sensitive terms=16 (9 subtypes)`） |
| `config/work_secret_terms.txt` | 7 | 少量 |
| `config/classification_terms.txt` | 9 | 6 词（与 `detect.py:54-56` 兜底一致） |
| `config/injection_terms.txt` | 49 | **22 条正则**（`m2_semantic` 实测 `patterns=22`） |

### 7.3 本次未验证清单（供后续补测）

`m5_outguard`、`m7_audit`、`m9_webui`、`t0_gateway`、`t0_stream`、`t0_labels`、`t0_mock_upstream`、
`m6_ocr`、`m8_generator`、`m8_quality`、`m10_e2e`（含 U8 真实腿）、`m11_robust`、`u8_repro`、
`ops/gate_d0..b6`、`ops/gate_final`、`ops/export_public`、`docker compose up`、`:9004` GPU 隧道连通性。

---

*本工作稿由静态盘点员独立产出；所有实测命令与输出如 §1.1 所载，未通过的一律如实标注
（「未验证」/ exit≠0），未为任何「通过」而修改源码、配置或文档。*
