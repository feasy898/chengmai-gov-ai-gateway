# GLM-5.3-Flash 独立盘点组 · 实测工作稿

- 日期：2026-10-03（20:08–20:45 左右完成）
- 执行：GLM-5.3-Flash 盘点组「实测验证员」（独立机器时段，无并行盘点组）
- 对象：`D:/new-workspace/澄迈项目/政务AI安全/gov-anon-gateway`（政务 AI 安全网关）
- 方法：全部结论来自本会话亲手执行的命令与真实 HTTP 响应；未修改任何源码/配置/文档；验收失败不允许改代码，本组**未出现需要重跑的失败**（16/16 一次通过，其中 m4/m8/m9 为补记精确用时复跑 1 次，结果一致）。

---

## 一、执行环境与调用方式

- 验收入口（编排者提供，实测可用）：工作区根执行
  `python wf_run.py venv -m evals.<模块名>`
  - `wf_run.py` 内部直调 `gov-anon-gateway/.venv/Scripts/python.exe`，cwd=仓库根；
  - stdout 首行 `[wf_run] log=<日志路径> exit=<退出码> secs=<秒>`，详细日志在 `gov-anon-gateway/tmp/wf/`；
  - Python 3.12.10（系统 PATH）+ 仓库自带 venv（fastapi 0.142.2 / uvicorn 0.54.0 / torch 2.14.1 / transformers 4.57.6 / rapidocr 3.9.2 等，m0 自检 20 个发行包全过）。
- 本机：Windows Server 2022（win32 10.0.20348），Git Bash shell。
- 端口约定：mock 上游 :8901（internet_mock）/ :8902（govcloud_local）；网关默认 :9000；m10_e2e 另用 :9010 真实链路实例 + :9004 本地真实大模型服务（ssh 隧道 `anolis-gpu-tailnet`，进程实测在监听，非本组拉起）；m11_robust 独立用 :8911/:8912/:8913/:9012/:9013。

## 二、16 个验收模块逐项实测

命令：`cd "D:/new-workspace/澄迈项目/政务AI安全" && python wf_run.py venv -m evals.<模块名>`

| # | 模块 | 退出码 | 用时 | 结果 | 关键行 / 关键数字（摘自日志） |
|---|---|---|---|---|---|
| 1 | m0_infra | 0 | 37s | **PASS 20/20** | `M0 INFRA: 20/20 checks passed`；config `listen=9000`、4 上游、ai_label=「本内容由AI生成」；dept_keys.yaml 3 部门 sha256 有效；name-lint 146 文件 0 违规；契约模型（Finding/RouteDecision/AuditEvent/FileReport/ApiError 等）JSON 往返全过 |
| 2 | m2_recognizers | 0 | <1s | **PASS 6/6** | `M2 RECOGNIZERS: 6/6 checks passed`；372 用例；结构化号码 micro recall=**1.0000（618/618）**；白名单 FPR=0/22；2000 字检测均值 **1.99ms** <100ms |
| 3 | m2_semantic | 0 | 2s | **PASS 11/11** | `M2 SEMANTIC: 11/11 checks passed (injection×34, normal×45)`；直接/间接/工具描述注入召回全部 **1.0000 ≥0.9**；正常公文误拦 **0/45**（含否定句式陷阱）；2000 字 0.54ms <50ms |
| 4 | m3_masking | 0 | 3s | **PASS 9/9** | 1000 值重放一致、跨会话互异、还原往返精确；流式 500 组切块还原==整段还原；**10 万次插入 0 碰撞**（同摘要值自动升位 8→10→12 位验证）；50 占位符/2004 字还原均值 **0.259ms** <20ms |
| 5 | m4_routing | 0 | <1s（复跑实测 0s） | **PASS 43/43** | 路由矩阵 39 例全对：批量 ≥3 结构化号码→GOVCLOUD、单 PII→INTERNET 脱敏出网、密级词→BLOCK、白名单不计数；纯函数/§5.2 契约/阈值可配（下限钳 1）全过 |
| 6 | m5_outguard | 0 | 9s | **PASS 13/13** | 密级 403 文案==文案库模板（流/非流同源）；AI 标识三形态（尾注行/annotations/响应头）+ 自定义文案生效 + 空文案零注入；工具调用 content=null 标识；moderation hook flag 审计 |
| 7 | m6_filesvc | 0 | 40s | **PASS 12/12** | 15 份夹具 seeded 命中 **82/82**；docx 四位面（正文/表格/页眉/页脚）7/7 精确定位；xlsx 隐藏列/隐藏行/批注 13/13；pdf bbox==charbox 并集；三导出引擎 re-inspect **零残留**；50MB/种类/畸形全拒 |
| 8 | m6_ocr | 0 | 202s | **PASS 6/6** | 3 份合成扫描件身份证+手机号命中 12 处，OCR 身份证召回 **12/12=1.00 ≥0.9**；bbox 与绘制行 y 带相交；导出「渲染→黑框→整页重栅格化」再 OCR **零残留**；零命中扫描件 pdf-noop 字节原样 |
| 9 | m7_audit | 0 | 6s | **PASS 17/17** | SQLite WAL；泄漏原值事件 pre-enqueue 拒收（0 行）；库文件 bytes 级扫描 65536B **0/7 原值命中**；会话 LRU 复活/TTL 过期；admin API 401 负例/分页/13 项指标手算全等/report.csv 5707 字节零明文 + 公式注入防护 |
| 10 | m8_generator | 0 | 5s（复跑实测） | **PASS 4/4** | 372 用例双跑**字节级一致**（seed 20260928）；15 份 docx/xlsx/pdf 夹具 sha256 命中；身份证/USCC/Luhn 校验位复算全过；26 难负例独立无效 |
| 11 | m9_webui | 0 | 34s（复跑实测） | **PASS 16/16** | 5 页面 200；演示材料下载（docx 往返全等/扫描件 pdf→scan_pdf/HIGH 3 枚身份证全命中）；inspect FileReport 契约 risk=MID；export 重开**零残留**（X-Report-Id=file_3edc23d9bb7f5290）；看板回环闸 403/200；admin key 硬闸；SSE 闭环 25 帧/[DONE]/零占位符泄漏 |
| 12 | m10_e2e | 0 | 86s | **PASS 8/0/0** | `e2e_smoke: 8 PASS / 0 FAIL / 0 DEFERRED`，共发 **31 个 /v1/chat/completions**：U1 非流式往返（上游全文=原文脱敏版）/U2 流式+20 次随机切块重放全等/U3 真实文件三路由/U4 工具参数还原+历史 tool_calls 藏密级 403/U5 审计 27 行+库级 77824B 零明文+report.csv/metrics 交叉核对/U6 文件体检导出零残留/U7 注入拦截（干净版放行、埋注版 403 INJECTION+flag）/U8 **真实大模型腿 PASS**（:9004 双腿真实推理、key 指纹 09176d9b≠fb073764、回复占位符零泄漏） |
| 13 | m11_robust | 0 | 66s | **PASS 7/0** | `m11_robust: 7 PASS / 0 FAIL`：>10MB 两形态 413（chunked 排空后应答）；深嵌套/数组体/非法 JSON→400；超帽单行 400、帽内 15 万字符 200；50MB 上传三闸 413；非法 SSE 四模式有界终止（12MB 行洪泛客户端仅收 292 字节）；**50 并发零串扰**（批 27.7s，库 73728B 零明文）；事后 healthz+流式全链仍绿 |
| 14 | t0_gateway | 0 | 15s | **PASS 15/15** | `T0 GATEWAY NONSTREAM: 15/15 checks passed`；401 信封/400 校验/普通往返（上游 bytes 级零原值）/会话稳定占位符（同会话恒同、跨会话互异）/批量 GOVCLOUD 走 8902/密级 403 两 mock 零感知/审计 8 事件预览占位符版/零明文硬闸/出站全量检测面/会话属主绑定/上游不可达 502 |
| 15 | t0_stream | 0 | 10s | **PASS 14/14** | `T0 GATEWAY STREAM: 14/14 checks passed`；流式还原 byte-exact+标识三形态；stream=true 密级→403 JSON（非 SSE）；工具参数 hold-to-finish 单 delta 还原；500 组切块 fuzz==整段还原；mid-UTF-8 字节级切分；19 种残缺占位符形态逐字节还原 |
| 16 | t0_labels | 0 | 21s | **PASS 8/8** | `T0 LABELS: 8/8 checks passed`；docs/contracts/labels.md 结构/19 实体类中文标签/9 子类型/词表与加载器引用/国标对齐/不确定性标注（12 处显式标记）全过；name-lint 0 违规 |

**汇总：16/16 模块全部 exit=0，无一失败，无一重跑修复。** 模块总用时约 8.7 分钟（不含冒烟）。

### 按要求跳过项
- `evals.u8_repro`、`evals.m8_quality`：**SKIP**（需真实上游大模型 key，本环境没有；按要求未尝试）。
- `evals.t0_mock_upstream`：辅助库，按要求未单独跑（其能力已被 t0_gateway/t0_stream/m10_e2e 反复行使）。

---

## 三、网关实跑冒烟（独立于验收套件，真实进程 + 真实 TCP）

### 3.1 启动方式（读码确定，未改任何配置文件）

- 启动代码：`gateway/__main__.py:26-38`——`python -m gateway --host <h> --port <p>`，`--port` 缺省取 config `listen`；**改端口无需改配置，直接 `--port 18731`**（`common/config.py:94-105` 亦支持 `ANONGW_LISTEN` 环境变量覆盖，本次用启动参数）。
- mock 上游：`gateway/mock_upstream.py:16-19`——`python -m gateway.mock_upstream --port 8901 / --port 8902`（独立进程，8901/8902 隐含实例名与模型名）。
- 密钥构造（读码确认）：
  - `config/dept_keys.yaml` 存 3 部门 key 的 sha256（`common/config.py:119-132` 加载）；**明文构造规则 = `.env.example` 文档化演示值**，本冒烟直接采用 `evals/t0_gateway.py:64-65` 声明的演示明文：民政局 `dk_5e6f7a8b`、某镇 `dk_9c0d1e2f`（仓库公开夹具，非真实凭据；实测 `sha256(dk_5e6f7a8b)` 与 yaml 中民政局摘要一致——该断言在 t0_gateway fixtures 步骤中执行且 PASS）。
  - `MASK_KEY`：环境变量必需（`gateway/app.py:225-229` 缺失即 `RuntimeError`）。本次启动以 `MASK_KEY=$(python -c "print('cd'*32)")` 注入 t0_gateway.py:66 同款 64 位演示掩码值；**该值不写入本报告**。
  - `MOCK_KEY=mock-demo-key`（`evals/t0_gateway.py:49` 公开夹具值，上游 api_key_env 在请求期解析）。
- 落库重定向（避免写仓库 data/）：经 `ANONGW_AUDIT_DB` / `ANONGW_SESSION_DB` 环境变量覆盖（`common/config.py:94-105` 实现的官方覆盖机制，m0 有专项验证），指向 `盘点/工作稿/tmp_smoke/`。事后核实：`tmp_smoke/audit.db` 落 **7 事件（1 拦截）**，证明覆盖真实生效。
- 实际启动命令（仓库根）：
  ```bash
  MASK_KEY=$(.venv/Scripts/python.exe -c "print('cd'*32)") MOCK_KEY=mock-demo-key \
  ANONGW_AUDIT_DB=<盘点>/tmp_smoke/audit.db ANONGW_SESSION_DB=<盘点>/tmp_smoke/session_map.db \
  .venv/Scripts/python.exe -m gateway --host 127.0.0.1 --port 18731
  .venv/Scripts/python.exe -m gateway.mock_upstream --port 8901
  .venv/Scripts/python.exe -m gateway.mock_upstream --port 8902
  ```
- 启动结果（netstat 实测）：`127.0.0.1:8901 LISTENING (PID 7396)`、`127.0.0.1:8902 LISTENING (PID 23668)`、`127.0.0.1:18731 LISTENING (PID 21580)`；gateway.log 首条 `gateway.start ... port=18731 upstreams=[internet_mock, govcloud_local, internet_real, govcloud_real]`。
- 客户端：`盘点/工作稿/tmp_smoke/smoke_client.py`（httpx 真实 HTTP；样例文本/号码全部取自 `evals/t0_gateway.py` 公开合成夹具，非真实个人信息）。

### 3.2 逐请求实测记录（8 组，全部真实 HTTP）

| # | 输入要点 | 路由判定与上游 | 响应码 | 关键响应内容（实测摘录） |
|---|---|---|---|---|
| 0 | GET /healthz、/v1/models | — | 200/200 | `{"ok":true,"service":"gov-anon-gateway"}`；models 含 `mock-chat(INTERNET)/gov-chat(GOVCLOUD)/local-chat-8b×2`（带 route 标签、仅名字） |
| a | 普通对话：「今天下午三点召开全镇防汛工作会议…」 | **INTERNET**，:8901 +1 | 200 | 响应头 `x-anongw-ai-label: 1`；正文尾注 `本内容由AI生成` 在位；首请求时延 682.8ms（含会话建库） |
| b | 含身份证+手机号：「居民张三的身份证号11010519491231002X，手机号138 0013 8000…」 | **INTERNET**，:8901 +1 | 200 | ① `/internal/detect` 识别明细：`f_0001 PERSON 张三`、`f_0002 ID_CARD 11010519491231002X`、`f_0003 PHONE_MOBILE 13800138000`（分隔符写法已归一化）；② 客户端拿到**还原版**（原值在位、占位符形状零残留）；③ mock 上游 `/admin/text` bytes 级实测：原身份证/手机号**零命中**，收到的是 `〔人名·a880e8ca〕` 等占位符 |
| c | `/internal/anonymize` → `/internal/restore` 往返（session=smoke_roundtrip） | 调试端点（部门 key 鉴权） | 200/200 | masked=`证件〔身份证·ccaafc16〕，联系电话〔手机号·83d6a8d0〕`（2 条映射）；restored=`证件11010519491231002X，联系电话13800138000`，与原文**逐字全等** |
| d | 流式 `/v1/chat/completions` stream=true（同 b 文本） | **INTERNET**，SSE | 200 | `content-type: text/event-stream`；28 帧；逐 delta 拼接后原值完整在位、占位符零残留、尾注「本内容由AI生成」在位；帧级原始 JSON 核查：**finish 帧带 `annotations:[{"type":"ai_generated","text":"本内容由AI生成"}]`**（首次冒烟客户端报 None 系客户端采集写法问题，以原始帧为准） |
| e | 密级标识：「机密★项目纪要：…不得外传。」 | **BLOCK（拦截，不转发）**：8901/8902 delta 均 **0** | **403** | `error.code=content_blocked`；reasons=`[{code:CLASSIFICATION_MARK, detail:'命中 机密★'}, {code:CLASSIFICATION_MARK, fid:'f_0004', detail:'命中 不得外传'}]` |
| f | 无 key / 错 key（dk_00000000）/ 跨部门复用会话 | 鉴权闸 | **401/401/403** | 无 key、错 key → `401 unauthorized` 信封；民政局先绑定会话后某镇 key 复用 → `403 unauthorized`（会话属主绑定生效） |
| g | 批量：3 个合法身份证+1 手机号 | **GOVCLOUD**，仅 :8902 +1（8901 零新增） | 200 | 客户端还原完整；:8902 `/admin/text` bytes 级原身份证**零命中**、`〔身份证·` 占位符在位 |
| h | `/admin/api/audit` 审计交叉核对 | 管理面 | 401/200 | 无 key 401；部门 key 200，`total=6`，与本次 6 个审计型 chat 请求一致（BLOCK 事件 blocked=true；GOVCLOUD/INTERNET 路由分布正确；预览均为占位符版，无原值） |

**冒烟结论：全部 8 组请求行为与设计一致**——PII 出不了网（上游 bytes 级零原值）、客户端无损还原、密级直接拦截、鉴权与会话属主闸生效、AI 标识三形态在位、审计只存脱敏预览。

### 3.3 进程清理（按 PID，实测确认）

- `taskkill //F //T //PID 21580`（网关）成功；mock 的监听 PID（7396/23668 及其子进程 21968/26064）随后台任务终止/由 taskkill 收尾。
- 终态实测：`netstat -ano` 过滤 8901/8902/18731 → **无任何 LISTENING/TIME_WAIT 之外条目（SMOKE_PORTS_ALL_FREE）**；本机遗留的 3 个 python 进程经 wmic 核实为 `python -m pytest`（非本组拉起，未动）；:9004 的 ssh 隧道（`anolis-gpu-tailnet`）为既有基础设施，非本组拉起，未动。

---

## 四、过程观察与异常（如实记录）

1. **8901 首次绑定失败（重试 1 次成功）**：批量 `&` 拉起时 8901 mock 未存活，重试时报 `[Errno 10048] error while attempting to bind ... (winerror 10048)`（TIME_WAIT 残留占位）；约 1 分钟后重试成功。属测试环境端口时序问题，与被测代码无关。
2. **流式 annotations 采集差异**：冒烟客户端首跑 `finish_annotations=None`，但 t0_stream 验收 14/14 PASS 声称 annotations 在位；用帧级原始 JSON 复核确认 annotations 确实落在 finish 帧（`{"type":"ai_generated","text":"本内容由AI生成"}`）。差异是客户端采集写法（show 输出时点）问题，**产品行为正常**，已以原始帧证据为准。
3. **m11_robust 端口滞后释放**：冒烟前检查时发现 :8911/:8912/:8913/:9012/:9013 仍被 `python -m evals.m11_robust`（PID 11844）监听；该进程创建时间 20:34:47 与本组 m11 运行窗口（20:23:14–20:24:20，据 wf 日志时间戳）**不符**，来源不明（非本组 smoke 进程）；数分钟后自行退出、端口全部释放，未做干预。如实存疑记录。
4. m10_e2e 的 U8「真实大模型全链」在本环境**真实跑通**（:9004 经 ssh 隧道 `anolis-gpu-tailnet` 到 GPU 机的本地大模型服务，双腿 key 指纹不同），这解释了为何 m10_e2e 无 DEFERRED。

## 五、边界与未验证项

- `evals.u8_repro` / `evals.m8_quality`：**未运行**（需真实上游大模型 API key，本环境无）。
- `internet_real` / `govcloud_real` 上游的**直连**形态未单独验证（本环境无该 key；但其能力已由 m10_e2e U8 经 :9004 真实推理腿覆盖验证）。
- 本冒烟覆盖 chat/流式/内部端点/文件通道入口之外的主链路；webui 页面交互、admin CSV 导出等未人工逐项点验（m9/m7 验收已自动化覆盖 16+17 项）。
- OCR 召回基于 3 份合成扫描件（12 处身份证），真实扫描件泛化能力**未验证**。
- 性能数字（1.99ms/0.259ms/50 并发 27.7s 等）均为本机实测单次结果，未做多机复现。

## 六、一句话结论

**该项目「真实能做什么」：在零真实 API key 依赖下，一个可运行的政务 AI 安全网关已经真实成立**——16/16 验收模块、e2e 八用例（含真实大模型腿）、8 组独立实跑冒烟全部通过：识别（结构化号码 micro 100%、注入召回 100%、误拦 0）、可逆脱敏与流式还原（10 万插入 0 碰撞）、三路由（含密级直接拦截）、文件通道（含 OCR 扫描件打码零残留）、审计零明文（bytes 级验证）、AI 标识、鉴权与会话属主闸、畸形输入防护与 50 并发零串扰，全部有实测证据；真实大模型接入（internet_real/govcloud_real 直连与质量评估 u8_repro/m8_quality）因无 key 未验证。
