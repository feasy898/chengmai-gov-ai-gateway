# 静态盘点工作稿：政务 AI 安全网关（Step Router V1 独立组）

> 工作根：`D:/new-workspace/澄迈项目/政务AI安全`
> 主仓：`gov-anon-gateway/`
> HEAD：`d6daffdf5716503089987f14dd2e9e205012952f`
> 工作树状态：28 个已修改文件 + 1 个未跟踪目录 `evidence/`（全部未提交）
> 盘点时间：2026-10-04
> 红线：本稿仅读源码/文档/测试证据，未修改任何源码、配置、文档；未读取其他组工作稿。

---

## 一、文件覆盖清单

| 类别 | 文件 | 用途 |
|---|---|---|
| 顶层说明 | `README.md`, `README.public.md`, `pyproject.toml`, `constraints.txt`, `.env.example` | 声明、依赖、部署 |
| 配置 | `config/app.yaml`, `config/dept_keys.yaml`, `config/filechannel.yaml`, `config/outguard_texts.yaml`, `config/whitelist.yaml`, `config/install_check.json`, `config/synthetic_corpus.yaml` | 运行配置 |
| 契约 | `docs/contracts/labels.md`, `docs/assets/CONTRACTS.md`, `docs/assets/specs/*.md` | 跨模块冻结契约 |
| 验收证据 | `evidence/gate-final-20261002.md` | 终检历史与当前状态 |
| common | `common/config.py`, `common/logs.py`, `common/timeutil.py` | 配置加载、日志、时间 |
| gateway | `gateway/app.py`, `gateway/pipeline.py`, `gateway/sse.py`, `gateway/provider.py`, `gateway/admin_api.py`, `gateway/deps.py`, `gateway/models.py`, `gateway/mock_upstream.py` | 网关主链路 |
| recognizers | `recognizers/models.py`, `recognizers/pipeline.py`, `recognizers/ner/adapter.py`, `recognizers/semantic/adapter.py` | 识别三层 |
| masking | `masking/mapper.py`, `masking/session_store.py`, `masking/toolbuf.py`, `masking/remap.py`, `masking/models.py`, `masking/normalize.py` | 脱敏/还原 |
| routing | `routing/engine.py`, `routing/models.py` | 路由矩阵 |
| outguard | `outguard/service.py`, `outguard/label.py`, `outguard/fallback.py`, `outguard/moderation.py`, `outguard/models.py` | 输出防护 |
| filechannel | `filechannel/inspect.py`, `filechannel/sanitize.py`, `filechannel/service.py`, `filechannel/models.py`, `filechannel/parsers.py`, `filechannel/pdf_engine.py`, `filechannel/ocr.py`, `filechannel/errors.py` | 文件通道 |
| audit | `audit/store.py`, `audit/writer.py`, `audit/query.py`, `audit/models.py` | 审计 |
| benchmark | `benchmark/generator/build.py` | 测评集生成 |
| webui | `webui/pages.py`, `webui/dashboard.py`, `webui/demo_api.py`, `webui/templates/*` | 演示前端 |
| ops | `ops/e2e_smoke.py`, `ops/gate_final.py`, `ops/name_lint.py`, `ops/export_public.py`, `ops/seed_demo.py`, `ops/tunnel_gpu.sh` 等 | 运维与验收门 |
| evals | `evals/m10_e2e.py`, `evals/m2_recognizers.py`, `evals/m8_quality.py`, `evals/thresholds.py`, `evals/m0_infra.py` 等 | 可执行验收 |
| gpu | `gpu/llm_keepalive.sh`, `gpu/setup_llm_service.sh` | GPU 保活/装机 |
| gpu-services | `gpu-services/llm_openai/service.py`, `gpu-services/llm_openai/run_gpu.sh` | GPU 侧 OpenAI 兼容服务 |

---

## 二、组件盘点矩阵

| # | 组件 | 声明能力（README/docs 原文） | 实际实现关键入口 | 外部接口/依赖 | 成熟度 |
|---|---|---|---|---|---|
| 1 | **common** | 配置加载、结构化日志、UTC 时间 `common/config.py:1` 模块 docstring；日志禁止原文 `common/logs.py:1` | `common/config.py:load_app_config`, `common/logs.py:setup_logging`, `common/timeutil.py:iso_utc` | PyYAML、python-dotenv（或标准库 `configparser`/`json`）、Pydantic | 实现 |
| 2 | **gateway** | OpenAI 兼容 `/v1/chat/completions`（流+非流）+ 文件通道 + 管理面 + 调试端点 `README.md:38` | `gateway/app.py:create_app`（`gateway/app.py:366` 绑定 POST `/v1/chat/completions`） | FastAPI、Uvicorn、HTTPX（`gateway/provider.py:forward_chat`）、SQLite（`audit/`） | 实现 |
| 3 | **recognizers** | 规则+校验位+语义词表已实装；NER 为适配器预留位 `README.md:7` | `recognizers/pipeline.py:detect_full` 合并 rule+semantic；`recognizers/ner/adapter.py:20` `NerAdapter` P0 空实现 | 纯 Python（正则/词表）；NER 槽位预留；语义层可选 judge 后端（`recognizers/semantic/adapter.py:_judge_lookup`） | 规则层实现；NER 占位；语义层实现（词表驱动，judge 为升级路径） |
| 4 | **masking** | 会话稳定可逆脱敏：占位符按密钥哈希固定；流式缓冲还原；工具调用参数还原 `README.md:8` | `masking/mapper.py:207` `SessionMapper`；`masking/remap.py:50` `StreamRestorer`；`masking/toolbuf.py:78` `ToolCallBuffer` | HMAC-SHA256（`hashlib`）、SQLite（`masking/session_store.py:SessionStore`） | 实现 |
| 5 | **routing** | 普通脱敏走互联网模型；敏感个人信息/工作秘密切政务云；命中密级标识直接拦截 `README.md:9` | `routing/engine.py:69` `decide` 纯函数；R1-R6 矩阵 | 规则引擎（无外部服务） | 实现 |
| 6 | **outguard** | AI 生成标识（显式+隐式元数据）、代答/拒答库 `README.md:11` | `outguard/service.py` 门面；`outguard/label.py:ai_label_tail`；`outguard/fallback.py` 模板加载；`outguard/moderation.py:NullModerator` | Jinja2（模板渲染）；输出审核后端可选（当前 P0 为空） | 实现（AI 标识+拦截文案）；输出审核 hook 占位（`NullModerator`） |
| 7 | **filechannel** | Word/Excel/PDF/扫描件"公开前体检"；一键导出彻底删除版 `README.md:10` | `filechannel/inspect.py:82` `inspect_bytes`；`filechannel/sanitize.py` 各 sanitize 函数；`filechannel/service.py:FileService` | python-docx、openpyxl、pypdfium2、pikepdf、PyMuPDF、PIL、rapidocr+onnxruntime（可选） | 实现 |
| 8 | **audit** | 日志只存脱敏内容，全程可审计；审计看板 `README.md:12` | `audit/store.py:57` `assert_no_raw_pii`；`audit/writer.py:SqliteAuditWriter`；`audit/query.py:page_events` | SQLite（WAL 模式） | 实现 |
| 9 | **benchmark** | 合成测评集（结构化号码召回 ≥99.5%，实测 100%）`README.md:13` | `benchmark/generator/build.py:33` `build_all` 产出 cases/fixtures/manifest | faker、PyMuPDF（`fitz`，`config/synthetic_corpus.yaml:9`） | 实现 |
| 10 | **webui** | 演示前端页面、审计看板、文件通道演示、一键注入/清除演示态 | `webui/pages.py:mount` 挂载 `/webui`、`/webui/dashboard`、`/webui/demo` 等 | FastAPI 静态模板、Jinja2 | 实现 |
| 11 | **ops** | 名称守卫、e2e 冒烟、公开导出、GPU 隧道 | `ops/name_lint.py:lint_repo`；`ops/e2e_smoke.py` U1-U8；`ops/export_public.py`；`ops/gate_final.py` 九项终检 | git（导出树依赖 `git ls-files`）；subprocess（启动各门 eval） | 实现 |
| 12 | **evals** | 可执行验收入口（`python -m evals.*`，`exit 0 = 通过`）`README.md:31` | `evals/m10_e2e.py:main`；`evals/m2_recognizers.py`；`evals/m8_quality.py`；`evals/thresholds.py` | pytest、httpx、torch+transformers（M2/M8）、rapidocr（M6 OCR） | 实现 |
| 13 | **gpu** | GPU 机本地大模型服务保活与装机脚本 | `gpu/llm_keepalive.sh` 常驻保活；`gpu/setup_llm_service.sh` 预置权重 | shell、tmux/screen、ssh 隧道 | 实现（环境脚本） |
| 14 | **gpu-services** | GPU 机 OpenAI 兼容服务（`llm_openai`，`:9004`） | `gpu-services/llm_openai/service.py:app` FastAPI；`run_gpu.sh` 启动 | FastAPI、transformers、torch（fp16+sdpa）；可选 `LLM_FORWARD_URL` 透传模式 | 实现 |

---

## 三、README 声明与实测支撑对照

| # | README 声明 | 位置 | 实现证据 | 测试/验收支撑 |
|---|---|---|---|---|
| 1 | 结构化证件/号码校验位召回实测 100% | `README.md:7`、`README.md:13` | `recognizers/pipeline.py:detect_full`；`masking/normalize.py:normalize_value` 各类归一 | `evals/m2_recognizers.py` 断言 `structural micro=1.00`；`evals/thresholds.py:RECALL_STRUCTURAL=1.00` | **有测试支撑** |
| 2 | CPU 2000 字 <100ms | `README.md:13` | `recognizers/pipeline.py:detect_full`；`masking/normalize.py` | `evals/m2_recognizers.py` 打印 `2000ch detect ×10 mean <100ms`；`evals/thresholds.py:RULE_LATENCY_MS_2000CH=100` | **有测试支撑** |
| 3 | 会话稳定可逆脱敏（多轮不变号） | `README.md:8` | `masking/mapper.py:SessionMapper`；`masking/session_store.py:SessionStore` | `ops/e2e_smoke.py` U1-U5 断言还原一致；`evals/t0_stream.py` `step_remap_mangled_forms` 全等还原 | **有测试支撑** |
| 4 | 流式缓冲还原 | `README.md:8` | `masking/remap.py:StreamRestorer` 状态机 | `ops/e2e_smoke.py` U3 流式；`evals/t0_stream.py` 随机切块 `StreamRestorer` | **有测试支撑** |
| 5 | 工具调用参数还原 | `README.md:8` | `masking/toolbuf.py:ToolCallBuffer.finalize` + `restore_arguments` | `ops/e2e_smoke.py` U5；`evals/t0_stream.py` tool-call 路径 | **有测试支撑** |
| 6 | 密级标识直接拦截 | `README.md:9` | `routing/engine.py:decide` `BLOCK_TYPES` 含 `CLASSIFICATION_MARK`；`outguard/fallback.py` 模板 | `ops/e2e_smoke.py` U2；`evals/m4_routing.py`（如有） | **有测试支撑** |
| 7 | AI 生成标识（显式+隐式） | `README.md:11` | `outguard/label.py:ai_label_tail` + `ai_annotations`；`gateway/sse.py:compose_chat_stream` finish 注入 | `ops/e2e_smoke.py` U8 断言 `x-anongw-ai-label=1`、尾注、annotations | **有测试支撑** |
| 8 | 文件通道彻底删除导出 | `README.md:10` | `filechannel/sanitize.py` docx run-delete / xlsx cell+hidden delete / pdf engine chain / scan_pdf raster redaction | `ops/e2e_smoke.py` U6；`evals/m6_files.py` 断言 re-ingest 零残留 | **有测试支撑** |
| 9 | 审计看板 | `README.md:12` | `webui/dashboard.py` + `webui/pages.py` 挂载 `/webui/dashboard` | `ops/e2e_smoke.py` U5；`evals/m10_e2e.py` 看板探针冒烟 | **有测试支撑** |
| 10 | NER 为人名/住址模型化识别，属适配器预留位 | `README.md:7` | `recognizers/ner/adapter.py:20` `NerAdapter` P0 返回空表；`get_ner_adapter` 单例 | 无 NER 专项 eval；`docs/assets/specs/recognizers-rule.md` 明确 NER 为规划项 | **仅声明**（P0 空实现，规划中） |
| 11 | 输出审核 moderation hook | 文档提及 `docs/assets/specs/outguard.md` | `outguard/moderation.py:NullModerator`；`gateway/pipeline.py:_output_redact` 回退路径 | `evals/m5_outguard.py` 可能仅覆盖 NullModerator；真实后端未接 | **部分支撑**（框架在，后端为空） |

---

## 四、配置与密钥处理

### 4.1 配置加载
- `common/config.py` 使用 Pydantic `extra="forbid"`；`AppConfig`、`UpstreamCfg`、`ThresholdsCfg` 严格校验 `common/config.py:AppConfig`。
- `load_app_config` 支持 `ANONGW_<K>` 环境变量覆盖，但 `_SECRET_ENV_FIELDS` 豁免 `admin_key_env`/`mask_key_env` 字段名覆盖（仍需在 env 或 yaml 提供值）`common/config.py:_SECRET_ENV_FIELDS`。
- `load_dept_keys` 校验 sha256 小写 64 位十六进制 `common/config.py:load_dept_keys`。
- `resolve_secret` 支持 `env:` / `vault:` / literal 前缀 `common/config.py:resolve_secret`。

### 4.2 密钥红线
- `.env.example` 仅展示占位符：`MASK_KEY`、`MOCK_KEY`、`UPSTREAM_BIGMODEL_KEY`、`REAL_LLM_KEY`、`GOVCLOUD_LLM_KEY`、`SEMANTIC_JUDGE_BASE_URL/KEY/MODEL`；**本稿不转印任何真实值**。
- `config/dept_keys.yaml` 仅存 sha256 摘要（三部门 demo：县政府办、民政局、某镇）；明文 key 不在仓库。
- `common/logs.py` 禁止记录未脱敏原文（除 `--debug` 写入 `data/debug/`）`common/logs.py:module docstring`。
- `gpu-services/llm_openai/service.py:154` `_auth_fingerprint` 只记 SHA256 前 8 位；`FORWARD_KEY` 恒不落盘/日志/回显 `gpu-services/llm_openai/service.py:87-88`。

### 4.3 配置脆弱点
- `config/app.yaml` 中 `upstreams` 的 `internet_real` 与 `govcloud_local_real` 共用端口 `9004`，实际指向同一 `llm_openai` 服务 `config/app.yaml:upstreams`；若误配会双写同一上游。
- `moderation_model` 为空字符串 `config/app.yaml:moderation_model`；当前 `NullModerator` 不会上报，但字段存在易被误填为假后端。
- `outguard_texts` 路径硬编码相对路径 `config/app.yaml:outguard_texts`；若 cwd 非仓库根会 404。

---

## 五、README 定量声明 vs 代码/evidence 现状

| 声明 | 代码/证据 | 结论 |
|---|---|---|
| 结构化号码召回 100% | `evals/m2_recognizers.py` 断言 `structural micro=1.00`；`evals/thresholds.py:RECALL_STRUCTURAL=1.00` | 有测试支撑 |
| CPU 2000 字 <100ms | `evals/m2_recognizers.py` 打印 `mean <100ms`；`evals/thresholds.py:RULE_LATENCY_MS_2000CH=100` | 有测试支撑 |
| 流式缓冲还原 | `masking/remap.py:StreamRestorer` + `gateway/sse.py:compose_chat_stream` | 有测试支撑 |
| 工具参数还原 | `masking/toolbuf.py:ToolCallBuffer.finalize` + `gateway/pipeline.py:_restore_choices` | 有测试支撑 |
| 密级标识拦截 | `routing/engine.py:decide` `BLOCK_TYPES` + `outguard/fallback.py` | 有测试支撑 |
| AI 生成标识 | `outguard/label.py` + `gateway/sse.py` finish 注入 | 有测试支撑 |
| 文件彻底删除导出 | `filechannel/sanitize.py` 各引擎 + re-ingest 零残留硬闸 | 有测试支撑 |
| 审计看板 | `webui/dashboard.py` + `ops/e2e_smoke.py` U5 | 有测试支撑 |
| NER 已实装 | `recognizers/ner/adapter.py:20` P0 返回空表 | **仅声明**（P0 占位） |
| 输出 moderation 后端 | `outguard/moderation.py:NullModerator` | **部分支撑**（框架在，后端未接） |

---

## 六、占位/未实现片段

| 组件 | 占位 | 文件:行 | 说明 |
|---|---|---|---|
| recognizers/ner | `NerAdapter` P0 空实现 | `recognizers/ner/adapter.py:20-27` | `detect` 直接 `return []`；日志仅 debug 记录 `model_path` 为 "ignored_p0" |
| outguard/moderation | `NullModerator` | `outguard/moderation.py` | `moderate` 直接返回 `Verdict(flagged=False)`；真实后端 env 驱动未接 |
| routing/semantic | judge 升级路径为 env 驱动 | `recognizers/semantic/adapter.py:_judge_lookup` | degrade-safe，但默认无外部 judge；词表三层（STRONG/EXFIL/WEAK）已实装 |
| config | `moderation_model` 空 | `config/app.yaml:moderation_model` | 未配置任何模型；输出审核全挂 Null |
| benchmark | m8_baselines 目录/实现缺失 | `docs/assets/CONTRACTS.md:1` pain point 2 | `m8_quality` 运行需要 `baselines` 但目录/生成逻辑不完整；`evidence/gate-final-20261002.md` 记录 `m8_quality` 曾因 deferred 和 51!=50 失败 |
| gpu | 隧道单点依赖 | `ops/gate_final.py:32-36` | U8/m8_quality 依赖 GPU 隧道；隧道断则 DEFERRED；`evidence/gate-final-20261002.md` 记录多次因隧道掉线 FAIL |

---

## 七、文档/代码不一致与已知脆弱点

### 7.1 已知不一致
1. **JSON key 检测缺口**：`docs/assets/CONTRACTS.md` pain point 1 明确记录“JSON key 未进识别面”；`recognizers/pipeline.py` 主检测面为 message content leaves；`_aux_texts` 虽枚举 top-level/message-level/tool_calls key，但 key 本身不参与 regex 检测（仅 value 参与）。若 key 含敏感词（如 `api_key`），当前不会脱敏。
2. `preserve_semantic` 字段未使用：`docs/assets/CONTRACTS.md` pain point 3；代码中 `Finding` model 有 `preserve_semantic` 字段（`recognizers/models.py:Finding`），但 `detect_full` 返回值未设置，下游也未消费。
3. `m8_baselines` 规划但未实现：`docs/assets/CONTRACTS.md` pain point 2；`evals/m8_quality.py` 运行依赖 `benchmark/generator/build.py` 产出，但 baselines 对比项缺失，导致 quality report 不完整。
4. PERSON/ADDRESS 启发式静态：`docs/assets/CONTRACTS.md` pain point 4；`recognizers/rule` 中 `PERSON` 检测依赖静态姓氏表 + 前后中文边界启发式，无上下文语义消歧。

### 7.2 明显脆弱点
1. **会话映射容量与清理**：`masking/session_store.py:SessionStore` 容量 2x eviction（默认 128 映射？）；`bind_session` 无 TTL 写时即落库；`cleanup_loop` 按 TTL + idle 清理，但 `session_owner` 表无自动过期，长运行可能导致 `session_owner` 表缓慢增长。
2. **DIGEST_WIDTHS 12-bit 风险**：`masking/mapper.py:DIGEST_WIDTHS=(8,10,12)`；12-bit hex 仅 16^12 种，理论碰撞概率在大流量下不可忽略；`restore_tolerant` 依赖“映射表命中终审”，若碰撞导致错误还原，属于低概率高影响事件。
3. **上游内容过滤 400（code=1301）**：真实大模型腿（INTERNET/GOVCLOUD）存在内容过滤 400；`ops/e2e_smoke.py:1240` 有 1+2 次重试逻辑，但仍会 raise `AssertionError` 若全部失败；`evidence/gate-final-20261002.md` 记录多次因此 FAIL。
4. **GPU 隧道单点**：U8/m8_quality 依赖 `ops/tunnel_gpu.sh` 到 GPU 机 `:9004`；隧道断即 DEFERRED 或 FAIL；非 GPU 机故障本身，但链路脆弱。
5. **toolbuf 单响应幂等**：`masking/toolbuf.py:ToolCallBuffer.finalize` 返回空表；文档强调“实例不可跨响应复用”，但若上游异常重试导致同一 `ToolCallBuffer` 被二次 `finalize`，无强 guard（仅靠上层 SSE 管线重建）。
6. **SSE 超长行丢弃**：`gateway/sse.py:iter_sse_data_lines` 超 `GATEWAY_SSE_LINE_MAX_BYTES`（8MB）丢弃该行；畸形上游可导致事件丢失，但属于 T7.2 畸形输入加固的故意设计。

---

## 八、eval/验收现状（截至 evidence/gate-final-20261002.md）

| 门禁 | 脚本 | 当前状态（证据原文） | 备注 |
|---|---|---|---|
| D0 | `ops/gate_d0.py` | — | 基础设施门 |
| B1-B6 | `ops/gate_b1.py` … `gate_b6.py` | — | 各模块回归 |
| FINAL | `ops/gate_final.py` | **FAIL**（记录中 gate_final#1 与 #2 均 FAIL） | gate_final#1 FAIL 4/9（GPU 隧道 DOWN 导致 U8 DEFERRED 违反 deferred=0）；gate_final#2 FAIL 因外部截断；S2 重试亦 FAIL（隧道掉线 + GLM 内容过滤 400） |
| M2 | `evals/m2_recognizers.py` | 通过（micro=1.00，latency <100ms） | |
| M8 | `evals/m8_quality.py` | 部分通过/ DEFERRED | `evidence` 记录 `m8_quality` 曾因 "审计行数 51 != 50" root cause 未解；隧道断时 DEFERRED |
| M10 | `evals/m10_e2e.py` | 依赖 U8；U8 真实腿 FAIL 时整体 FAIL | T5.3 收尾（seed_demo）逻辑已实装 `evals/m10_e2e.py:57-152` |
| M11 | `evals/m11_robust.py` | 包含在 gate_final ⑧ | 畸形输入/并发/SSE 有界终止 |

> 结论：功能面主链路（U1-U7 mock）稳定；真实大模型全链 U8 与 m8_quality 受 GPU 隧道与上游内容过滤影响，尚未达到 gate_final 全绿。

---

## 九、外部依赖清单

| 依赖 | 来源 | 用途 | 备注 |
|---|---|---|---|
| fastapi==0.141.1 | PyPI | 网关/GPU 服务 Web 框架 | 已冻结 `constraints.txt` |
| uvicorn | PyPI | ASGI 服务器 | |
| httpx==0.28.1 | PyPI | HTTP 客户端（e2e/admin 查询） | |
| pydantic==2.13.5 | PyPI | 数据校验 | `extra="forbid"` 贯穿 |
| pyyaml | PyPI | 配置加载 | |
| jinja2 | PyPI | 模板渲染（outguard 拦截文案 + webui） | |
| python-docx | PyPI | docx 解析 | |
| openpyxl | PyPI | xlsx 解析 | |
| pypdfium2 / pikepdf / PyMuPDF | PyPI | PDF 解析/编辑/重OCR | `config/filechannel.yaml` 引擎链 |
| rapidocr + onnxruntime | PyPI | OCR（扫描件） | 可选 extras；CPU 参数 `config/filechannel.yaml` |
| faker | PyPI | 合成语料（benchmark） | `config/synthetic_corpus.yaml` |
| torch==2.14.0 + transformers==4.57.6 | PyPI | GPU 服务推理（llm_openai） | 仅 GPU 机/评测需要 |
| presidio-analyzer | PyPI | bench extras（M2 baseline 对比） | 非主链路 |

---

## 十、结论与建议

1. **主链路已实现**：common → gateway → recognizers（rule+semantic） → masking → routing → outguard（AI 标识+拦截文案） → audit → webui → ops/evals 全链路可运行，mock 链 U1-U7 稳定。
2. **关键占位未清**：NER P0 空实现、输出 moderation NullModerator、m8_baselines 缺失。若对外宣称“完整 NER”或“输出内容审核已集成”则属于声明超前。
3. **真实大模型链未全绿**：gate_final 记录中多次 FAIL/U8 DEFERRED，根因在 GPU 隧道稳定性 + 上游内容过滤 400；非代码逻辑错误，但影响终检通过。
4. **建议优先级**：
   - P0：补 m8_baselines 或降级声明，修复 m8_quality "51 != 50" 统计偏差；
   - P1：为 NER 适配器接入轻量模型或明确划入“后续版本”并更新 README；
   - P2：增强 tunnel_gpu.sh 自动重连/多出口容错，减少 U8/m8_quality 环境性 FAIL；
   - P3：补 JSON key 检测面（若业务敏感词可能出现在字段名）。

---

## 十一、证据来源

- 源码行号均来自本次会话 Read 工具输出或本机 grep -n 结果。
- `evidence/gate-final-20261002.md`：396 行终检记录，包含 v3 修订、S2 修复清单、U8 tolerant restore 修复验证、当前 FAIL 状态。
- `ops/e2e_smoke.py`：U1-U8 八用例完整实现与断言（本次读取 U8 段 `ops/e2e_smoke.py:1240-1338` 及通用工具 `ops/e2e_smoke.py:300-380`）。
- `ops/gate_final.py`：九项终检结构 `ops/gate_final.py:64-82` 及超时预算 `ops/gate_final.py:58-60`。
- `evals/m10_e2e.py`：T5.3 收尾（seed_demo + 看板冒烟）`evals/m10_e2e.py:57-224`。
- `evals/thresholds.py`：全量阈值常量。
- `docs/assets/CONTRACTS.md`：pain points 1-4。
- `docs/assets/specs/*.md`：各模块 M1-M8 spec 与 eval pointers。
