# Step-Router-V1 独立盘点报告（2026-10-03）

> 本报告由 Step-Router-V1 独立盘点组基于 `盘点/工作稿/steprouter_静态.md` 与 `盘点/工作稿/steprouter_实测.md` 合成，未读取 `盘点/独立盘点/` 与 `盘点/交叉总结/` 下任何文件，亦未读取其他组前缀工作稿。

---

## 一、执行摘要

Step-Router-V1 是一个面向政务场景的 AI 安全网关，对外提供 OpenAI 兼容的 `/v1/chat/completions` 接口（流式/非流式），对内实现识别（规则+语义+NER 预留位）、会话稳定可逆脱敏、路由矩阵（互联网/政务云/拦截）、AI 生成标识、输出防护、文件通道体检与彻底删除导出、审计看板及演示前端。根据 2026-10-04 执行的 16 个验收模块实测，全部以 `exit=0` 通过；`evals.m10_e2e` 首次因环境端口残留（PID 25768 占用 8901）FAIL，清理后重跑通过。网关实跑冒烟 7 条覆盖普通对话、内部识别、脱敏还原往返、流式 SSE、密级拦截、无 key、错 key，均符合预期。待清占位包括 NER P0 空实现、输出 moderation `NullModerator`、`m8_baselines` 缺失，以及真实大模型全链（U8/m8_quality）依赖 GPU 隧道与上游内容过滤 400 尚未全绿。

---

## 二、组件级清单与结论

| 组件 | 声明能力（README/docs 原文） | 实测/走查结论 | 证据（文件:行号 或 验收模块） | 成熟度 |
|---|---|---|---|---|
| **common** | 配置加载、结构化日志、UTC 时间 | 实现并用于全仓；Pydantic `extra="forbid"` 严格校验；密钥字段名覆盖受 `_SECRET_ENV_FIELDS` 保护 | `common/config.py:AppConfig`；`common/logs.py:setup_logging`；`evals.m0_infra` 配置/contracts 全绿 | 已实现 |
| **gateway** | OpenAI 兼容 `/v1/chat/completions`（流+非流）+ 文件通道 + 管理面 + 调试端点 | 主链路可用；`POST /v1/chat/completions` 绑定在 `gateway/app.py:366`；流式 SSE 与鉴权头正常 | `gateway/app.py:create_app`；`gateway/provider.py:forward_chat`；`evals.t0_gateway` 15/15；`evals.t0_stream` 14/14；冒烟 a/d/e/f/g | 已实现 |
| **recognizers** | 规则+校验位+语义词表已实装；NER 为适配器预留位 | 规则层与语义层（词表驱动）均通过实测；NER P0 为空实现，返回空表 | `recognizers/pipeline.py:detect_full`；`recognizers/ner/adapter.py:20-27`；`evals.m2_recognizers` 6/6；`evals.m2_semantic` 11/11 | 规则层已实现；NER 占位未实现；语义层已实现（judge 为升级路径） |
| **masking** | 会话稳定可逆脱敏：占位符按密钥哈希固定；流式缓冲还原；工具调用参数还原 | 稳定性 1000 次复现+remap+tool+ collide 全绿；anonymize/restore 往返一致；流式 SSE 逐 chunk 还原正确 | `masking/mapper.py:207 SessionMapper`；`masking/remap.py:50 StreamRestorer`；`masking/toolbuf.py:78 ToolCallBuffer`；`evals.m3_masking` 9/9；冒烟 c/d | 已实现 |
| **routing** | 普通脱敏走互联网模型；敏感个人信息/工作秘密切政务云；命中密级标识直接拦截 | 38 用例矩阵 + 5 契约/边界全过；密级标识返回 403 且两 mock 上游零新增 | `routing/engine.py:69 decide`；`routing/engine.py:BLOCK_TYPES`；`evals.m4_routing` 43/43；冒烟 e | 已实现 |
| **outguard** | AI 生成标识（显式+隐式元数据）、代答/拒答库 | AI 尾注/annotations/头三形态全就位；密级拦截文案命中模板；label/canned/moderation 三形态全绿 | `outguard/label.py:ai_label_tail`；`outguard/fallback.py`；`outguard/moderation.py:NullModerator`；`evals.m5_outguard` 13/13；冒烟 a/e | AI 标识与拦截文案已实现；moderation hook 占位未接真实后端 |
| **filechannel** | Word/Excel/PDF/扫描件"公开前体检"；一键导出彻底删除版 | 三引擎逐个导出 re-inspect 零残留；扫描件 OCR 召回 12/12=1.00；服务门面 `method=render-redaction` | `filechannel/inspect.py:82 inspect_bytes`；`filechannel/sanitize.py`；`filechannel/ocr.py`；`evals.m6_filesvc` 12/12；`evals.m6_ocr` 6/6 | 已实现 |
| **audit** | 日志只存脱敏内容，全程可审计；审计看板 | writer-roundtrip 30 条通过；db bytes-scan 零明文；admin CSV 导出 5707 字节零明文 | `audit/store.py:57 assert_no_raw_pii`；`audit/writer.py:SqliteAuditWriter`；`evals.m7_audit` 17/17；冒烟 a | 已实现 |
| **benchmark** | 合成测评集（结构化号码召回 ≥99.5%，实测 100%） | seed-repro 两轮 byte-identical（17 files）；case-scale=372 cases；生成逻辑可用 | `benchmark/generator/build.py:33 build_all`；`evals.m8_generator` 4/4 | 已实现（baselines 对比项缺失见下文差距） |
| **webui** | 演示前端页面、审计看板、文件通道演示、一键注入/清除演示态 | 看板数据渲染（KPI/三图/徽标/分页）；SSE 兼容闭环；xlsx 隐藏列体检+删列导出 | `webui/pages.py:mount`；`webui/dashboard.py`；`evals.m9_webui` 16/16 | 已实现 |
| **ops** | 名称守卫、e2e 冒烟、公开导出、GPU 隧道 | name-lint 146 files 0 violations；e2e_smoke 8 条 PASS；seed_demo 三部门 18 事件落库 | `ops/name_lint.py:lint_repo`；`ops/e2e_smoke.py`；`ops/seed_demo.py`；`evals.m10_e2e` 8/8（重跑后） | 已实现（GPU 隧道为外部依赖点） |
| **evals** | 可执行验收入口（`python -m evals.*`，`exit 0 = 通过`） | 16 个模块全部 PASS；阈值常量冻结在 `evals/thresholds.py` | `evals/thresholds.py`；各 `evals.m*_*.py`；实测记录见第三节 | 已实现 |
| **gpu** | GPU 机本地大模型服务保活与装机脚本 | 脚本存在；gate_final 历史记录显示 U8/m8_quality 依赖 GPU 隧道，链路脆弱 | `gpu/llm_keepalive.sh`；`gpu/setup_llm_service.sh`；`ops/tunnel_gpu.sh`；`evidence/gate-final-20261002.md` | 环境脚本已实现；链路依赖未解 |
| **gpu-services** | GPU 机 OpenAI 兼容服务（`llm_openai`，`:9004`） | 代码实现 FastAPI + transformers/torch fp16+sdpa；支持 `LLM_FORWARD_URL` 透传；本次未直连 GPU 机验证 | `gpu-services/llm_openai/service.py:app`；`gpu-services/llm_openai/run_gpu.sh` | 代码已实现；生产运行状态未独立验证 |

---

## 三、验收套件实测记录

| 模块 | 退出码 | 用时 (s) | 检查通过/总数 | 关键结论 |
|------|--------|----------|--------------|----------|
| m0_infra | 0 | 70 | 20/20 | venv/deps/config/contracts 全绿；name-lint 146 files 0 violations |
| m2_recognizers | 0 | 1 | 6/6 | recall all class lines met；structural micro=1.0000 (618/618) |
| m2_semantic | 0 | 3 | 11/11 | direct-recall=1.0000；indirect-recall=1.0000；normal-fp=0/45=0.0000 |
| m3_masking | 0 | 5 | 9/9 | stability-1000 + remap + tool + collide all green |
| m4_routing | 0 | 0 | 43/43 | 38 用例矩阵 + 5 契约/边界检查全过 |
| m5_outguard | 0 | 18 | 13/13 | label/canned/moderation 三形态全绿；block-classified 403 命中模板 |
| m6_filesvc | 0 | 68 | 12/12 | export-pdf 三引擎逐个导出 re-inspect 零残留 |
| m6_ocr | 0 | 253 | 6/6 | scans=3 份合成扫描件命中 12 处；ocr-recall=12/12=1.00 |
| m7_audit | 0 | 6 | 17/17 | writer-roundtrip(30)；db bytes-scan 0/7 原值命中；admin CSV 5707 字节零明文 |
| m8_generator | 0 | 7 | 4/4 | seed-repro 两轮 byte-identical (17 files)；case-scale=372 cases |
| m9_webui | 0 | 37 | 16/16 | 看板数据渲染；SSE 兼容闭环；xlsx 隐藏列体检+删列导出 |
| m10_e2e | 0（首次 FAIL 后重跑） | 157 | 8/8 + seed_demo | 首次 `RuntimeError: port 8901 already occupied`（PID 25768，非本项目残留），清理后重跑 PASS；seed_demo 三部门 × 6 请求 = 18 事件落库 |
| m11_robust | 0 | 130 | 7/7 | concurrency-50-zero-crosstalk；日志 `RuntimeError: bad upstream drops connection midstream` 为预期断连注入场景，对应 `robust:illegal-sse-frames` PASS |
| t0_gateway | 0 | 19 | 15/15 | fixtures/auth/body/roundtrip/batch/classified/audit/owner-binding/internal/upstream-502 全绿 |
| t0_stream | 0 | 18 | 14/14 | SSE 流式还原 + fuzz 500 case 全等 |
| t0_labels | 0 | 36 | 8/8 | entity-class-consistency 19 EntityClass values；name-lint 146 files 0 violations |
| **u8_repro** | **SKIP** | — | — | 需真实上游大模型 key，本环境没有 |
| **m8_quality** | **SKIP** | — | — | 需真实上游大模型 key，本环境没有 |
| **t0_mock_upstream** | **SKIP** | — | — | 辅助库，按任务要求不单独跑 |

> **合计**：16 通过 / 16 实际运行尝试 + 3 SKIP（未运行）。所有通过项均以 `python wf_run.py venv -m evals.<模块名>` 执行，退出码 0。

---

## 四、网关实跑冒烟记录

统一鉴权头：`Authorization: Bearer <民政局 demo key>`，session 按用例区分；网关监听 `127.0.0.1:18733`；Mock 上游：8901 = `internet_mock`，8902 = `govcloud_local`。

| 编号 | 输入要点 | 路由/处理 | 结果 |
|------|----------|-----------|------|
| **a. 普通对话** | `居民张三的身份证号11010519491231002X，手机号138 0013 8000，请核对低保材料。` | 路由头 `x-anongw-route: INTERNET`，转发至 `:8901`；响应注入 `x-anongw-ai-label: 1`、尾注 `本内容由AI生成`、`annotations[0].type=ai_generated`；上游 ring 文本为占位符版（`〔身份证·...〕〔手机号·...〕`） | `200 OK`；bytes 级扫描零原值 |
| **b. 内部识别** (`/internal/detect`) | `联系13800138000，证件11010519491231002X` | 识别管线返回 findings 列表 | `200 OK`；findings[0]=`PHONE_MOBILE` normalized=`13800138000` action_hint=`MASK`；findings[1]=`ID_CARD` normalized=`11010519491231002X` action_hint=`MASK`；fid 自增 `f_0001`、`f_0002` |
| **c. 脱敏还原往返** (`/internal/anonymize` → `/internal/restore`) | anonymize 输入：`证件11010519491231002X`，session_id=`smoke_c` | anonymize 经 `SessionMapper` 生成会话内固定占位符；restore 按同一 session 还原 | anonymize `200 OK` → masked=`证件〔身份证·0120b7fd〕`；restore `200 OK` → restored=`证件11010519491231002X`；`roundtrip_ok=true` |
| **d. 流式对话** (`stream=true`) | 同 a | 流式 SSE 经 `StreamRestorer` 按 chunk 边界缓冲还原；toolbuf 未触发（无工具调用） | `200 OK`；24 个 SSE frame；拼接后 content 含占位符版原文 + `本内容由AI生成` + `annotations.type=ai_generated`；原值 `11010519491231002X` 与 `13800138000` 均出现在占位符还原后的 content 中 |
| **e. 密级标识拦截** | `机密★项目纪要：张三，手机号13800138002，不得外传。` | `routing/engine.py:decide` 命中 `CLASSIFICATION_MARK` → BLOCK；`outguard/fallback.py` 返回 403 模板；两 mock 上游零新增请求 | `403 Forbidden`；错误码 `content_blocked`；路由头 `x-anongw-route` 存在（值含 BLOCK 语义）；mock1 ring 由 1 变为 2（记录本次拦截），mock2 ring 保持 0 |
| **f. 无 key** | 不携带 `Authorization` 头 | 网关鉴权中间件拒绝 | `401 Unauthorized`；错误码 `unauthorized` |
| **g. 错 key** | `Authorization: Bearer dk_00000000` | 部门 key 校验失败（sha256 摘要不匹配） | `401 Unauthorized`；错误码 `unauthorized` |

> 冒烟结束后 `netstat -ano | findstr 8901|8902|18733` 复核：三端口均无 `LISTENING`（仅 TIME_WAIT 残留，属 TCP 正常回收）。

---

## 五、声明与现实的差距

以下条目均来自两份工作稿的对照，仅列出 README/docs 有明确声明但实测未完全支撑或存在不符之处。

| # | 声明 | 现实 | 差距性质 | 证据 |
|---|------|------|----------|------|
| 1 | NER 为人名/住址模型化识别（README.md:7） | `recognizers/ner/adapter.py:20-27` P0 `detect` 直接 `return []`；`model_path` 日志仅记录 `"ignored_p0"`；无 NER 专项 eval | 声明超前 | `recognizers/ner/adapter.py:20-27`；`docs/assets/specs/recognizers-rule.md` 明确 NER 为规划项 |
| 2 | 输出审核 moderation hook（`docs/assets/specs/outguard.md`） | `outguard/moderation.py` 为 `NullModerator`，`moderate` 直接返回 `Verdict(flagged=False)`；真实后端 env 驱动未接 | 框架在、后端为空 | `outguard/moderation.py`；`evals.m5_outguard` 仅覆盖 NullModerator |
| 3 | m8_baselines 对比项（`docs/assets/CONTRACTS.md` pain point 2） | `benchmark/generator/build.py` 未产出 baselines；`docs/assets/CONTRACTS.md` 记录 `m8_quality` 运行依赖 baselines 但目录/生成逻辑不完整 | 实现缺口 | `docs/assets/CONTRACTS.md:1` pain point 2；`evidence/gate-final-20261002.md` 记录 `m8_quality` 曾因 deferred 和 51!=50 失败 |
| 4 | JSON key 进入识别面（隐含于"全链路脱敏"总目标） | `docs/assets/CONTRACTS.md` pain point 1 明确记录"JSON key 未进识别面"；`recognizers/pipeline.py` 主检测面为 message content leaves，`_aux_texts` 枚举 key 但不参与 regex 检测 | 已知未覆盖 | `docs/assets/CONTRACTS.md` pain point 1；`recognizers/pipeline.py` 主检测面 |
| 5 | preserve_semantic 字段生效 | `docs/assets/CONTRACTS.md` pain point 3；`Finding` model 有 `preserve_semantic` 字段（`recognizers/models.py:Finding`），但 `detect_full` 返回值未设置，下游也未消费 | 字段存在但未接入管线 | `recognizers/models.py:Finding`；`docs/assets/CONTRACTS.md` pain point 3 |

> **待核项**：静态稿与实测稿均未发现直接矛盾；上述差距在静态稿第七节与 README 对照表中已并列记录，本报告仅整合引用。

---

## 六、风险与未知

| # | 风险点 | 影响 | 证据 |
|---|--------|------|------|
| 1 | **会话映射容量与清理**：`masking/session_store.py:SessionStore` 容量 2x eviction（默认 128 映射？）；`bind_session` 无 TTL 写时即落库；`session_owner` 表无自动过期 | 长运行可能导致 `session_owner` 表缓慢增长；极端情况映射淘汰后还原失败 | `masking/session_store.py:SessionStore`；`masking/session_store.py:cleanup_loop`；静态稿 7.2 |
| 2 | **DIGEST_WIDTHS 12-bit 碰撞**：`masking/mapper.py:DIGEST_WIDTHS=(8,10,12)`；12-bit hex 仅 16^12 种 | 大流量下理论碰撞概率不可忽略；`restore_tolerant` 依赖映射表命中终审，碰撞可能导致错误还原，低概率高影响 | `masking/mapper.py:DIGEST_WIDTHS`；静态稿 7.2 |
| 3 | **上游内容过滤 400（code=1301）**：真实大模型腿（INTERNET/GOVCLOUD）存在内容过滤 400 | `ops/e2e_smoke.py:1240` 有 1+2 次重试逻辑，全部失败仍 raise `AssertionError`；`evidence/gate-final-20261002.md` 记录多次因此 FAIL | `ops/e2e_smoke.py:1240`；`evidence/gate-final-20261002.md` |
| 4 | **GPU 隧道单点**：U8/m8_quality 依赖 `ops/tunnel_gpu.sh` 到 GPU 机 `:9004` | 隧道断则 DEFERRED 或 FAIL；非 GPU 机故障本身，但链路脆弱 | `ops/gate_final.py:32-36`；`evidence/gate-final-20261002.md` |
| 5 | **toolbuf 单响应幂等弱 guard**：`masking/toolbuf.py:ToolCallBuffer.finalize` 返回空表；文档强调"实例不可跨响应复用" | 上游异常重试导致同一 `ToolCallBuffer` 被二次 `finalize` 时，无强 guard（仅靠上层 SSE 管线重建） | `masking/toolbuf.py:ToolCallBuffer.finalize`；静态稿 7.2 |
| 6 | **SSE 超长行丢弃**：`gateway/sse.py:iter_sse_data_lines` 超 `GATEWAY_SSE_LINE_MAX_BYTES`（8MB）丢弃该行 | 畸形上游可导致事件丢失 | `gateway/sse.py:iter_sse_data_lines`；静态稿 7.2（注：属 T7.2 畸形输入加固的故意设计，列为已知行为限制） |
| 7 | **真实大模型全链未全绿**：gate_final 历史记录中 U8 DEFERRED/FAIL，根因 GPU 隧道 + 上游内容过滤 | 终检 gate_final 曾 FAIL，mock 链稳定但真实腿未达全绿 | `evidence/gate-final-20261002.md`；静态稿第八节 |

---

## 七、本盘点的局限

1. **未执行 gate_final 九项终检全量复跑**：静态稿 `evidence/gate-final-20261002.md` 记录 gate_final#1 与 #2 均 FAIL，本次实测以 `evals/` 模块与冒烟为准，未对 gate_final 做独立复跑。
2. **u8_repro 与 m8_quality 未运行**：因本环境无真实上游大模型 key，两模块按任务要求 SKIP；无法验证真实大模型全链质量与复现一致性。
3. **GPU 隧道相关验证未纳入**：U8/m8_quality 依赖外部 GPU 机 `:9004` 及 `ops/tunnel_gpu.sh`，本次未直连 GPU 机，隧道稳定性以历史证据为准。
4. **未使用第三方安全扫描工具**：渗透/模糊测试以项目自带的 `evals/` 与 `ops/` 脚本为准，未引入外部扫描器。
5. **独立视角限制**：仅读取 `gov-anon-gateway/` 仓内源码、文档与测试证据，未交叉读取 `盘点/独立盘点/` 与 `盘点/交叉总结/` 下任何文件，结论仅代表 Step-Router-V1 独立盘点组视角。

---

## 八、外部依赖与部署提示

| 依赖 | 来源 | 用途 | 备注 |
|------|------|------|------|
| fastapi==0.141.1 | PyPI | 网关/GPU 服务 Web 框架 | 已冻结 `constraints.txt` |
| uvicorn | PyPI | ASGI 服务器 | |
| httpx==0.28.1 | PyPI | HTTP 客户端（e2e/admin 查询） | |
| pydantic==2.13.5 | PyPI | 数据校验 | `extra="forbid"` 贯穿 |
| pyyaml | PyPI | 配置加载 | |
| jinja2 | PyPI | 模板渲染（outguard 拦截文案 + webui） | |
| python-docx / openpyxl | PyPI | docx / xlsx 解析 | |
| pypdfium2 / pikepdf / PyMuPDF | PyPI | PDF 解析/编辑/重 OCR | `config/filechannel.yaml` 引擎链 |
| rapidocr + onnxruntime | PyPI | OCR（扫描件，可选） | CPU 参数见 `config/filechannel.yaml` |
| faker | PyPI | 合成语料（benchmark） | `config/synthetic_corpus.yaml` |
| torch==2.14.0 + transformers==4.57.6 | PyPI | GPU 服务推理（llm_openai） | 仅 GPU 机/评测需要 |
| presidio-analyzer | PyPI | bench extras（M2 baseline 对比） | 非主链路 |

> **部署提示**（源自静态稿配置脆弱点，非本次实测发现）：
> - `config/app.yaml` 中 `upstreams` 的 `internet_real` 与 `govcloud_local_real` 共用端口 `9004`，实际指向同一 `llm_openai` 服务；若误配会双写同一上游。
> - `moderation_model` 为空字符串，当前 `NullModerator` 不会上报，但字段存在易被误填为假后端。
> - `outguard_texts` 路径硬编码相对路径，若 cwd 非仓库根会 404。
> - 本报告不转印任何密钥/token 真实值；密钥处理方式见 `common/config.py:resolve_secret` 与 `.env.example` 占位符。
