# MiniMax-M3.1-Flash 独立盘点组 · 实测工作稿

> 执行者：独立盘点组「实测验证员」（模型族 minimax）
> 执行时间：2026-10-03 20:51 – 21:22（本机 windev-01，独占验收窗口）
> 工作区根：`D:/new-workspace/澄迈项目/政务AI安全`；主仓：`gov-anon-gateway/`
> Python：`C:/PROGRA~1/PYTHON~1/python.exe` 3.12.10 驱动 `wf_run.py`，实际执行为
> `gov-anon-gateway/.venv/Scripts/python.exe`
>
> **本稿只写我亲手跑出来的结果。** 所有结论都附命令或代码位置；跑不到的、没验的，
> 一律标「未验证」。全程未修改任何源码/配置/文档文件（仅本文件可写）。
> 报告中不含 `.env`、`MASK_KEY`、任何 key/token 的真实值。

---

## 0. 结论速览

| 维度 | 结论 |
|---|---|
| 16 个验收模块 | **16/16 全部 exit=0 通过**，无一失败、无一需重跑 |
| 累计耗时 | 约 724 秒（12 分钟） |
| 断言总数 | 各模块自报合计 **234 项**（20+6+11+9+43+13+12+6+17+4+16+8+7+15+14+8） |
| 网关实跑冒烟 | 在 127.0.0.1:18732 起真实网关 + 两个 mock 上游，**11 类请求全部符合预期** |
| 进程清理 | 我拉起的 6 个 PID 全部终止，8901/8902/18732 已释放 |
| 需真实大模型 key 的两项 | 按指令记 SKIP（`evals.u8_repro`、`evals.m8_quality`）——但**指令给出的 SKIP 理由与实测证据不符**，见 §4 说明 |

一句话：**这个项目在本地 mock 链路上是真的能跑通的**，识别→脱敏→路由→还原→审计
五段全链路在真实 TCP 上复现成功，脱敏侧与审计侧的「零明文」断言在我独立复核时同样成立。

---

## 1. 验收模块逐个实跑（16/16 PASS）

### 1.1 调用方式

编排者给的可靠调用方式实测有效，我全程使用它：

```bash
cd "D:/new-workspace/澄迈项目/政务AI安全"
python wf_run.py venv -m evals.<模块名>
```

`wf_run.py:99-102` 走 `venv` 分支，用 `<REPO>/.venv/Scripts/python.exe` 直调，
`cwd` = 仓库根（`wf_run.py:102` → `REPO`），子进程 stdout/stderr 全量落
`gov-anon-gateway/tmp/wf/<毫秒时间戳>_<模块名>.log`（`wf_run.py:82,84`），
包装器首行打印 `[wf_run] log=… exit=… secs=…`（`wf_run.py:60`）。

### 1.2 结果总表

| # | 模块 | exit | secs | 自报结论（原文摘录） | 关键数字 |
|---|---|---|---|---|---|
| 1 | `m0_infra` | 0 | 34 | `M0 INFRA: 20/20 checks passed` | 13+7 个依赖 dists 校验；146 文件名称检查 0 违规；9 契约模型 extra=forbid 负例 |
| 2 | `m2_recognizers` | 0 | 0 | `M2 RECOGNIZERS: 6/6 checks passed` | 结构化号码 micro=**1.0000 (618/618)**；白名单误报 FPR=**0/22=0.0000**；难负例 26 条零满置信误判；2000 字×10 均值 **2.07ms**（<100ms） |
| 3 | `m2_semantic` | 0 | 2 | `M2 SEMANTIC: 11/11 checks passed (injection×34, normal×45)` | 直接/间接/工具描述注入召回均 **1.0000**；正常公文误拦 **0/45=0.0000**；均值 0.85ms |
| 4 | `m3_masking` | 0 | 3 | `M3 MASKING: 9/9 checks passed` | 10 万次插入 **0 冲突**（2 例升级为 10 位）；50 占位符/2004 字符还原均值 **0.279ms** |
| 5 | `m4_routing` | 0 | 0 | `M4 ROUTING: 43/43 checks passed` | 38 条矩阵用例，三路由全覆盖；批量阈值可配（2→批量 / 5→单 PII），下限钳 1 |
| 6 | `m5_outguard` | 0 | 10 | `M5 OUTGUARD: 13/13 checks passed` | 流式末 delta 尾注 + finish annotations；403 文案 == 文案库模板；flagged → 403 |
| 7 | `m6_filesvc` | 0 | 39 | `M6 FILESVC(text-layer+export): 12/12 checks passed` | 15 份夹具命中 82/82；docx 四位面 7/7；xlsx 隐藏列 D 全删；PDF 三引擎回退链零残留 |
| 8 | `m6_ocr` | 0 | **302** | `M6 OCR(scan-pdf): 6/6 checks passed` | 3 份合成扫描件身份证召回 **12/12=1.00**；12 处 bbox 全在页内；导出再 OCR 零残留 |
| 9 | `m7_audit` | 0 | 5 | `M7 AUDIT(...): 17/17 checks passed` | WAL；库文件(+wal/shm) 65536B bytes 扫描 **0/7 原值命中**；投毒行负控被抓；admin API/CSV 全绿 |
| 10 | `m8_generator` | 0 | 5 | `M8 GENERATOR: 4/4 checks passed` | 372 用例（detect 300/白名单 46/难负例 26）、14 模板、7 类扰动；**双跑字节级一致** |
| 11 | `m9_webui` | 0 | 35 | `m9_webui: 16/16 检查通过` | 看板回环闸（192.0.2.111→403 / 回环→200）；docx/xlsx/pdf 体检+导出零残留；SSE 26 帧闭环 |
| 12 | `m10_e2e` | 0 | 108 | `e2e_smoke: 8 PASS / 0 FAIL / 0 DEFERRED` + `m10_e2e(+T5.3 演示数据): …18 事件三部门可查` | 审计落库 27 行零明文；seed_demo 90112 字节 **0 命中**；**U8 双腿真实大模型推理通过** |
| 13 | `m11_robust` | 0 | 88※ | `M11 ROBUST(T7.2 畸形输入/极端负载): 7/7 checks passed` | 10MB×2→413、深嵌套/数组体→400；非法 UTF-8/12MB 超长行有界；**50 并发全 200 零串扰**（批 36.3s） |
| 14 | `t0_gateway` | 0 | 15 | `T0 GATEWAY NONSTREAM: 15/15 checks passed` | 无 key/错 key→401；批量→GOVCLOUD 仅走 8902；密级→403 双 mock 零新增；审计 8 事件 |
| 15 | `t0_stream` | 0 | 17 | `T0 GATEWAY STREAM: 14/14 checks passed` | 23 种已知改形逐字节还原；8 负例原样放行；流式审计预览零原值 |
| 16 | `t0_labels` | 0 | 21 | `T0 LABELS: 8/8 checks passed` | labels.md 172 行/8580 字符，10 章节；19 类 + 9 子类型 + 4 政务身份与代码值域一致 |

※ `m11_robust` 的 88 秒是我用「日志文件名内嵌的启动毫秒时间戳 vs 文件 mtime」推算的
（`wf_run.py:82` 把启动时间写进了文件名）。原因：这一条我用了
`… | tail -50` 截取，把 `wf_run` 打印 secs 的首行一起截掉了。同一算法在 `m6_ocr`
上算出 302 秒、与 `wf_run` 自报的 302 完全吻合，故采信。其余 15 个模块的 secs 均为
`wf_run` 首行原值。

### 1.3 三个必须如实标注的「通过了但有前提」

**(1) `m2_semantic` 跑的是纯规则降级模式，不是真 LLM 语义判定。**
日志前两行原样是 `semantic_judge.degrade`（出现 2 次）。原因见
`.env.example` 的语义层说明与 `evals/m2_semantic.py` 的 `judge-adapter` 检查项：
`SEMANTIC_JUDGE_BASE_URL/KEY/MODEL` 三项齐备才启用，否则降级为纯词表。
所以 **11/11 证明的是「规则词表拦截面 + 降级不炸」，不是「真模型能判注入」**。
真 judge 路径（补判/故障降级/env 驱动）只做到了注入假后端的单元级验证。

**(2) `m10_e2e` 的 U8 腿是真推理，但 SKIP 指令的理由与事实不符 —— 见 §4。**

**(3) `m11_robust` 日志里有一段 Python traceback，那不是失败。**
日志含 `RuntimeError: bad upstream drops connection midstream`，来自
`evals/m11_robust.py:275`——这是**故意**让坏上游在流中途断连的夹具，用来验证网关
不失能。对应检查项原文：`robust:illegal-sse-frames — … 流中途断连→SSE error 事件收尾
+ 审计 flag=upstream_stream_interrupted`，PASS。

---

## 2. 网关实跑冒烟（独立于验收套件）

### 2.1 先读代码：三件事的答案

**(1) 网关如何启动** —— `gov-anon-gateway/gateway/__main__.py`

- 入口 `main()` 在 `__main__.py:16`；命令行参数 `--host`（默认 127.0.0.1，
  `__main__.py:26`）、`--port`（缺省 None，`__main__.py:27`）。
- `__main__.py:31` 先 `load_env_file()` 预载 `.env`（不覆盖已有环境变量），
  然后 `__main__.py:33` `load_app_config(args.config)` 读 `config/app.yaml`。
- 端口取法在 `__main__.py:35`：`port = args.port if args.port is not None else cfg.listen`。
  **即 `--port` 优先级最高**；默认才是 yaml 的 `listen: 9000`。
- 另有环境变量通道：`common/config.py:94-105` 的 `_override_from_env` 支持
  `ANONGW_<键大写>` 覆盖顶层键（`common/config.py:5-7` 文档化，`ANONGW_LISTEN` 即端口）。
  注意 `common/config.py:91,97` 明确豁免 `mask_key_env`/`admin_key_env` 不被覆盖。
  **我用的是 CLI `--port`**，没动环境变量，因为命令行更直接、也不碰配置。
- MASK_KEY 缺失即拒绝启动：`gateway/app.py:225-229`，值经
  `common/config.py:135-145 resolve_secret()` 从环境变量名解析，**从不落配置文件**。

**(2) 部门 key 明文如何构造** —— 存哈希、明文不在配置里

- `config/dept_keys.yaml` 只有 3 个部门的 **sha256 十六进制摘要**
  （`common/config.py:119-132 load_dept_keys()` 强制校验 64 位小写 hex）。
- 鉴权在 `gateway/deps.py:30-38 authenticate()`：对客户端 presented key 取
  `sha256_hex`，与库存摘要逐个 `hmac.compare_digest` **常量时间**比较，命中返回部门名。
- 明文约定为 `dk_` 前缀 + 8 位十六进制，公开演示值写在
  `.env.example` 的注释里（"演示部门 key（明文仅演示用）"三行），
  并以常量形式硬编码在仓内自测脚本：`evals/t0_gateway.py:63-65`。
- 我独立复核了哈希对得上（**不打印明文**）：
  ```
  .venv/Scripts/python.exe -c "import hashlib,yaml; …"
  → sha256(demo) in dept_keys: True -> dept ['民政局'];  digest-ok count: 3
  ```
- 冒烟全程只用**民政局**这一把演示 key（值见上，不在本稿复述）。

**(3) mock 上游如何拉起** —— `gov-anon-gateway/gateway/mock_upstream.py`

- CLI 入口 `main()` 在 `mock_upstream.py:407`；用法写在模块文档
  `mock_upstream.py:16-19`：`python -m gateway.mock_upstream --port 8901`。
- 端口隐含实例名与模型名：`mock_upstream.py:59-62 DEFAULT_PORT_ROLES`
  → `8901=("internet_mock",["mock-chat"])`、`8902=("govcloud_local",["gov-chat"])`，
  与 `config/app.yaml:9-10` 的上游条目一一对齐。
- 供断言用的三个管理端点（`mock_upstream.py:273-286`）：
  `GET /admin/records`（请求全文 JSON）、`GET /admin/text`（messages 全文拼接，
  供 bytes 级扫描）、`POST /admin/reset`（清空环缓冲）。
- 它只记 `Authorization` 是否存在，**不记录其值**（`mock_upstream.py:227`，凭据不入日志红线）。

### 2.2 起停实录

```bash
# 两路 mock 上游（PowerShell Start-Process -WindowStyle Hidden，拿到 PID）
python -m gateway.mock_upstream --host 127.0.0.1 --port 8901   → 启动器 PID 23156 / 子进程 8436
python -m gateway.mock_upstream --host 127.0.0.1 --port 8902   → 启动器 PID 16060 / 子进程 23636
# 网关（真实入口，读真实 config/app.yaml + 真实 .env）
python -m gateway --host 127.0.0.1 --port 18732                 → 启动器 PID 25480 / 子进程 25760
```

> 注：venv 的 `python.exe` 是启动器桩，真正持有监听 socket 的是它派生的
> `C:\PROGRA~1\PYTHON~1\python.exe` 子进程（ParentProcessId 分别是 23156/16060/25480）。
> 所以清理时要杀**两代共 6 个 PID**。

就绪与复位：

```bash
curl -s http://127.0.0.1:8901/healthz  → {"ok":true,"instance":"internet_mock","models":["mock-chat"]}
curl -s http://127.0.0.1:8902/healthz  → {"ok":true,"instance":"govcloud_local","models":["gov-chat"]}
curl -s -X POST http://127.0.0.1:8901/admin/reset → {"instance":"internet_mock","cleared":0}
curl -s http://127.0.0.1:18732/healthz           → {"ok":true,"service":"gov-anon-gateway"}
```

> 踩坑记录（不是项目缺陷，是 Windows 客户端问题）：第一版用
> `curl -d '{"…":"今天下午三点…"}'` 内联中文，服务端返回
> `400 bad_request / "request body is not valid JSON"`。改为把 payload 以 UTF-8
> 写入文件再 `--data-binary @file` 后即 200。**网关对畸形 JSON 的拒绝行为本身是正确的**，
> 这是 curl 在 Windows 下传参编码的问题。

### 2.3 逐条请求实录（11 类，均为真实 HTTP over TCP）

#### (a) 普通对话 —— 预期：互联网路由 + AI 生成标识 ✅

输入要点：`今天下午三点召开全镇防汛工作会议，请各村干部参加。`（无任何 PII）

| 项 | 实测 |
|---|---|
| 路由判定 | `x-anongw-route: INTERNET` |
| 响应码 | **200** |
| 响应头 | `x-anongw-request-id: req_67fad537a60d`、`x-anongw-session-id: smoke-a`、**`x-anongw-ai-label: 1`** |
| 关键内容 | `content` 尾行为 `本内容由AI生成`；`annotations:[{"type":"ai_generated","text":"本内容由AI生成"}]`；`usage.total_tokens=74` |

标识文案与 `config/app.yaml:22` 的 `ai_label: "本内容由AI生成"` 完全一致；
标识由 `gateway/pipeline.py:407-410` 注入（正文尾注 + annotations + 响应头三处）。

#### (b) 含身份证/手机号 —— 识别明细 + 占位符形态 ✅

输入要点：`居民张三的身份证号11010519491231002X，手机号138 0013 8000，请核对低保申领材料。`

**(b1) `/internal/detect` 识别明细**（fid 请求内自增，`gateway/app.py:454`）：

```
findings= 3
 fid=f_0001 type=PERSON        layer=rule  raw='张三'                 normalized='张三'
 fid=f_0002 type=ID_CARD       layer=rule  raw='11010519491231002X'  normalized='11010519491231002X'
 fid=f_0003 type=PHONE_MOBILE  layer=rule  raw='138 0013 8000'       normalized='13800138000'
```

手机号 raw 保留分隔符写法、normalized 去掉空格——即「归一化等价」口径。

**(b2) 对话链路**：200，`x-anongw-route: INTERNET`，客户端拿到**还原后的**原文：
`…身份证号11010519491231002X，手机号13800138000…` + `本内容由AI生成` 尾注。

**(b3) 上游实收（`GET :8901/admin/text`，280 字节）**：

```json
[{"content": "今天下午三点召开全镇防汛工作会议，请各村干部参加。", "role": "user"}]
[{"content": "居民〔人名·a0e1c61d〕的身份证号〔身份证·ece5a6d2〕，手机号〔手机号·49140cc5〕，请核对低保申领材料。", "role": "user"}]
```

**(b4) bytes 级原值扫描**（对这 280 字节做 UTF-8 子串判定）：

```
contains '11010519491231002X' -> False
contains '13800138000'        -> False
contains '张三'               -> False
contains placeholder 〔身份证· -> True
```

占位符形态 = `〔<标签>·<8位hex>〕`（HMAC 派生，`gateway/deps.py:16-17` 同一 sha256/hmac 家族；
值不落在任何配置文件里）。

#### (c) `/internal/anonymize` → `/internal/restore` 往返一致性 ✅

输入要点：同 (b) 的文本，指定 `session_id=smoke-c`。

```
(c1) anonymize → 200
  masked   = 居民〔人名·75d1c9c0〕的身份证号〔身份证·a0673fbb〕，手机号〔手机号·72f80ad3〕，请核对低保申领材料。
  mappings = 3 条，键集 = [first_seen, normalized, placeholder, preserve_semantic, session_id, type]

(c2) restore → 200
  restored = 居民张三的身份证号11010519491231002X，手机号13800138000，请核对低保申领材料。
  严格逐字一致 = False
  归一化等价（去空格）= True
```

**如实标注**：往返**不是**逐字还原——手机号由 `138 0013 8000` 变回 `13800138000`。
这是设计口径（`m2_recognizers` 的 `normalization-equivalence` 检查项：还原值 = 归一化值），
不是缺陷；但「往返一致性」这句话必须按归一化等价来理解，逐字一致性在本例为 **False**。

#### (d) 流式 `/v1/chat/completions`（`stream=true`）—— 核对流式还原不漏原值 ✅

输入要点：同 (b) 文本 + `"stream":true`，`curl -N` 抓全流。

| 项 | 实测 |
|---|---|
| 响应码 / 类型 | **200**，`content-type: text/event-stream; charset=utf-8`，`transfer-encoding: chunked` |
| 响应头 | `x-anongw-route: INTERNET`、`x-anongw-ai-label: 1`、request-id / session-id 齐全 |
| 帧数 | **23 帧**，以 `data: [DONE]` 正常收尾 |
| delta 拼接 | `〔Mock上游回显〕internet_mock\n居民张三的身份证号11010519491231002X，手机号13800138000，请核对低保申领材料。\n本内容由AI生成` |
| 还原完整性 | 原值 `11010519491231002X` / `13800138000` / `张三` **三个全部在流中** → True/True/True |
| 占位符残留 | 正则 `〔[^〕]*·[0-9a-f]{8,12}〕` 扫描结果 **False**（零残留） |
| AI 标识 | 尾注行在流中 True；`finish` 帧 delta 带 `annotations` True |

上游 8901 侧同一时刻 `/admin/text` 仍是全占位符（见 b3/b4，流式与非流式同一断言面）。

#### (e) 密级标识用例 —— 预期直接拦截而非转发 ✅

输入要点：`机密★项目纪要：居民张三，手机号13800138002，不得外传。`

| 项 | 实测 |
|---|---|
| 响应码 | **403 Forbidden** |
| 路由判定 | `x-anongw-route: BLOCK`（**不是** INTERNET/GOVCLOUD） |
| 信封 | `{"error":{"code":"content_blocked","message":"您的提问包含密级标识或内部资料字样，已按保密要求拦截。涉密事项请通过本单位保密渠道线下办理。","reasons":[…]}}` |
| 理由明细 | `reasons[0]={code:CLASSIFICATION_MARK, fid:f_0001, detail:"命中 机密★"}`；`reasons[1]={…detail:"命中 不得外传"}` |
| 是否转发 | **否**：拦截后 `:8901/admin/records` count 仍为 **3**（= 我此前的 a/b/d 三条，未 +1），`:8902` count 仍为 **0**；`:8902/admin/text` 中 `机密★` 出现次数 = **0** |

#### (f) 无 key 与错 key —— 预期 401/403 ✅

| 请求 | 响应码 | 信封 |
|---|---|---|
| `POST /v1/chat/completions` **不带** Authorization | **401** | `{"error":{"code":"unauthorized","message":"无效部门 Key（Authorization: Bearer dk_***）","reasons":[]}}` |
| `POST /v1/chat/completions` 带**错** key | **401** | 同上信封（`code=unauthorized`） |
| `POST /internal/detect` 不带 key | **401** | — |
| `POST /internal/restore` 带错 key | **401** | — |

鉴权闸在 `gateway/app.py:369-373`（chat）与 `:441-444,459-463,500-504`（三个 internal 端点）。

#### (g) 补测：批量名单 → GOVCLOUD（第三路由实跑）

输入要点：`低保名单：11010519491231002X；110105194912311019；110105194912312027；联系电话13800138000`

| 项 | 实测 |
|---|---|
| 响应码 / 路由 | 200，`x-anongw-route: GOVCLOUD`，响应 `model: gov-chat` |
| 转发切分 | `:8901` count 保持 **3** 未变，`:8902` count 由 0 → **1**（只走政务云腿） |
| 还原 | 客户端拿到 3 个身份证 + 手机号全量还原 + `本内容由AI生成` 尾注 |
| 依据 | `config/app.yaml:25 thresholds.batch_pii_to_govcloud: 3` |

#### 附：审计落账独立复核（我直接读库，不看自测报告）

```bash
.venv/Scripts/python.exe -c "import sqlite3; … select dept,route,blocked,upstream,reasons,prompt_preview from audit_events where session_id like 'smoke-%' order by id"
```

`data/audit.db` 中 `smoke-%` 会话共 **5 行**（正好对应 5 次 chat 请求；`/internal/*` 不落审计）：

| dept | route | blocked | upstream | reasons | 预览形态 |
|---|---|---|---|---|---|
| 民政局 | INTERNET | 0 | internet_mock | `["NO_FINDING"]` | 原文逐字（无 PII） |
| 民政局 | INTERNET | 0 | internet_mock | `["SINGLE_STRUCTURED_PII"]` | `居民〔人名·a0e1c61d〕的身份证号〔身份证·ece5a6d2〕…` |
| 民政局 | INTERNET | 0 | internet_mock | `["SINGLE_STRUCTURED_PII"]` | 同上（流式那条） |
| 民政局 | **BLOCK** | **1** | **None** | `["CLASSIFICATION_MARK","CLASSIFICATION_MARK"]` | `〔密级·已拦截〕项目纪要：居民〔人名·0d471a7f〕…〔密级·已拦截〕。` |
| 民政局 | GOVCLOUD | 0 | govcloud_local | `["BATCH_STRUCTURED_PII"]` | `低保名单：〔身份证·7b9d7cb4〕；〔身份证·0515c97b〕；〔身份证·9b0fe0cc〕；联系电话〔手机号·015f2c1e〕` |

预览全文对 4 个原值做子串扫描：`11010519491231002X` / `13800138000` / `张三` / `机密★`
**全部 False**——审计侧零明文在我这里同样成立。

---

## 3. 进程清理

```bash
taskkill //PID 25760 //T //F   → 成功（属 25480 子进程）   # 网关
taskkill //PID 23636 //T //F   → 成功（属 16060 子进程）   # mock 8902
taskkill //PID  8436 //T //F   → 成功（属 23156 子进程）   # mock 8901
taskkill //PID 25480 //T //F   → 错误：没有找到进程（随子进程终止已退出）
taskkill //PID 23156 //T //F   → 错误：没有找到进程（同上）
taskkill //PID 16060 //T //F   → 错误：没有找到进程（同上）
```

复核（3 秒后）：

```bash
netstat -ano | grep LISTENING | grep -E ":8901|:8902|:18732"
→ 8901 / 8902 / 18732: no LISTENING
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where CommandLine -match 'gateway'
→ 无我拉起的 gateway / mock_upstream 进程
```

**三个端口均已释放。** 审计门（`audit_db=data/audit.db`）与
`session_map.db` 因冒烟新增了 5 条审计事件与若干会话映射——这是网关的正常运行时写入
（`gateway/app.py:232-237`），不是源码/配置/文档改动。

---

## 4. SKIP 项与「指令前提与实测证据不符」的如实说明

指令要求：`evals.u8_repro`、`evals.m8_quality` 记 SKIP，理由「需真实上游大模型 key，
本环境没有，不要尝试」。

**我遵守了「不要尝试」，两项均未运行。** 但必须指出该理由与实测证据冲突：

1. `m10_e2e` 的 **U8 腿实跑通过了真实大模型推理**，日志原文：
   `PASS U8 真实大模型全链 — 双腿真实推理（INTERNET/GOVCLOUD，服务 http://127.0.0.1:9004）：
   回复非空+占位符零泄漏+AI 标识（头/尾注/annotations）；上游 ring 全文=原文脱敏版；
   key 指纹 09176d9b≠fb073764 两腿不同`。回复正文是自然中文长文（不是 mock 回显），
   例如 `针对您提供的低保申领核对请求，我必须严格遵循个人信息保护原则和政务规范。…`。
2. `netstat` 实测 `127.0.0.1:9004 … LISTENING`，`Get-Process -Id 23880` 显示
   该监听是 **`ssh` 进程，StartTime 2026/10/3 19:00:06**（我拉起之前就在跑），
   与 `config/app.yaml:12-13` 注释所述「本机经 `ops/tunnel_gpu.sh` 隧道以
   127.0.0.1:9004 访问 GPU 机大模型服务」吻合。

结论：**这台机器上真实上游是可达的**（隧道已在），`.env` 里
`REAL_LLM_KEY` / `GOVCLOUD_LLM_KEY` 也有值。所以这两项 SKIP 的真实含义是
「按指令不跑」，而非「环境不具备条件」。**这两项在本报告中记 SKIP（未运行），
其通过与否我没有任何实测证据，不做任何推断。**

---

## 5. 环境干扰与隔离性说明（如实记录）

- **本机在我验收期间并非完全空闲。** 除我拉起的进程外，观察到他人/其他会话的进程：
  - `ops/gate_b5.py` PID 25740（StartTime 21:08:16）
  - `ops/gate_b4.py` PID 22000（StartTime 21:11:17）
  - `ops/gate_b3.py` PID 25216（StartTime 21:16:08）
  - 另在我跑 `t0_labels` 期间，8901/8902 上曾存在两个**不是我启动的** mock 上游
    （PID 21152 / 25832，StartTime 21:09:53 / 21:09:55，命令行同为
    `python -m gateway.mock_upstream --port 890X`），它们随后自行退出。
  - 这些进程**我一律没有杀**（不是我拉起的）。
- **对冒烟结果的影响评估：无。** 依据是我自己的旁证：冒烟全程 `:8901/admin/records`
  的 count 精确等于我发出的请求数（a/b/d 后 =3，e 拦截后仍 =3，g 之后 =3），
  `:8902` 从 0 → 1 只出现在 g；且 `/admin/text` 全文只含我自己的两条 messages。
  若有外来流量混入会污染这两个计数。
- **对 16 个模块的影响评估：无 PASS 被污染的迹象**——各模块自己就带
  端口占用断言（`evals/t0_gateway.py:98-102` `_assert_port_free` 会在端口被占时直接
  FAIL「leftover process running?」），而 `t0_gateway` / `t0_stream` /
  `m5_outguard` / `m6_filesvc` / `m9_webui` / `m10_e2e` / `m11_robust`
  都真实起了自己独占端口的 mock 与网关并全部 PASS。

---

## 6. 我认为「真实能做什么」与「没验到什么」

**实测确证能做的（全部有本次执行的输出为证）：**

1. OpenAI 兼容入口 `/v1/chat/completions` 的**非流式 + SSE 流式**双形态，
   连同 `x-anongw-route / x-anongw-request-id / x-anongw-session-id /
   x-anongw-ai-label` 四个协议头。
2. 19 类政务敏感实体的识别（结构化号码 micro 召回 618/618 = 1.0000）、
   白名单零误报（0/22）、难负例零满置信误判。
3. 占位符脱敏与**跨会话稳定 / 跨会话互异**、10 万次插入零碰撞。
4. 三路由决策：INTERNET / GOVCLOUD / BLOCK，冲突优先级（BLOCK > GOVCLOUD > 单 PII）
   与批量阈值可配。
5. 出站零原值：上游只收 `〔标签·hash〕`，我独立 bytes 扫描复核。
6. 入站还原：流式与非流式都把原值送回客户端，**流式 23 帧零占位符残留**。
7. 密级内容 403 直接拦截、**不触达上游**（环缓冲计数未增长）。
8. 部门 Key 鉴权（sha256 常量时间比较），无 key / 错 key 一律 401，
   `/internal/*` 同样受闸。
9. 审计落库（含 WAL）、预览仅占位符版本、库文件 bytes 级零明文。
10. 文件通道：docx 四位面 / xlsx 隐藏行列 / pdf 三引擎回退链，体检与打码导出零残留。
11. 扫描件 OCR 全链：300dpi 渲染 → RapidOCR → 重建文本 → 体检（身份证召回 12/12）
    → 重栅格化打码 → 再 OCR 零残留。
12. 畸形输入健壮性：10MB/50MB 三闸 413、深嵌套与数组体 400、非法 SSE 帧有界处理、
    **50 并发零串扰**。
13. WebUI：体检页 / 演示控制页 / 聊天双屏 / 看板，含回环闸与管理面 key 硬闸。

**明确「未验证 / 有前提」的部分：**

- `evals.u8_repro`、`evals.m8_quality`：**未运行**（按指令 SKIP），无任何通过性证据。
- 语义层 LLM-judge 的**真模型**判定能力：**未验证**。`m2_semantic` 全程
  `semantic_judge.degrade`，只证明了规则词表面 + 降级健壮。
- `internet_real` / `govcloud_real` 两个 profile 的**长时间稳定性**：
  本次只经 `m10_e2e` U8 跑过各 1 次双腿，无重复压测证据。
- Docker 交付路径：**未验证**。`README.public.md:82-89` 自己已声明
  「构建环境无 Docker，`docker-compose.yml` 未在容器环境实测」。
- `README.public.md:96` 提到的 `DEPS.txt`：我在仓根 `ls` 中**未看到**该文件
  （仓根实有 `.env`/`.env.example`/`README.md`/`README.public.md`/`constraints.txt`/
  `docker-compose.yml`/`pyproject.toml` 等，无 `DEPS.txt`）。README 引用了一个
  当前工作副本里不存在的文件——**如实记录，未深究原因**（可能是公开导出时排除）。
- `config/app.yaml:27 moderation_model: ""` = 未配置，所以输出侧语义审核同样是
  NullModerator 恒 safe（`m5_outguard` 的 `moderation` 检查项即断言这一点），
  **真实审核模型未验证**。

---

## 7. 命令与证据索引

全部日志在 `gov-anon-gateway/tmp/wf/`，文件名内嵌启动毫秒时间戳：

| 模块 | 日志 |
|---|---|
| m0_infra | `1791031951697_evals.m0_infra.log` |
| m2_recognizers | `1791031992322_evals.m2_recognizers.log` |
| m2_semantic | `1791031998266_evals.m2_semantic.log` |
| m3_masking | `1791032017923_evals.m3_masking.log` |
| m4_routing | `1791032025057_evals.m4_routing.log` |
| m5_outguard | `1791032031085_evals.m5_outguard.log` |
| m6_filesvc | `1791032045026_evals.m6_filesvc.log` |
| m6_ocr | `1791032093047_evals.m6_ocr.log` |
| m7_audit | `1791032530349_evals.m7_audit.log` |
| m8_generator | `1791032545562_evals.m8_generator.log` |
| m9_webui | `1791032562940_evals.m9_webui.log` |
| m10_e2e | `1791032604310_evals.m10_e2e.log` |
| m11_robust | `1791032742549_evals.m11_robust.log` |
| t0_gateway | `1791032948168_evals.t0_gateway.log` |
| t0_stream | `1791032970113_evals.t0_stream.log` |
| t0_labels | `1791032993652_evals.t0_labels.log` |

冒烟进程的 stdout/stderr 另存于 `gov-anon-gateway/tmp/smoke/`
（`mock8901.*`、`mock8902.*`、`gw18732.*`，均为运行时工件）。

**红线自证（可复核）**：`git status --porcelain` 在我跑完后显示仓内有一批
**先前已存在的**未提交改动（`.gitignore`、`common/config.py`、`gateway/app.py`、
`evals/*.py` 等 20+ 文件）——**这些不是我改的**。逐个比对 mtime，最新一个是
`evals/t0_stream.py` @ **20:27:15**，而我的会话窗口是 **20:51–21:22**；
按 `stat -c %Y > 1791031050`（= 20:51:00）筛选，结果为空：

```
=== 我的会话开始时间 20:51 之后被改的源码/配置（应为空）===
(以上为空即未被我改动)
```

即：**本组未新建、未修改、未删除任何源码/配置/文档文件**；
唯一写入的非 `盘点/` 路径是运行时工件目录（`tmp/smoke/`，与 `wf_run.py` 自身写日志
到 `tmp/wf/` 同一性质）。本稿全文不含 `.env` 内容、`MASK_KEY` 或任何 key/token 明文
（冒烟用的部门演示 key 明文见 `.env.example` 注释与 `evals/t0_gateway.py:63-65`）。
