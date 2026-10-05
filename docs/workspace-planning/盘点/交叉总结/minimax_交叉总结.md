# 三族独立盘点交叉总结（MiniMax-M3.1-Flash 视角，2026-10-03）

> 交叉总结编制日：2026-10-04；三份被总结的独立盘点报告题头日期均为 2026-10-03。

## 盘点方法说明

本轮盘点采用「三族各自独立盘点 → 交叉比对」的两段式方法：GLM-5.3-Flash、MiniMax-M3.1-Flash、Step-Router-V1 三个模型族各自组成独立的「静态盘点员 + 实测验证员 + 报告合成员」小组，在互不知情的前提下对同一对象 `gov-anon-gateway`（git HEAD `d6daffd`，加一批未提交工作区修改）分别做「14 组件只读静态走查 + 全部 19 个 `evals.*` 验收模块实跑 + 真实进程/真实 TCP 的网关实跑冒烟 + README 与 docs 量化声明逐条核对」，三份成稿落于 `盘点/独立盘点/`。本文件是这三份成稿的**纯文档交叉比对**：编制者于 2026-10-04 通读三份报告全文，按「同一结论是否被多族独立复现」把条目分为共识、分歧、单族独有三档，并对每条标注证据强度。**本交叉总结未执行任何验收模块、未启动网关、未打开任何源码或配置文件，因此不产生任何三份报告之外的新数字或新断言**；文中出现的每一个数值、行号、路径，都是对三份报告原文的转录，行号与秒数以各报告自报值为准、未经本轮复核。凡三族无法相互印证且无法在本轮范围内裁决者，一律标「待人工复核」，不做倾向性取舍。本文件不修改任何源码/配置/文档；同目录下另一份 `steprouter_交叉总结.md` 系其他流程产物，本轮未读取，以避免交叉污染。

**证据强度标签定义**：
- **三族实测一致** = 三份报告各自实跑各自复现同一数字/行为。
- **两族实测一致** = 两个模型族各自独立实跑复现，第三族未覆盖或未给出该数字。
- **单族实测** = 只有一个族实跑得到。
- **仅静态走查** = 只有读码结论，无实跑佐证。
- **留档证据（三族未复跑）** = 三族共同引用 `evidence/gate-final-20261002.md` 等历史留档，但本轮无一复跑。

---

## 共识

以下条目为三族可相互印证的结论，构成基线总文可信度最高的核心。凡「三族实测一致」者，均已在不同时间窗、不同端口、独立进程下复现（GLM53 用 `127.0.0.1:18731`，MiniMax 用 `18732`，Step-Router 用 `18733`；见 glm53_独立盘点.md §四、minimax_独立盘点.md §网关实跑冒烟、steprouter_独立盘点.md §四）。

### C1. 验收套件：16 个模块全部 `exit=0`，0 失败 —— **三族实测一致**

这是三份报告中最硬的一条。三族在同一台机器上各自独立跑同一套 `python wf_run.py venv -m evals.<模块名>`，**16 个模块的通过项计数逐格对齐，无一格不一致**：

| 模块 | GLM-5.3-Flash | MiniMax-M3.1-Flash | Step-Router-V1 |
|---|---|---|---|
| m0_infra | 20/20（37s） | 20/20（34s） | 20/20（70s） |
| m2_recognizers | 6/6 | 6/6 | 6/6 |
| m2_semantic | 11/11 | 11/11 | 11/11 |
| m3_masking | 9/9 | 9/9 | 9/9 |
| m4_routing | 43/43 | 43/43 | 43/43 |
| m5_outguard | 13/13 | 13/13 | 13/13 |
| m6_filesvc | 12/12 | 12/12 | 12/12 |
| m6_ocr | 6/6 | 6/6 | 6/6 |
| m7_audit | 17/17 | 17/17 | 17/17 |
| m8_generator | 4/4 | 4/4 | 4/4 |
| m9_webui | 16/16 | 16/16 | 16/16 |
| m10_e2e | 8 PASS / 0 FAIL / 0 DEFERRED | 8 PASS / 0 FAIL / 0 DEFERRED | 8/8（**首次 FAIL 后重跑**，见分歧 D4） |
| m11_robust | 7 PASS / 0 FAIL | 7/7 | 7/7 |
| t0_gateway | 15/15 | 15/15 | 15/15 |
| t0_stream | 14/14 | 14/14 | 14/14 |
| t0_labels | 8/8 | 8/8 | 8/8 |

出处：glm53_独立盘点.md §三、minimax_独立盘点.md §验收套件实测记录、steprouter_独立盘点.md §三。
注：三族都用时合计口径不同（约 8.7 分钟 / 724 秒 / 逐项秒数表），见分歧 D11。

### C2. 三条安全红线的端到端复现 —— **三族实测一致**

1. **出站零原值**：普通含 PII 对话转发到 mock 上游后，上游实收全文为占位符版；GLM53 对上游 bytes 做原值扫描零命中（glm53 §四 冒烟组 b），MiniMax 另做了独立复核（对上游 280 字节正文逐个原值子串判定，身份证/手机号/人名三项均 `False`，占位符形态 `True`，minimax §冒烟 b3/b4），Step-Router 记「bytes 级扫描零原值」（steprouter §四 a）。MiniMax 的复核是三族中唯一不依赖自测报告、直接查上游原文的一次，证据强度最高。
2. **审计库零明文**：审计 SQLite（含 `-wal`/`-shm`/死信）65536 字节级扫描 **0/7 原值命中**（glm53 §三#9、minimax §验收#9、steprouter §三 逐字一致）；另有 admin 导出 CSV 5707 字节零明文（glm53 §三#9 与 steprouter §三 两族给出同一数字，minimax 只报「公式注入防护全绿」）。
3. **客户端无损还原**：出站脱敏、入站还原后会话内占位符零残留；三族冒烟均验证。

### C3. 识别与脱敏的量化指标 —— **三族实测一致**

- 结构化号码 micro recall **1.0000（618/618）**——三族同数字（glm53 §三#2、minimax §验收#2、steprouter §三）。
- 注入检测召回（直接/间接/工具描述三类）**均 1.0000**；正常公文误拦 **0/45**——三族同数字（glm53 §三#3、minimax §验收#3、steprouter §三）。**但见 C14 与单族独有 U1：这三族同数字证明的是规则/词表面，不是真 LLM 判定面。**
- 白名单误报率 **0/22**——GLM53 与 MiniMax 两族一致（glm53 §三#2、minimax §验收#2）；Step-Router 未给该数。
- 扫描件 OCR 身份证召回 **12/12 = 1.00**、重栅格化后再 OCR 零残留——三族一致（glm53 §三#8、minimax §验收#8、steprouter §三）。
- 合成测评集 **372 用例**、双跑字节级一致（seed 20260928）——三族一致（glm53 §三#10、minimax §验收#10、steprouter §三）。
- 10 万次占位符插入 **0 碰撞**（自动升位 8→10→12）——GLM53 与 MiniMax 两族实测一致（glm53 §三#4、minimax §验收#4）；Step-Router 只记「collide all green」无数字。

### C4. 路由矩阵：密级直接 BLOCK、不触达上游 —— **两族实测一致 + 一族数据自相矛盾（见分歧 D1）**

GLM53 冒烟组 e 记「8901/8902 delta 均 0」、MiniMax 冒烟 (e) 记「`:8901/admin/records` count 仍为 3（未 +1）、`:8902` count 仍为 0、`:8902/admin/text` 中 `机密★` 出现 **0** 次」（minimax §冒烟 e），两者均实测支持「BLOCK 不触达上游」。eval 层三族一致：`m4_routing` 43/43 中含 BLOCK 恒 `null upstream`（glm53 §二#5、minimax §组件表 routing、steprouter §二 routing）。**Step-Router 的观测数字与其自身文字结论相反，须人工复核后方可写入基线。**

### C5. 鉴权闸行为 —— **三族实测一致**

无 Authorization 头 → `401` 信封（`error.code=unauthorized`）；错误 key → `401`；跨部门复用他人会话 → `403`（会话属主绑定）。冒烟层：GLM53 组 f 一次测全 401/401/403（glm53 §四 f），MiniMax 冒烟 f1–f4 全 401（minimax §冒烟 f），Step-Router 冒烟 f/g 无 key 与错 key 各 401（steprouter §四 f/g）。eval 层三族一致：`t0_gateway` 15/15 含 `session:owner-binding` 与 `upstream-502`（steprouter §三逐项列出 10 类检查名，与另两族同格）。注意错误 key 的取值在 Step-Router 报告正文中以明文占位形式出现，**本文件不复述该值**。

### C6. 三处「能力是接口位不是实现」—— **三族一致**

1. **NER 人名/住址**：`recognizers/ner/adapter.py` 的 `detect` 恒返回空表；三族一致（glm53 §二#3 与 §5.2 记 `adapter.py:29-31`，minimax §组件表 recognizers，steprouter §五#1 记 `adapter.py:20-27`）。三族均确认 README.md:7 **已改口**为「NER 为适配器预留位」，不存在文档夸大。
2. **输出侧内容风控**：`outguard/moderation.py` 的 `NullModerator` 恒 `safe`，`config/app.yaml:27 moderation_model` 为空串，真实审核模型未接（glm53 §二#6、minimax §组件表 outguard、steprouter §五#2）；验收层无对应门，三族一致。
3. **`m8_baselines` 文件不存在**，多基线对比与 NER F1 验收门为规划态（glm53 §二#9、minimax §组件表 benchmark + D15、steprouter §五#3）；`docs/assets/CONTRACTS.md` 痛点 2 已如实登记（glm53 §5.2、minimax §组件表、steprouter §五#3 三族同引）。

### C7. `preserve_semantic` 字段无消费方 —— **三族一致**

字段存在于模型定义、SQLite 列与 eval 断言，但全仓无任何读取该标志改变替换行为的代码；`CONTRACTS.md:150` 已自认「形同虚设」（glm53 §5.2、minimax §风险 9、steprouter §五#5）。三族独立得出同一结论，是「已知未修复项」中最干净的一条。

### C8. 未提交修改是当前最大工程风险 —— **两族实测一致（数字有分歧，见 D3）**

GLM53 与 MiniMax 各自跑 `git status --short`，都确认**全部 S2 安全修复（`gateway/pipeline.py`、`masking/mapper.py`、`audit/store.py`、`common/config.py`、`outguard/moderation.py`、`gpu-services/llm_openai/*`）处于未提交状态**，HEAD 仍为 `d6daffd`，因此「按 git 复现」拿到的是修复前的旧代码（glm53 §二、§6.2#6；minimax §代码态、§风险 4）。MiniMax 另指出历史留档 `evidence/gate-final-20261002.md` 记的是 28 个文件，现已漂移（minimax §风险 4）。Step-Router 报告未做此项检查。**结论（未固化即高风险）进基线；具体文件数待核。**

### C9. 整门 `gate_final` 在 S2 修复后未取得 9/9 —— **三族留档证据，三族均未复跑**

GLM53 引 `evidence/gate-final-20261002.md §7.3`（S2-A 1/9 FAIL：U1 ConnectTimeout + U5 KeyError；S2-B 2/9 FAIL：`:9004` 隧道中途掉线触发 DEFERRED 政策连环）；MiniMax 引同文件 `:38-70`；Step-Router 引同文件记「gate_final#1 与 #2 均 FAIL」。三族口径一致。**三族实测均未跑整门**（glm53 §七.2、minimax §局限 2、steprouter §七.1 均自述未跑），故此结论在基线中只能表述为「历史留档记载」，不可表述为「本轮实测」。

### C10. 端口独占是真实的工程约束，并已实际造成一次验收失败 —— **三族一致（Step-Router 提供直接实测证据）**

GLM53 §6.2#10 与 MiniMax §代码面脆弱点 F7 / §环境干扰 8 都记录了端口竞争与并行进程干扰；Step-Router 则在 `m10_e2e` 上**实际踩中**（首次 `RuntimeError: port 8901 already occupied`，PID 25768，清理后重跑 PASS，steprouter §三 m10_e2e 行）。这条把「并行批次会互相污染」从走查风险升级为已发生事实。

### C11. 真实链路单点依赖 `:9004` GPU 隧道 —— **两族实测一致 + 两族一致标注脆弱**

GLM53 §6.2#8 与 Step-Router §六#4/#7 都把隧道单点列为风险，并都引 `evidence/gate-final-20261002.md` 记隧道掉线已导致整门 FAIL；MiniMax 实测确认隧道确在监听（`Get-Process` 显示监听 `127.0.0.1:9004` 的是 `ssh` 进程，StartTime 2026/10/3 19:00:06，早于其验收窗口，与 `config/app.yaml:12-13` 所述 `ops/tunnel_gpu.sh` 隧道一致，minimax §SKIP 表）。三族一致：`internet_real` / `govcloud_real` 的长稳与重复压测均未做，本轮各只跑过 1 次（glm53 §6.3#12、minimax §环境与外部未知 10）。

### C12. 未跑 / 未验证项的清单本身 —— **三族一致**

| 项 | GLM53 | MiniMax | Step-Router | 证据强度 |
|---|---|---|---|---|
| `evals.u8_repro` 未运行 | ✓ SKIP | ✓ SKIP（但对 SKIP 理由提出异议，见 D5） | ✓ SKIP | 三族一致（未运行）；**理由有分歧** |
| `evals.m8_quality` 未运行 | ✓ SKIP | ✓ SKIP（同上） | ✓ SKIP | 同上 |
| `evals.t0_mock_upstream` 未单独跑 | ✓ SKIP（辅助库） | 未单列 | ✓ SKIP（辅助库） | 三族一致 |
| `evals.m8_baselines` | 文件不存在 | 文件不存在 | 未产出 | 三族一致 |
| docker compose | 未实测（环境无 Docker） | 未实测 | 未提及 | 两族一致 |
| `gpu/` 部署脚本执行 | 未执行（无 GPU 环境） | 未执行 | 未执行 | 三族一致 |
| `:9004` 直连联通性 | 未验证 | 未验证（仅经 U8 间接） | 未验证 | 三族一致 |
| `ops/gate_final.py` 整门 | 未跑 | 未跑 | 未跑 | 三族一致 |
| `ops/export_public.py` | 未跑 | 未跑 | 未提及 | 两族一致 |
| 安全渗透测试 | 未做 | 未做（无端口扫描/越权穷举/密钥强度评估） | 未做 | 三族一致 |

### C13. 测试基础设施纪律扎实 —— **三族一致**

阈值单一来源 `evals/thresholds.py`（GLM53 §二#12、MiniMax §组件表 evals、Step-Router §二 evals 三族同引）；Pydantic `extra="forbid"` 契约模型负例断言（glm53 §三#1、minimax §验收#1、steprouter §二 common）；name-lint 标准档 146 文件 0 违规三族一致（glm53 §三#1、minimax §验收#1/#16、steprouter §二 ops / §三 t0_labels）；S2 修复的每条都有 eval 断言支撑而非仅注释（glm53 §6.2#7、minimax §风险 5、steprouter §五各条）。

### C14. `m11_robust` 日志中的 `RuntimeError` 不是失败 —— **三族一致**

MiniMax 定位到 `evals/m11_robust.py:275` 是故意的「坏上游中途断连」夹具（minimax §验收#13 备注）；Step-Router 记对应检查项 `robust:illegal-sse-frames` PASS（steprouter §三 m11_robust 行）；GLM53 §三#13 记非法 SSE 四模式有界终止且通过。基线中如引用 m11_robust 结果，必须连同这条前提一起引用。

### C15. `m4_routing` 内部构成 = 38 条矩阵 + 5 条契约/边界 = 43 —— **两族一致 + 第三族自身两稿口径不一**

MiniMax（minimax §验收#5）与 Step-Router（steprouter §二 routing、§三 m4_routing 行）**均记 38+5**；GLM53 的静态稿也记 38+5，只有其实测稿记「路由矩阵 39 例 + 纯函数 + 契约 + 阈值可配」（glm53 §5.4 表）。三份报告的总判定 43/43 PASS 完全一致，仅内部分项记法有出入，基线按 **38+5** 记。

### C16. `pyproject.toml` 的 `testpaths=["tests"]` 指向不存在的目录，`pytest` 实为空跑 —— **两族一致（走查 + 实测各一）**

GLM53 §5.1#4 走查发现 `pyproject.toml:65`（`packages.find` 含 `"tests*"`）与 `:77`（`testpaths=["tests"]`）指向不存在的 `tests/`，并判定「轻微不一致，不影响运行」；MiniMax 实跑得到 `python -m pytest evals/m0_infra` → **exit 4 / `collected 0 items`**、`python -m pytest`（无参）→ **exit 5**，并判定 README.public §2 的 pytest 冒烟命令在本仓实为空跑（minimax §C6）。两族指向同一事实，一族走查 + 一族实测。Step-Router 未覆盖。

### C17. `/v1/files/inspect` 与 `/v1/files/export` 无鉴权 —— **两族一致（均仅静态走查）**

GLM53 §6.1#4 记 `gateway/app.py:285-364` 两端点只有体积/种类闸、无 `authenticate`，且 `findings` 明细含 raw 回显，设计口径是「生产部署应置于管理面/内网」；MiniMax §D12 独立复核同一行号区间并进一步指出 **README.md:38-41 与 README.public.md:112-114 只提了 `/v1/chat/completions` 与 `/internal/*` 需部门 Key，未提这两片**，属文档层安全面缺口，同时确认 spec 侧（`specs/gateway-main-chain.md:72-73`）已如实标注并给了理由。两族各补一块拼图：代码事实 + 文档缺口。Step-Router 未提。

### C18. 演示部门 Key 明文常量在仓内、其 sha256 就在 `config/dept_keys.yaml` —— **两族一致**

GLM53 §6.1#1 记三个演示部门 key 明文写在 `.env.example:21-24` 注释中并以常量存在于仓内 evals/ops 脚本，`README.public.md:122-128`（S2 修复 #8）已声明「生产部署必须更换哈希」；MiniMax §风险 1 给出更完整的实测清单（实测 12 处 `dk_` 明文常量，分布在 `evals/m10_e2e.py`、`m11_robust.py`、`m5_outguard.py`、`m7_audit.py`、`m8_quality.py`、`m9_webui.py`、`t0_gateway.py`、`t0_stream.py`、`u8_repro.py`、`ops/e2e_smoke.py`），并把「更换 `dept_keys.yaml` 三个 sha256」列为部署阻断项。**本文件不复述任何 key 值或摘要。** Step-Router 未提该风险。

### C19. 文档相对代码已滞后一轮 —— **两族一致（两族各自独立列清单）**

GLM53 §5.1 列 6 条（含 CONTRACTS 痛点 #1 未回填、`labels.md` 流式缓冲字长、旧仓库路径、`pyproject.toml` tests、README「建设中」措辞、`quality_report.json` 数值随轮次刷新）；MiniMax §D1–D10 列 10 条（`masking-placeholder` 形态数与常量表、`canonical_placeholder` 步数、`gateway-main-chain.md` 行号偏移、`CONTRACTS.md` 痛点 #1、`manifest.md` 验收项数、门清单缺 G-B6、旧路径、出站辅助面描述不完整、`feedback.md` 引旧 README 口径、`README.public.md` 引用不存在的 `DEPS.txt`）。两族重叠项：`REGENERATE.md` 旧路径（glm53 §5.1#3 / minimax D8）、`CONTRACTS.md:148` 痛点 #1 未回填（glm53 §5.1#1 / minimax D5）。Step-Router 未系统盘点文档漂移。**注意两族对「不符处总数」的口径不同，且 MiniMax 报告内部不自洽，见 D9。**

### C20. 口径提醒：所有性能数字均为单机单次实测 —— **两族一致**

GLM53 §6.3#15 与 MiniMax §局限 7 均声明全部结论来自 windev-01 一台机器、2026-10-03 的一个时间窗，未做跨机/跨平台/跨 Python 版本复现，且三族冒烟期间均观察到非本组进程在跑（GLM53 见 PID 11844；MiniMax 见 `ops/gate_b3/b4/b5` 三个进程与两个非本组拉起的 mock 上游；Step-Router 见 PID 25768）。**基线引用任何毫秒值或并发批耗时，必须标注为「单次实测、非稳定指标」。**

---

## 分歧与待核

以下为同一组件/同一数字三族结论不一致或无法相互印证之处，共 **14 条（D1–D14）**。**本交叉总结未做事实裁决**：D2、D6、D8、D10、D11、D13、D14 七条因三族信息可自行互证而给出「可核方向」或「建议写法」，其余一律标「待人工复核」。

### D1【最高优先·安全面】密级 BLOCK 是否真的「上游零新增」——Step-Router 数据与其自身结论相反

- **GLM-5.3-Flash**：BLOCK「不转发：8901/8902 delta 均 0」（glm53_独立盘点.md §四 冒烟组 e）。
- **MiniMax-M3.1-Flash**：BLOCK「**是否转发：否**」——`:8901/admin/records` count 仍为 3（未 +1）、`:8902` count 仍为 0、`:8902/admin/text` 中 `机密★` 出现 **0** 次（minimax_独立盘点.md §冒烟 e）；并把这作为其「冒烟结果未被他人流量污染」的反证链之一。
- **Step-Router-V1**：同一行表格的「路由/处理」列写「两 mock 上游零新增请求」，但「结果」列写「**mock1 ring 由 1 变为 2**（记录本次拦截），mock2 ring 保持 0」（steprouter_独立盘点.md §四 冒烟 e）。ring 若统计到达请求数，1→2 即 +1，与 GLM53、MiniMax 的实测相反，也与其自身「零新增请求」文字矛盾。该报告未解释二者关系。
- **影响**：这是「密级内容不得外传」这条核心红线的端到端证据。基线在人工复核前**不得写「BLOCK 零触达上游」**，建议写为「BLOCK 路径在 eval 层三族一致（`m4_routing` 43/43 含 BLOCK 恒 `null upstream`）；冒烟层两族实测零触达、一族数据存疑（见 D1），待人工复核」。
- **待人工复核**。建议人工在无他人进程干扰的窗口重跑一次 BLOCK 用例，同时读 mock 上游的请求计数。

### D2 JSON Key 是否已进入检测面——一族判「已修复」，一族判「已知未覆盖」

- **GLM-5.3-Flash**：契约痛点 #1「字符串键不进检测面」**已过时**，代码已实现键检测/换名：`gateway/pipeline.py:172-192` 的 `_iter_string_leaves` 有 `include_keys` 参数、`:220/:231/:238` 三处调用均传 `include_keys=True`、`:242-257` 做键换名，S2 修复 #2 亦声明「保留，行为有 eval 佐证」（glm53_独立盘点.md §5.1#1）。
- **MiniMax-M3.1-Flash**：同一结论、同一行号区间，并补 `evals/t0_gateway.py:540 outbound:full-detection-face` 有断言（minimax_独立盘点.md §D5）。
- **Step-Router-V1**：列为「已知未覆盖」差距 #4——「`docs/assets/CONTRACTS.md` pain point 1 明确记录『JSON key 未进识别面』；`recognizers/pipeline.py` 主检测面为 message content leaves，`_aux_texts` 枚举 key 但不参与 regex 检测」（steprouter_独立盘点.md §五#4）。
- **分析（不裁决）**：Step-Router 引的是 `recognizers/pipeline.py`（识别器层），另两族引的是 `gateway/pipeline.py`（网关层出站检测面）。二者是否本就是两个不同的检测面、或 Step-Router 确有一处覆盖缺口，**三份报告的证据不足以判定**。
- **待人工复核**。安全面相关，建议人工直接读 `gateway/pipeline.py:172-257` 与 `recognizers/pipeline.py` 的 `detect_full`，确认「出站全量检测面」是否真的覆盖 dict 键位。

### D3 未提交修改的文件数：33 vs 37（留档为 28）

- **GLM-5.3-Flash**：「33 个文件修改未提交（含全部 S2 安全修复）」（glm53_独立盘点.md §代码态、§执行摘要、§6.2#6）。
- **MiniMax-M3.1-Flash**：「`git status --short` 实测 **37 个文件被修改（M）全部未提交**」，并指出留档 `evidence/gate-final-20261002.md:38-70` 记的是 28 个、现已漂移（minimax_独立盘点.md §代码态、§风险 4）。
- **Step-Router-V1**：未做此项检查。
- **判定**：三份报告的执行窗口不重叠（GLM53 20:08–20:45；MiniMax 20:51–21:22；Step-Router 未标时点仅题头日期），数字差异**可能来自测量时点不同**，但两份报告都没有列出各自的完整文件清单，无法判定。**基线不得写具体文件数**，只写「全部 S2 安全修复处于未提交状态（两族实测，数量口径不一致：33 / 37）」。
- **待人工复核**。

### D4 「16/16 一次通过」与「一次 FAIL 后重跑通过」

- **GLM-5.3-Flash**：「16/16 验收模块**一次通过**（约 8.7 分钟，**无一重跑修复**）」（glm53_独立盘点.md §执行摘要、§三合计行）。
- **MiniMax-M3.1-Flash**：m10_e2e 记「`8 PASS / 0 FAIL / 0 DEFERRED`」、108s，未记首次 FAIL（minimax_独立盘点.md §验收#12）。
- **Step-Router-V1**：`m10_e2e` 记「退出码 0（**首次 FAIL 后重跑**），157s；首次 `RuntimeError: port 8901 already occupied`（PID 25768，非本项目残留），清理后重跑 PASS」（steprouter_独立盘点.md §三、§执行摘要）。
- **可核方向（不裁决）**：三族窗口不重叠，Step-Router 观测到的 PID 25768 占用 8901 在 GLM53 报告里没有对应记录（GLM53 记录的是 PID 11844 占用 8911/8912/8913/9012/9013，端口不同）。因此「16 个模块最终全部 exit 0」是三族一致的（C1），但「一次通过、零重跑」不是。
- **基线写法**：只写「16/16 通过」；若需写重跑，须写「其中 m10_e2e 在三族中至少一族因端口残留失败一次后重跑通过，根因是并行批次争用端口（见 C10）」。

### D5 `u8_repro` / `m8_quality` 的 SKIP 理由是否成立

- **GLM-5.3-Flash**：「SKIP——需真实上游大模型 API key，本环境没有，按要求未尝试」（glm53_独立盘点.md §三 SKIP 项、§6.3#11）。
- **Step-Router-V1**：「SKIP；需真实上游大模型 key，本环境没有」（steprouter_独立盘点.md §三 u8_repro/m8_quality 行、§七.2）。
- **MiniMax-M3.1-Flash**：同意 SKIP（未运行、0 推断），但**明确指出该理由与其组实测证据冲突**：① `m10_e2e` 的 U8 腿已实跑通过真实大模型推理；② `netstat` 实测 `127.0.0.1:9004` LISTENING，`Get-Process` 显示该监听是 `ssh` 进程、StartTime 2026/10/3 19:00:06，早于验收窗口，与隧道口径一致；③ `.env` 中 `REAL_LLM_KEY` / `GOVCLOUD_LLM_KEY` 有值（值全程未读取、未记录）。故「本项 SKIP 的真实含义是『按指令不跑』，而非『环境不具备条件』」（minimax_独立盘点.md §SKIP 表、§风险 9、§结论 5）。
- **三族一致的部分**：两个模块**确实未运行、确无任何通过性证据**（C12）。**不一致的只是 SKIP 理由**。
- **基线写法**：「`u8_repro` / `m8_quality` 本轮未运行，**无任何实测证据**（三族一致）；未运行理由三族记录不一致——两族照录任务指令的『本环境无真实上游 key』，MiniMax 组以 `:9004` 在监听且 U8 已跑通真实推理为据提出异议（待人工复核实际 key 可用性）。」

### D6 本轮 `m10_e2e` 的 U8 是否真的跑通了真实大模型腿

- **GLM-5.3-Flash**：U8「**真实大模型腿 PASS**：`:9004` 双腿真实推理、key 指纹 `09176d9b` ≠ `fb073764`、回复占位符零泄漏」（glm53_独立盘点.md §三#12）。GLM53 同时如实并列了自身两稿的差异：静态稿记「本会话未起服、运行面未验证」，实测稿记 U8 PASS，判定为「互补而非矛盾」（glm53 §5.4）。
- **MiniMax-M3.1-Flash**：「U8 **双腿真实大模型推理通过**（服务 `http://127.0.0.1:9004`）」（minimax_独立盘点.md §验收#12），并在 F2 记录「残余靠 e2e U8 裁定（本次 U8 PASS，但仅 1 次双腿）」。
- **Step-Router-V1**：执行摘要写「真实大模型全链（U8/m8_quality）依赖 GPU 隧道与上游内容过滤 400 **尚未全绿**」（steprouter_独立盘点.md §一），§三 的 m10_e2e 行只记 8/8 未标 U8 腿，§五#3 引 `evidence/gate-final-20261002.md` 记「`m8_quality` 曾因 deferred 和 51!=50 失败」，§六#3 记「上游内容过滤 400（code=1301）」重试逻辑 `ops/e2e_smoke.py:1240`。
- **可核方向（不裁决）**：Step-Router 的「尚未全绿」明确指向**历史 evidence 留档**（gate_final 的 U8 DEFERRED/FAIL），而 GLM53 与 MiniMax 的「PASS」是**本轮实测**。两者可能描述不同时间点，不必然矛盾；但三份报告无法互证。
- **基线写法**：「mock 链 U1–U7 三族一致全绿；**U8 真实大模型腿由 GLM53 与 MiniMax 两族在本轮实测通过，Step-Router 未复现**，其『未全绿』结论来源为 `evidence/gate-final-20261002.md` 历史留档。真实腿本轮仅 1 次双腿、无重复压测（三族一致）。」待人工复核。

### D7 `t0_stream` 的「残缺/改形占位符形态数」：19 vs 23

- **GLM-5.3-Flash**：`t0_stream` 14/14 含「**19 种**残缺占位符形态逐字节还原」（glm53_独立盘点.md §三#15、§二#4）。
- **MiniMax-M3.1-Flash**：`t0_stream` 14/14 含「**23 种**已知改形逐字节还原、8 负例原样放行」（minimax_独立盘点.md §验收#15）。**同一模块、同一通过计数（14/14）、形态数不同。**
- **Step-Router-V1**：只记「SSE 流式还原 + fuzz 500 case 全等」，未给形态数（steprouter_独立盘点.md §三 t0_stream 行）。
- **旁证（非裁决）**：MiniMax 另在 §D1 指出文档 `specs/masking-placeholder.md:131,:249` 冻结为「11 形态 + 4 负例」，而 `evals/m3_masking.py:255-273` 实际是「15 形态 + 6 负例」；GLM53 §三#4 的 `m3_masking` 9/9 未给形态数。即：形态数在「文档冻结值 / m3_masking 实际值 / t0_stream 实际值」三处各不相同，报告之间无法对齐。
- **待人工复核**。基线在人工核对 `evals/t0_stream.py` 用例表前，**不引用形态数**，只写「`t0_stream` 14/14，含 N 种残缺/改形占位符形态的逐字节还原（N 待核）」。

### D8 冒烟覆盖量与审计事件数：三族口径不同（部分可自行互证）

**（a）冒烟请求条数**
- GLM53：健康检查 2 次 + 业务请求 **8 组（a–h）**（glm53_独立盘点.md §四）。
- MiniMax：报告标题处记「11 类请求」，同报告 §冒烟计数口径备注自注「逐小节展开为 (a)(b1)(b2)(c1)(c2)(d)(e)(f×4)(g) 共 **12 次**业务请求 + 4 次 `/healthz` + 1 次 `/admin/reset`……**两种计数口径并列存疑，未深究**」（minimax_独立盘点.md §计数口径备注）。
- Step-Router：冒烟 **7 条（a–g）**（steprouter_独立盘点.md §四）。
- **可核方向（不裁决）**：三族冒烟用例集合本就不同（GLM53 有批量 GOVCLOUD 组 g 与审计交叉核对组 h；MiniMax 有内部端点与错误 key 的细分 f1–f4；Step-Router 最简），条数不同不必然矛盾，但说明**三族冒烟不是同一套用例**。
- **基线写法**：不写「N 条请求」，改写「三族各自设计并实跑了覆盖普通对话/内部识别/脱敏还原往返/流式 SSE/密级 BLOCK/鉴权（无 key、错 key、跨部门）/批量 GOVCLOUD/审计落账等场景的冒烟（GLM53 8 组、MiniMax 约 11–12 次、Step-Router 7 条，用例集合互有增减）」。

**（b）审计事件数**
- GLM53：组 h 实时查 `/admin/api/audit` 得 `total=6`（对应本次 6 个审计型 chat 请求），但事后核实 `tmp_smoke/audit.db` 落 **7 事件（1 拦截）**，**相差 1，报告自认未解释并标「待核」**（glm53_独立盘点.md §四组 h、§待核数字注、§5.4）。
- MiniMax：直接读 `data/audit.db` 查 `smoke-%` 得 **5 行**，并解释为「正好对应 5 次 chat 请求（`/internal/*` 不落审计）」（minimax_独立盘点.md §冒烟附「盘点员直接读库复核」）。
- Step-Router：冒烟未查审计库。
- **可核方向（不裁决）**：MiniMax 的 5 次 chat 请求（a/b2/d/e/g）与 GLM53 的 6 次（a/b/c/d/e/g，c 为 `/internal/*` 往返）本就不是同一集合；GLM53 自身的 6 vs 7 才是真差异。
- **基线写法**：审计落账只写行为结论「chat 请求落审计、`/internal/*` 不落审计、BLOCK 事件 `blocked=true`、预览均为占位符版」（三族一致），**不引用事件计数**。

### D9 文档不符处数：MiniMax 报告内部不自洽（13 vs 10）

- minimax_独立盘点.md §执行摘要称「`docs/assets/` 已落后代码一轮（**13 处**不符）」；
- 同一报告 §风险 5 与 §结论 3 均称「D1–D10 共 **10** 处」/「D1–D10 全部 10 处」。
- 该差异在 MiniMax 报告内部即存在，三份报告无一可仲裁。
- **基线写法**：不引用「N 处」，改为「文档相对代码存在十余处滞后（两族各自独立列清单，条数口径不一，见 C19）」。**待人工复核**（如需精确条数，须人工逐条重数）。

### D10 GLM-5.3-Flash 报告内部的若干不自洽（记录供合并者注意）

- **组件规模数字**：§代码态记「约 2.6 万行 Python，26292 行 `wc -l` 实测」，§5.4 又把「`gpu-services` 代码行数静态稿 §2 表记 737 行 vs §3.14 记 732 行」列为待核（glm53_独立盘点.md §5.4）。
- **「一次通过」与「补记复跑」并存**：§三 合计行称「无一失败、无一重跑修复」，同表内 `m4_routing` / `m8_generator` / `m9_webui` 三行均注「补记复跑实测」（GLM53 自注为补精确用时而复跑，非为修复）。**表述不矛盾，但基线不能照抄「一次通过、零重跑」。**
- **延迟数字自认双口径**：§5.4 表把静态稿与实测稿的 2000 字检测 3.21ms / 1.99ms、语义 1.36ms / 0.54ms、还原 0.437ms / 0.259ms 并列，自判「均远低于阈值，非矛盾」（与 C20 一致）。

### D11 各族用时/性能数字互不相同（环境相关，判定为非矛盾但不可作为稳定指标）

| 指标 | GLM53 | MiniMax | Step-Router |
|---|---|---|---|
| m2_recognizers 2000 字均值 | 1.99ms（静态稿 3.21ms） | 2.07ms（静态稿 4.53ms / max 11.47ms） | 未给 |
| m2_semantic 2000 字均值 | 0.54ms（静态稿 1.36ms） | 0.85ms（静态稿 0.55ms） | 未给 |
| m3_masking 还原均值 | 0.259ms（静态稿 0.437ms） | 0.279ms（静态稿 0.763ms） | 未给 |
| m6_ocr 用时 | 202s | 302s | 253s |
| m11_robust 50 并发批耗时 | 27.7s | 36.3s | 未给 |
| 冒烟 SSE 帧数 | 28 帧 | 23 帧 | 24 帧 |
| 16 模块合计 | 约 8.7 分钟 | 约 724 秒 | 未给合计（逐项秒数表） |

**判定**：全部远低于 `evals/thresholds.py` 阈值且三族**都判通过**，属单机单次实测的环境差异（C20），**不是矛盾**。MiniMax 自注其 `m11_robust` 的 88s 是用日志文件名内嵌启动毫秒时间戳推算（因 `wf_run` 打印 secs 的首行被 `tail -50` 截掉），并以同一算法在 `m6_ocr` 上算出 302s、与 `wf_run` 自报值吻合为佐证（minimax §验收表※）。**基线一律不引用具体毫秒值/帧数，只引用「<阈值」这一通过事实。**

### D12 README 行号引用存在 1 行偏移

- GLM53 记 common 组件的 README 出处为 `README.md:21`（glm53_独立盘点.md §二#1）。
- MiniMax 记 common 为 `README.md:20`、gateway 为 `README.md:21`，并对后 12 个组件给出连续行号（minimax_独立盘点.md §组件表：20/21/22/23/24/25/26/27/28/29/30/31）。
- Step-Router 不引 README 行号。
- **判定**：属行号漂移，不影响任何结论；但**基线引用 README 行号前须人工重核**。**待人工复核**。

### D13 组件清单口径不同（是否把 `gpu/`、`gpu-services/` 计入组件表）

- GLM53 把 `gpu` 与 `gpu-services/llm_openai` 列为第 13、14 号组件，共 14 个（glm53_独立盘点.md §二）。
- MiniMax 在 `gpu` 与 `gpu-services` 两行明确标注「**不在 README 组件表内**」，`docs/assets/manifest.md` 也未列（minimax_独立盘点.md §组件表），即 README 组件表为 12 项。
- Step-Router 组件表列 14 行，含 `gpu` 与 `gpu-services`（steprouter_独立盘点.md §二）。
- **判定**：三份报告的「组件」计数口径不同（12 / 14），非事实冲突。**基线须先声明采用哪种口径**，建议按「README 组件表 12 项 + 仓内但未列入组件表的 2 个部署侧件（`gpu/`、`gpu-services/`）」写，与 MiniMax 一致且信息量最大。

### D14 脱敏往返是「逐字还原」还是「归一化等价」——两族对同一能力的描述强度不同

- **GLM-5.3-Flash**：`/internal/anonymize` → `/internal/restore` 往返「200/200；masked 含 **2 条**映射；restored 与原文**逐字全等**」（glm53_独立盘点.md §四 冒烟组 c）。另在 §二#4 把 masking 的能力记为「会话稳定可逆脱敏」、在 §执行摘要记「客户端无损还原」。
- **MiniMax-M3.1-Flash**：`/internal/restore` 返回「**严格逐字一致 = `False`**（手机号由带分隔符形式变回归一化形式），**归一化等价 = `True`**」；`/internal/anonymize` 的 `mappings` 含 3 条（minimax_独立盘点.md §冒烟 c1/c2）。该报告判为**设计口径非缺陷**（对应 `m2_recognizers` 的 `normalization-equivalence` 概念），但要求「对外表述必须按归一化等价讲」（minimax §D17）。
- **Step-Router-V1**：冒烟 c 用的输入**不含分隔符变体**（`restored=证件11010519491231002X`），因此对两种口径都成立，**不构成第三方裁决**（steprouter_独立盘点.md §四 c）。
- **证据不对称（不裁决）**：MiniMax 的表述与其读码结论互相印证——其 §组件表 masking 行明确写「**注意：往返是『归一化等价』不是『逐字还原』**」，并指出 `masking/normalize.py:52-84` 与 `mapper.py:110-135 canonical_placeholder`（含四步归一化）就是归一化的来源；GLM53 的「逐字全等」表述**未附任何代码出处**。两族的冒烟输入也不同（2 条 vs 3 条映射），故也不能排除是输入差异所致。
- **基线写法（建议）**：统一按**归一化等价**表述「客户端还原无损」，并在同一句注明「号码类经归一化后还原，非逐字还原」——这是更保守且有代码出处支撑的写法。**待人工复核**（人工用同一段含分隔符的手机号文本重跑一次 anonymize→restore 即可定案）。

---

## 单族独有发现

以下条目仅一份报告提到。标注证据强度与出处，供合并者定夺采信级别。**除 MiniMax 组外，均未获另外两族印证**——不等于错误，只等于「未经交叉验证」。

### 来自 MiniMax-M3.1-Flash 族

| # | 发现 | 证据强度 | 出处 |
|---|---|---|---|
| U1 | **`m2_semantic` 的 11/11 跑的是纯规则/词表降级面，不是真 LLM 判定**：日志前两行原样是 `semantic_judge.degrade`（出现 2 次）；`SEMANTIC_JUDGE_BASE_URL/KEY/MODEL` 三项齐备才启用真 judge。报告判定「11/11 证明的是『规则词表拦截面 + 降级不炸』，不是『真模型能判注入』」，真 judge 路径只做到注入假后端的单元级验证 | **单族实测**（读实跑日志） | minimax_独立盘点.md §三个必须随「通过」一起引用的前提(1)、§D16 |
| U2 | **语义层的验收结论需降级表述**。**Step-Router 部分呼应**（其 §二 recognizers 行写「语义层已实现（**judge 为升级路径**）」），GLM53 未提 degrade。基线把「注入召回 1.0000」与「真 LLM 语义判定」切开 | **单族实测 + 一族部分呼应** | minimax §D16；steprouter §二 |
| U3 | **地址 ADDRESS 规则层完全不产出**：实测 grep `EntityClass.ADDRESS` 在 `recognizers/rule/detect.py` 零命中。连带：`masking/normalize.py:11,:84` 对 PERSON/ADDRESS 只做半角化 + strip，**不做串级归一化**，一旦开放域 NER 接入，归一化等价面需重新设计；`Whitelist.public_title_before()` 在 NER 接入前是休眠路径 | **单族实测**（grep） | minimax_独立盘点.md §风险 7 |
| U4 | `config/person_names.txt` 实测非注释行**仅 4 条**演示名 + 前 100 姓启发式（confidence=0.5）+ 静态停用词 | **单族实测**（行数统计） | minimax_独立盘点.md §风险 7；GLM53 §5.2 从 `feedback.md R1` 独立记载「演示人名现场穿帮」风险但未给条数 |
| U5 | **`CONTRACTS.md:161` 与本仓实跑结果字面冲突**：契约写「`python -m ops.name_lint --strict` 零命中」，静态盘点员实跑 `--strict` → **exit 1、193 文件 19 处命中**，全部在 `config/`。报告判定这**符合设计**（`ops/name_lint.py:33-35` 注释：配置文件默认不扫、库名只许在 `config/`；strict 只用于导出树终检 `ops/export_public.py:315`），但「开发者照做会拿到 exit 1」 | **单族实测** | minimax_独立盘点.md §D11 |
| U6 | **文档 `masking-placeholder` 冻结值已过时**：文档记「11 形态 + 4 负例」，`evals/m3_masking.py:255-273` 实际 15 形态 + 6 负例（多出 `prefix-merged`/`prefix-ascii-colon`/`prefix-multi-segment`/`prefix-combo-noise` 四种「前缀文案并入括号内」形态）；`canonical_placeholder` 文档记「三步」实际**四步**（多出 `_strip_prefix_segments`）；冻结常量表缺 `PLACEHOLDER_PREFIX_COLONS`、`KNOWN_LABELS` | 仅静态走查 | minimax_独立盘点.md §D1/D2/D3 |
| U7 | **文档行号已漂移 28–48 行**：`specs/gateway-main-chain.md` 记 `pipeline.py:144-158/131-141/161-191/194-202`，实测 `_iter_string_leaves` 在 172、`_content_segments` 在 157、`_aux_texts` 在 195、`_apply_aux_masked` 在 242 | 仅静态走查 | minimax_独立盘点.md §D4 |
| U8 | **`manifest.md:8` 的验收项数冻结在 2026-09-29 基线**（记 t0_gateway 13/13、t0_stream 11/11、m9_webui 14/14、m7_audit 16/16），实跑为 15/14/16/17 | 仅静态走查（与实跑结果交叉印证） | minimax_独立盘点.md §D6 |
| U9 | **门清单不全**：`manifest.md:32` 写「标准库门脚本 ×6（gate_d0 + gate_b1..b5）」，实际是 7 门 + 1 终检门（含 `gate_b6`，`gate_final.py:64-77` 明确列出）；`specs/gates.md:19-26` 门项表同样无 G-B6 行 | 仅静态走查 | minimax_独立盘点.md §D7。GLM53 §二#11 记「八门脚本」（数量口径一致，但未指出文档缺项） |
| U10 | **出站辅助面文档描述不完整，会让安全评审低估覆盖面**：`specs/gateway-main-chain.md:34-42` §2.2 只列 3 类（tools / 历史 tool_calls / 非 text 多模态段），代码已扩到顶层其余全部字段 + dict 键 + 消息级非 content 字段（`pipeline.py:195-239`） | 仅静态走查 | minimax_独立盘点.md §D9 |
| U11 | **`/webui/*` 整体无鉴权**（`webui/pages.py:152 mount`），看板另有回环闸（`:202`，`_LOCAL_CLIENT_HOSTS={127.0.0.1,::1}`）；GLM53 只记了 admin key 硬闸，未覆盖此面 | 仅静态走查 | minimax_独立盘点.md §组件表 webui、§D12 |
| U12 | **docker-compose 把 mock 上游对外发布**：`docker-compose.yml:39/53` 中 mock 以 `--host 0.0.0.0` 起、端口 `"8901:8901"`（**无 `127.0.0.1` 前缀**）对外发布，而网关是 `"127.0.0.1:9000:9000"`。报告判定 mock 只回显 prompt、不含真实数据，且 compose 整体已标注未实测 | 仅静态走查 | minimax_独立盘点.md §风险 3 |
| U13 | **`.env` 有 8 个变量**（MASK_KEY / MOCK_KEY / UPSTREAM_BIGMODEL_KEY / REAL_LLM_KEY / GOVCLOUD_LLM_KEY / SEMANTIC_JUDGE_BASE_URL / SEMANTIC_JUDGE_KEY / SEMANTIC_JUDGE_MODEL），**值全程未读取未记录**；其中 **`UPSTREAM_BIGMODEL_KEY` 是孤儿变量**——全仓 grep 在 `.py/.yaml/.json` 零命中，`config/app.yaml` 的 `api_key_env` 只有另三个 | 单族走查（未读值） | minimax_独立盘点.md §局限 3 |
| U14 | **审计预览 `_safe_response_preview` 对真实大模型自由文本做规则层再脱敏**，docstring 自陈「人名等 NER 层实体规则层不可见，属 open-vocabulary 残余，由 U8 的命中宿主裁定兜底」——即 NER 恒空会在这条路径上留下残余 | 仅静态走查 | minimax_独立盘点.md §F2 |
| U15 | **冒烟隔离性有反证链**：`:8901/admin/records` 的 count 精确等于盘点员发出的请求数、`:8902` 从 0→1 只出现在 g、`:8901/admin/text` 全文只含盘点员自己的两条 messages，故可反推冒烟结果未被他人流量污染 | **单族实测** | minimax_独立盘点.md §旁证与隔离性 |
| U16 | **Windows 下 `curl -d` 内联中文导致 400 的踩坑**（`request body is not valid JSON`），改 `--data-binary @file` 即 200；报告判定**网关对畸形 JSON 的拒绝行为本身是正确的**，这是 curl 传参编码问题、非项目缺陷 | **单族实测** | minimax_独立盘点.md §踩坑 |
| U17 | **还原是「归一化等价」不是「逐字还原」**：冒烟 (c) 实测严格逐字一致 = `False`（手机号由带分隔符形式变回归一化形式），归一化等价 = `True`。报告判为设计口径非缺陷，但**对外表述必须按归一化等价讲**。**注意此项与 GLM53 §四组 c「restored 与原文逐字全等」直接矛盾，见 D14** | **单族实测** | minimax_独立盘点.md §冒烟 c2、§D17 |
| U18 | **公开导出后配置被占位符替换**：`config/app.yaml:31 pdf_engine_module`、OCR 引擎、合成语料库坐标在导出后变为 `_BY_DEPLOYER_`，未配置前 PDF 导出/OCR/夹具生成**显式失败**（`README.public.md:100-106` 已如实声明）；报告注明**该导出树本次未生成、未验证** | 仅静态走查 | minimax_独立盘点.md §风险 6 |
| U19 | **两处「诚实加分项」**：`docs/contracts/labels.md:36-44` 主动声明「GB/T 45574-2025 标准全文未逐字核对」并逐条标注「已核实（摘要）/推断/项目自定义」，且 `evals/t0_labels.py:167` 有 `labels:uncertainty-marked` 断言把这条纪律**钉进 eval**（本次 8/8 通过）；`README.public.md:82-89` 与 `docker-compose.yml:3-5` 对 docker compose 明写「⚠ 未实测声明」 | 仅静态走查（与 t0_labels 8/8 实跑呼应） | minimax_独立盘点.md §两处诚实加分项。GLM53 §三#16 亦记「不确定性标注（12 处显式标记）全过」 |
| U20 | **交付阻断项清单（5 条）**：更换 `config/dept_keys.yaml` 三个 sha256 / 提交并冻结 37 个未提交修改 / README 补写 `/v1/files/*` 与 `/webui/*` 无鉴权 / 修正 `CONTRACTS.md:161` 的 `--strict` 措辞与 `CONTRACTS.md:148` 已销项痛点 / 同步 D1–D10 | 观点（依据族内实测） | minimax_独立盘点.md §结论 3 |

### 来自 GLM-5.3-Flash 族

| # | 发现 | 证据强度 | 出处 |
|---|---|---|---|
| G1 | **会话库按设计必须存归一化原值，落盘为未加密 SQLite**（`masking/session_store.py:14-17`）——文件泄露 = 占位符全量反查。缓解=与审计库分文件 / 跨部门还原 403 / TTL 24h；**at-rest 无静态加密是残余风险** | 仅静态走查 | glm53_独立盘点.md §6.1#2 |
| G2 | **`MASK_KEY` 全零占位 + `resolve_secret` 只查存在性**：`.env.example:7` 提供全零占位，`common/config.py:140-144` 的 `resolve_secret` 只查存在性，部署者忘改不报错，占位符密钥即退化为可预测值 | 仅静态走查 | glm53_独立盘点.md §6.1#3 |
| G3 | **`/internal/*` 含还原原文**：已有部门 key + 属主绑定 + `SESSION_ID_RE` 形态闸，但 `README.md:38-41` 明示不得直接暴露公网——**依赖部署纪律** | 仅静态走查 | glm53_独立盘点.md §6.1#5 |
| G4 | **规则层固有边界被项目自认**：密级词表**仅 6 词**、人名词表**仅 4 个演示名 + 姓氏启发式 0.5 置信度**（`labels.md §9-6` 与 `feedback.md R1`「演示人名现场穿帮」）；词表外新词漏检属规则层边界 | 仅静态走查 | glm53_独立盘点.md §6.2#9。MiniMax U4 从实测侧独立得出「人名仅 4 条」，两族在此点上方向一致 |
| G5 | **`labels.md` 流式缓冲字长与代码不一致**：文档写「≤32 字符缓冲」，代码与 masking spec 均为 48（`masking/mapper.py:63-65`、`remap.py:39-41`、`REGENERATE.md:106-108`） | 仅静态走查 | glm53_独立盘点.md §5.1#2。**MiniMax 未提此条**（其报告只从实测侧确认「缓冲 ≤48 字符」为通过项） |
| G6 | **`quality_report.json` 数值随轮次刷新**：`evidence/gate-final-20261002.md:197` 记 9/9 认证运行 `f1_masked=0.9971`、S2-A 记 1.0，而在盘文件实读 `f1_masked_mean=0.9943`（`evals/m8_quality.py:93` 每次运行刷新）。属设计行为，但**引用数字必须注轮次** | 单族走查 | glm53_独立盘点.md §5.1#6 |
| G7 | **webui 页面人工交互与 admin CSV 人工点验未做**（由 m9_webui 16 项 / m7_audit 17 项自动化覆盖） | 仅静态走查 | glm53_独立盘点.md §6.3#17 |
| G8 | **e2e 离线 DEFERRED 分支本轮未验证**：两稿记录的两轮 e2e 运行 U8 均真实跑通（0 DEFERRED），「无真实上游时 U8 如实 DEFERRED」的离线分支行为三族均未验证 | 仅静态走查 | glm53_独立盘点.md §6.3#14 |
| G9 | **out/public-export/ 与 _upstream/ 未逐文件走查**（按导出产物镜像与上游来源快照对待） | 范围声明 | glm53_独立盘点.md §二 附注、§七.3 |

### 来自 Step-Router-V1 族

| # | 发现 | 证据强度 | 出处 |
|---|---|---|---|
| S1 | **`config/app.yaml` 中 `internet_real` 与 `govcloud_local_real` 共用端口 `9004`，实际指向同一 `llm_openai` 服务**；若误配会双写同一上游 | 仅静态走查 | steprouter_独立盘点.md §八 部署提示（源自其静态稿配置脆弱点，非本次实测发现） |
| S2 | **`outguard_texts` 路径硬编码相对路径，cwd 非仓库根会 404** | 仅静态走查 | steprouter_独立盘点.md §八 部署提示 |
| S3 | **`DIGEST_WIDTHS` 12-bit 理论碰撞**：`masking/mapper.py:DIGEST_WIDTHS=(8,10,12)`，12 位 hex 仅 16^12 种；报告称大流量下理论碰撞不可忽略，碰撞可能导致错误还原，「低概率高影响」，`restore_tolerant` 依赖映射表命中终审。**注：此为理论风险，GLM53 与 MiniMax 两族实测 10 万次插入 0 碰撞，本轮未复现** | 仅静态走查（理论推导） | steprouter_独立盘点.md §六#2 |
| S4 | **`session_owner` 表无自动过期 / `bind_session` 无 TTL 写时即落库**：长运行可能导致该表缓慢增长；极端情况映射淘汰后还原失败 | 仅静态走查 | steprouter_独立盘点.md §六#1。GLM53 G1 从「明文落盘」角度覆盖了同一组件的不同侧面 |
| S5 | **`toolbuf` 二次 `finalize` 无强幂等 guard**：`ToolCallBuffer.finalize` 返回空表，上游异常重试导致同一 buffer 被二次 finalize 时无强 guard（仅靠上层 SSE 管线重建） | 仅静态走查 | steprouter_独立盘点.md §六#5。**注：MiniMax F3 从「唯一无上界缓冲点、上限 1,000,000 字符、绊线式抛 `ToolArgumentsOverflowError` 而非静默截断」角度覆盖了同一文件，两族结论不冲突（一个讲有界性、一个讲幂等性）** |
| S6 | **上游内容过滤 400（code=1301）是真实链路的既有失败模式**：`ops/e2e_smoke.py:1240` 有 1+2 次重试逻辑，全部失败仍 raise `AssertionError`；`evidence/gate-final-20261002.md` 记录多次因此 FAIL | 留档证据 + 走查 | steprouter_独立盘点.md §六#3。**这是 D6 中「真实腿未全绿」的唯一具体根因线索，另两族未提** |
| S7 | `m7_audit` 含 `writer-roundtrip(30)` 检查项；`m8_generator` 的 seed-repro 为「两轮 byte-identical（**17 files**）」 | 单族实测 | steprouter_独立盘点.md §三 |
| S8 | **外部依赖清单**（含 `presidio-analyzer` 作为 bench extras / M2 baseline 对比、**非主链路**），并注 `torch==2.14.0 + transformers==4.57.6` 仅 GPU 机需要 | 仅静态走查 | steprouter_独立盘点.md §八。另两族未列依赖矩阵 |
| S9 | **报告内部日期不一致**：题头为「（2026-10-03）」，§一 执行摘要写「根据 **2026-10-04** 执行的 16 个验收模块实测」 | 记录 | steprouter_独立盘点.md §标题 vs §一。合并者排期时须知 |

---

## 给基线总文的建议

### 一、可直接进基线的数字（证据强度足够）

以下条目均为**三族实测一致**或**两族实测一致**，且为确定值而非环境相关值，建议原样进基线并标注「三族独立实测复现」：

1. 16 个验收模块的**通过项计数全表**（C1，含 `m4_routing` 43/43、`t0_gateway` 15/15、`t0_stream` 14/14、`m7_audit` 17/17、`m9_webui` 16/16、`m5_outguard` 13/13、`m6_filesvc` 12/12、`m6_ocr` 6/6、`m0_infra` 20/20、`t0_labels` 8/8 等）。
2. 结构化号码 micro recall **1.0000（618/618）**、注入召回 **1.0000**、正常公文误拦 **0/45**、白名单 FPR **0/22**（后两项两族一致）。
3. 合成测评集 **372 用例**、seed 20260928 双跑字节级一致。
4. 占位符插入 **10 万次 0 碰撞**（自动升位 8→10→12）。
5. OCR 身份证召回 **12/12 = 1.00**、重栅格化后再 OCR 零残留。
6. 审计库（含 `-wal`/`-shm`/死信）**65536 字节级扫描 0/7 原值命中**；admin CSV **5707 字节零明文**（后一项两族一致）。
7. 文档三处**能力空位**：NER 恒空、`NullModerator` 恒 safe、`evals/m8_baselines.py` 不存在（C6）。
8. `preserve_semantic` 无消费方（C7）。
9. `m11_robust` 日志 `RuntimeError` 为故意断连夹具（C14）。
10. `m4_routing` 内部构成 **38 矩阵 + 5 契约/边界**（C15）。
11. 合成 OCR 扫描件 **3 份**、docx/xlsx/pdf 夹具 **15 份 / 命中 82**（后者两族一致）。

### 二、必须降级表述或暂缓写入基线的项

| 项 | 处理 | 原因 |
|---|---|---|
| 「BLOCK 零触达上游」的**冒烟层**证据 | 降级：只写 eval 层结论，冒烟层标「两族实测、一族数据待核」 | D1 |
| JSON Key 是否已进检测面 | **暂缓写入**，标「待人工复核」；两族说已修复、一族说未覆盖 | D2 |
| 未提交修改的**具体文件数**（33 / 37 / 留档 28） | 只写「全部 S2 安全修复处于未提交状态」，不写数字 | D3 |
| 「16/16 一次通过、零重跑」 | 改为「16/16 通过；其中 `m10_e2e` 在至少一族因端口残留失败一次后重跑通过」 | D4 |
| `u8_repro` / `m8_quality` 的**未运行理由** | 只写「本轮未运行，无任何实测证据」；理由三族记录不一致，注明存在异议 | D5 |
| U8 真实大模型腿 | 写「两族本轮实测通过、一族未复现，历史留档记 gate_final 未全绿」 | D6 |
| 占位符形态数（19 / 23 / 文档 11 / m3 15） | **不引用具体形态数** | D7 |
| 冒烟请求条数、审计事件数 | 不引用数字，只写行为结论与场景清单 | D8 |
| 文档不符处数（13 / 10） | 写「十余处」，不写精确条数 | D9 |
| **所有毫秒值、并发批耗时、SSE 帧数、各族合计秒数** | 只写「< 阈值」这一通过事实，**一个具体性能数字都不进基线** | D11、C20 |
| README / specs 的**行号引用** | 全部人工重核后再引（D12 已发现 1 行偏移） | D12 |
| 「组件数 14」 | 改为「README 组件表 12 项 + 仓内未列入组件表的 2 个部署侧件」 | D13 |
| 「客户端**逐字**无损还原」的表述 | 改为「客户端还原无损（**归一化等价**：号码类经归一化后还原，非逐字还原）」 | D14 |

### 三、必须与「通过」一起引用的前提（漏掉即构成夸大）

1. **`m2_semantic` 的 11/11 是规则/词表降级面，不是真 LLM 判定**（MiniMax U1 实测 `semantic_judge.degrade` 日志；Step-Router §二 亦称 judge 为升级路径）。基线引用「注入召回 1.0000」时必须带这句。
2. **NER 与输出侧内容风控是接口位不是实现**（C6，三族一致）。
3. **`m11_robust` 日志里的 `RuntimeError` 不是失败**（C14）。
4. **`m8_generator` 会重写 `data/`**（`data/` 已被 `.gitignore` 覆盖、实测 `git check-ignore` 命中），属运行时工件非源码改动（minimax §前提 3）。
5. **所有召回率/准确率均来自合成或自生成样本，不能外推为真实分布下的召回与误报**（glm53 §6.3、minimax §局限 5 口径一致）。
6. **OCR 召回仅基于 3 份合成扫描件，真实扫描件未测**（glm53 §6.3#13、minimax §局限 4）。
7. **性能数字为单机单次实测，未多机复现**（C20）。

### 四、建议的基线总文结构

建议按「**结论 → 可信证据 → 已知空位 → 文档债务 → 交付阻断项 → 未覆盖面 → 方法论与局限**」七段组织，对应如下取舍：

1. **结论段（1 段）**：只写「主链真实可跑 + 验收纪律扎实 + 两处接口位 + 最大风险在版本与文档固化」四句，不掺任何未裁决数字。
2. **可信证据段**：放 C1 全表 + C2 三条红线 + C3 量化指标；每表加一列「三族独立复现 ✓」以体现可信度来源。
3. **已知空位段**：C6 三项 + C7 `preserve_semantic`，措辞用「接口在位、实质未落地」而非「缺陷」。
4. **文档债务段**：C19，用「两族各自独立列清单」的表述，并明确区分**两类方向相反的文档滞后**——一类是**高估风险面**（`CONTRACTS.md:148` 痛点 #1 未销项，见 D2，取决于人工裁决结果）、一类是**低估风险面**（出站辅助面描述不完整，minimax D9）。**这两类必须分开写，否则读者会得到相反的印象。**
5. **交付阻断项段**：合并 GLM53 §6.2#6（未提交）、C9（整门未 9/9）、C17/C18（无鉴权面 + 演示凭据）、U5（`--strict` 措辞）、D2（待核项）五条，并按「可立即做 / 需人工裁决 / 需外部条件」三档排。
6. **未覆盖面段**：C12 全表 + U3（ADDRESS 零产出）+ G4（词表仅 6 词/4 名）+ G1（会话库未加密）+ G2（全零 MASK_KEY 占位）+ G7（人工点验未做）+ G8（离线 DEFERRED 分支未验）。**每条须标「哪一族发现」**，便于后续复核分工。
7. **方法论与局限段**：如实写明三族共有的局限（同一台机、同一日、窗口不重叠、互有并行进程干扰、C20）、各族报告自身的局限（GLM53 两稿合成、Step-Router 未查审计库/未做 git status、MiniMax 合成本人未执行任何命令），以及**本交叉总结未做任何实测**这一事实。

### 五、合并时必须人工裁决的清单（按优先级）

1. **D1** —— BLOCK 是否真的不触达上游（安全红线，Step-Router 数据矛盾）。重跑一次 BLOCK 用例并读 mock 请求计数。
2. **D2** —— JSON Key 是否已进检测面（安全面，Step-Router 与另两族结论相反）。人工读 `gateway/pipeline.py:172-257` 与 `recognizers/pipeline.py`。
3. **D5 / D6** —— 真实上游 key 到底可用与否、U8 本轮是否跑通。需人工确认 `.env` 中 `REAL_LLM_KEY` / `GOVCLOUD_LLM_KEY` 是否可连（**核对时不得打印 key 值**），并据此决定 `u8_repro` / `m8_quality` 是否补跑。
4. **D3** —— 未提交文件数到底是 33 还是 37（跑一次 `git status --short | wc -l` 即可，须在无并行会话时跑）。
5. **D7** —— `t0_stream` / `m3_masking` 的占位符形态数真值（读 `evals/t0_stream.py` 与 `evals/m3_masking.py:255-273` 用例表）。
6. **D8(b)** —— GLM53 报告自认的审计事件数 6 vs 7 差异。
7. **D9** —— 文档不符处的精确条数。
8. **D12** —— README 行号偏移 1 行（顺带重核全部 spec 行号引用）。
9. **D14** —— 脱敏往返是「逐字还原」还是「归一化等价」（用一段含分隔符的手机号文本重跑一次 anonymize→restore 即可定案；此项决定基线能否写「无损还原」）。

### 六、合并者须知的三条「不要照抄」清单

- **不要照抄任何一族的具体性能数字**（毫秒、秒数、帧数）——三族互不相同且均为单机单次实测（D11）。
- **不要照抄「一次通过、零重跑」**——Step-Router 有一次实测失败记录（D4）。
- **不要照抄任何一族的组件计数**（12 / 14 口径不同）——先声明口径再写（D13）。

---

## 本交叉总结自身的局限

1. **未执行任何检查。** 本文件是纯文档比对：编制过程中只读取了 `盘点/独立盘点/glm53_独立盘点.md`、`minimax_独立盘点.md`、`steprouter_独立盘点.md` 三份报告全文，**没有运行任何 eval 模块、没有启动网关或 mock 上游、没有打开 `gov-anon-gateway/` 下的任何源码、配置或文档**。因此**本文件不能证明任何一条技术结论为真**，只能证明「三份报告对同一件事说了什么、是否互相印证」。
2. **所有行号与数字均为转录，未经复核。** 三份报告都自述行号可能漂移（GLM53 §七.7「文中行号为静态稿实读时点」、MiniMax §局限 1「文件:行号引用未由合成本人复核」、Step-Router §七.5「结论仅代表本组视角」）。**基线引用前必须人工重核行号。**
3. **未读取同目录另一份交叉总结。** `盘点/交叉总结/steprouter_交叉总结.md` 系其他流程产物，本轮刻意未读，以避免把第四个信息源混入三族比对。**本文件与该文件可能存在结论差异，需由合并者统一裁决。**
4. **未做裁决，只做标注。** 除 D2、D6、D8、D10、D11、D13、D14 七条因三族信息可自行互证而给出「可核方向」或「建议写法」外，其余分歧一律标「待人工复核」，不做倾向性取舍。
5. **本文件不含任何密钥值。** 引用到 `dk_` 前缀演示 Key、key 指纹、MASK_KEY 占位等处，只写「位置」与「机制」，不复述任何值。

---

*本文件由 MiniMax-M3.1-Flash 交叉总结员编制（2026-10-04），仅依据三份独立盘点报告全文。全程未修改任何源码/配置/文档文件；仅写入 `盘点/交叉总结/minimax_交叉总结.md`。未新增三份报告之外的任何断言；凡三族无法互证者一律标「待人工复核」。*
