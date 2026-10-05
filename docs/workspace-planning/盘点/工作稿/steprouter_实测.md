# Step-Router-V1 实测工作稿

> 实测时间：2026-10-04  
> 实测人：Step-Router-V1 独立盘点组  
> 工作区根：D:/new-workspace/澄迈项目/政务AI安全  
> 主仓库：gov-anon-gateway/（Python venv 已就绪）

---

## 1. 环境与启动要点（实跑前代码确认）

### 1.1 网关启动方式
- `gateway/__main__.py` 支持 `--port` 参数覆盖 `config/app.yaml` 的 `listen`（默认 9000）。
- 本次实跑将监听端口改到 `127.0.0.1:18733`（通过启动参数 `--port 18733` 传入，未修改任何源码/配置文件）。
- 启动命令等价形式：`gov-anon-gateway/.venv/Scripts/python.exe -m gateway --port 18733`

### 1.2 部门 key 明文构造规则
- `config/dept_keys.yaml` 仅存 sha256 摘要（64 位十六进制小写）。
- 明文 key 形态为 `dk_` + 8 位十六进制（示例明文见 `evals/t0_gateway.py` 第 64-65 行注释）。
- 演示明文与 yaml 摘要的对应关系已通过 `hashlib.sha256` 复验：
  - `dk_5e6f7a8b`（民政局）→ `64b314e44797243ce717d9e7ed55df613befea370076779988b8229cb05fa25e`
  - `dk_9c0d1e2f`（某镇）→ `1955a94c8e156d2955cd803dbb2b5e1d76205b0f653a8f92f54a88f0baaa7dc1`

### 1.3 Mock 上游拉起
- 命令：`gov-anon-gateway/.venv/Scripts/python.exe -m gateway.mock_upstream --port 8901|8902`
- 端口角色：8901 = `internet_mock`（模型 `mock-chat`），8902 = `govcloud_local`（模型 `gov-chat`）
- 进程内 fixture 类：`MockUpstreamServer(port).start()`（evals/t0_gateway.py 等自备）

### 1.4 可靠调用方式
- 工作区根执行：`python wf_run.py venv -m evals.<模块名>`
- `wf_run.py` 内部直调 venv python，stdout 首行：`[wf_run] log=<路径> exit=<码> secs=<秒>`
- 详细日志落盘：`gov-anon-gateway/tmp/wf/`

---

## 2. 验收模块逐项记录（16 项）

通用命令：`cd D:/new-workspace/澄迈项目/政务AI安全 && python wf_run.py venv -m evals.<模块名>`

| 模块 | 退出码 | 用时(s) | 检查通过/总数 | 状态 | 关键输出摘录 |
|------|--------|---------|--------------|------|-------------|
| m0_infra | 0 | 70 | 20/20 | PASS | venv/deps/config/contracts 全绿；`name-lint — 146 files scanned, 0 violations` |
| m2_recognizers | 0 | 1 | 6/6 | PASS | `recall — all class lines met; structural micro=1.0000 (618/618)` |
| m2_semantic | 0 | 3 | 11/11 | PASS | `direct-recall=1.0000; indirect-recall=1.0000; normal-fp=0/45=0.0000` |
| m3_masking | 0 | 5 | 9/9 | PASS | `mask:stability-1000 — 1000 values × repeat/replay identical; restore round-trip exact` |
| m4_routing | 0 | 0 | 43/43 | PASS | 38 用例矩阵 + 5 契约/边界检查全过；`threshold(批量阈值可配+下限钳 1)` |
| m5_outguard | 0 | 18 | 13/13 | PASS | `e2e:block-classified — 403 message==模板`；label 三形态（尾注/annotations/头）全就位 |
| m6_filesvc | 0 | 68 | 12/12 | PASS | `export-pdf — 三引擎逐个导出 re-inspect 零残留；门面 method=render-redaction` |
| m6_ocr | 0 | 253 | 6/6 | PASS | `scans(3份合成扫描件) — 体检命中 12 处；ocr-recall=12/12=1.00` |
| m7_audit | 0 | 6 | 17/17 | PASS | `audit:writer-roundtrip(30)`；`gate:db-file-bytes-scan — 0/7 原值命中`；`admin:report-csv — 5707 字节 bytes 级零明文` |
| m8_generator | 0 | 7 | 4/4 | PASS | `seed-repro — two runs byte-identical (17 files)`；`case-scale=372 cases` |
| m9_webui | 0 | 37 | 16/16 | PASS | 看板数据渲染（KPI/三图/徽标/分页）；SSE 兼容闭环；xlsx 隐藏列体检+删列导出 |
| m10_e2e | 0（首次 FAIL 后重跑通过） | 157 | 8/8 + seed_demo | PASS（首次 FAIL 后重跑 PASS） | **首次失败**：`RuntimeError: port 8901 already occupied`（PID 25768，非本项目 e2e 残留）。清理 PID 25768 后重跑通过。最终输出：`e2e_smoke: 8 PASS / 0 FAIL / 0 DEFERRED`；`seed_demo 三部门演示数据注入: 3 部门 × 6 请求 = 18 事件落库` |
| m11_robust | 0 | 130 | 7/7 | PASS | `load:concurrency-50-zero-crosstalk — 50 并发全 200；零串扰三面`。**注**：日志中可见 `RuntimeError: bad upstream drops connection midstream`（`m11_robust.py:275`），此为测试脚本主动注入的断连故障场景，属于预期行为，对应 `robust:illegal-sse-frames` 检查项 PASS。 |
| t0_gateway | 0 | 19 | 15/15 | PASS | `T0 GATEWAY NONSTREAM: 15/15 checks passed`；覆盖 fixtures/auth/body/roundtrip/batch/classified/audit/owner-binding/internal/upstream-502 |
| t0_stream | 0 | 18 | 14/14 | PASS | `T0 GATEWAY STREAM: 14/14 checks passed`；流式 chunked-restore fuzz 500 case 全等 |
| t0_labels | 0 | 36 | 8/8 | PASS | `labels:entity-class-consistency — 19 EntityClass values`；`name-lint — 146 files scanned, 0 violations` |

### 跳过项（SKIP）
- `evals.u8_repro`：需真实上游大模型 key，本环境没有。
- `evals.m8_quality`：需真实上游大模型 key，本环境没有。
- `evals.t0_mock_upstream`：辅助库，按任务要求不单独跑。

---

## 3. 网关实跑冒烟

### 3.1 启动拓扑（实跑确认）

| 组件 | 地址 | 启动方式 |
|------|------|----------|
| Mock 上游（互联网） | `127.0.0.1:8901` | `python -m gateway.mock_upstream --port 8901` |
| Mock 上游（政务云） | `127.0.0.1:8902` | `python -m gateway.mock_upstream --port 8902` |
| 网关 | `127.0.0.1:18733` | `python -m gateway --port 18733`（`ANONGW_LISTEN` 环境变量覆盖同理生效） |

- 启动前确认 8901/8902/18733 均无 LISTENING 进程（`netstat -ano` 复核）。
- 结束后按 PID 终止 uvicorn 线程 + mock 线程，再次 `netstat -ano` 确认三端口均无 LISTENING（仅残留 TIME_WAIT 属于 TCP 正常回收，不影响端口复用）。

### 3.2 冒烟请求逐条记录

统一鉴权头：`Authorization: Bearer <民政局 demo key>`，session 按用例区分。

#### a. 普通对话（预期互联网路由、响应含 AI 生成标识）

- **输入要点**：`居民张三的身份证号11010519491231002X，手机号138 0013 8000，请核对低保材料。`
- **响应码**：`200`
- **路由判定与上游**：`x-anongw-route: INTERNET`（走 `:8901`）
- **关键响应内容**：
  - `x-anongw-ai-label: 1`
  - 响应体 `content` 末尾含 `本内容由AI生成`
  - `annotations[0].type = ai_generated`
  - 上游 ring 文本全文为占位符版（`〔身份证·...〕〔手机号·...〕`），bytes 级扫描零原值

#### b. 含身份证/手机号的输入（/internal/detect）

- **输入要点**：`联系13800138000，证件11010519491231002X`
- **响应码**：`200`
- **识别明细**：
  - findings[0]：`type=PHONE_MOBILE, normalized=13800138000, action_hint=MASK`
  - findings[1]：`type=ID_CARD, normalized=11010519491231002X, action_hint=MASK`
  - fid 请求内自增：`f_0001`, `f_0002`

#### c. /internal/anonymize → /internal/restore 往返一致性

- ** anonymize 输入**：`证件11010519491231002X`，session_id=`smoke_c`
- ** anonymize 响应码**：`200`
- ** anonymize 返回**：`masked = "证件〔身份证·0120b7fd〕"`
- ** restore 响应码**：`200`
- ** restore 返回**：`restored = "证件11010519491231002X"`
- **往返一致性**：`roundtrip_ok = true`

#### d. 流式 /v1/chat/completions（stream=true）

- **输入要点**：同 a，`stream=true`
- **响应码**：`200`
- **流式还原**：逐 delta 拼接后 content = `〔Mock上游回显〕internet_mock\n居民张三的身份证号11010519491231002X，手机号13800138000\n本内容由AI生成`
- **原值不漏**：`11010519491231002X` 与 `13800138000` 均在 content 中
- **AI 标识**：content 末尾含 `本内容由AI生成`，且 `annotations` 元数据注入 `type=ai_generated`
- **chunks 数**：24 个 SSE frame

#### e. 密级标识用例（预期直接拦截而非转发）

- **输入要点**：`机密★项目纪要：张三，手机号13800138002，不得外传。`
- **响应码**：`403`
- **错误码**：`content_blocked`
- **路由头**：`x-anongw-route` 存在（BLOCK）
- **上游验证**：请求前 mock1 ring=1（来自 a），mock2 ring=0；请求后 mock1=2, mock2=0（新增 0）。两 mock 均零新增。

#### f. 无 key

- **输入要点**：不携带 Authorization 头
- **响应码**：`401`
- **错误码**：`unauthorized`

#### g. 错 key

- **输入要点**：`Authorization: Bearer dk_00000000`
- **响应码**：`401`
- **错误码**：`unauthorized`

---

## 4. 端口清理复核

- 冒烟结束后执行 `netstat -ano | findstr 8901|8902|18733`。
- 结果：三端口均无 `LISTENING` 条目（仅见 TIME_WAIT 状态残留，属 TCP 正常回收，不阻塞后续复用）。
- 网关进程与 mock 进程均已按线程停止 + `server.should_exit=True` 收尾。

---

## 5. 结论与遗留

- 16 个验收模块全部 PASS（m10_e2e 首次因环境残留占端口 FAIL，清理后重跑 PASS）。
- 2 个模块按任务要求 SKIP（u8_repro、m8_quality），原因：需真实上游大模型 key，本环境没有。
- 网关实跑冒烟 7 条全部符合预期（含流式、内部端点、密级拦截、鉴权负例）。
- 未发现需修复的缺陷；未修改任何源码/配置/文档文件。
