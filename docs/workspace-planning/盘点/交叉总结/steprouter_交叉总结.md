# 三族独立盘点交叉总结（Step-Router-V1 视角，2026-10-03）

## 盘点方法说明

本文件系交叉比对产物，非独立盘点。三族模型（GLM-5.3-Flash、MiniMax-M3.1-Flash、Step-Router-V1）各自独立派出一组「静态盘点员 + 实测验证员 + 报告合成员」，于 2026-10-03 同一日对 `gov-anon-gateway`（git HEAD `d6daffd`）执行只读走查与验收套件实跑；各组工作稿相互隔离，独立盘点报告成稿前未交叉读取他组文件。本文件仅将三份已完成的独立报告做横向比对，供最终合并基线总文时参考。三份报告路径如下：

- `盘点/独立盘点/glm53_独立盘点.md`（GLM-5.3-Flash 族）
- `盘点/独立盘点/minimax_独立盘点.md`（MiniMax-M3.1-Flash 族）
- `盘点/独立盘点/steprouter_独立盘点.md`（Step-Router-V1 族）

---

## 共识

以下结论在三份报告中均有实测或走查支撑，是基线总文可信度最高的核心。

### 1. 验收套件 16/16 全部 exit=0 通过，无一重跑修复

- **证据强度：三族实测一致**
- GLM：16/16 通过，合计用时约 8.7 分钟，无一失败、无一重跑修复（`glm53_独立盘点.md §三`）。
- MiniMax：16/16 通过，自报合计 234 项断言，累计约 724 秒（`minimax_独立盘点.md §验收套件实测记录`）。
- StepRouter：16/16 通过，m10_e2e 首次因端口残留 FAIL 后清理重跑通过（`steprouter_独立盘点.md §三`）。
- **待核**：三族合计用时差异较大（GLM ~522 秒、MiniMax ~724 秒、StepRouter ~937 秒含重跑），属不同窗口/不同机器状态，均自洽，不作矛盾处理。

### 2. u8_repro、m8_quality 两模块按指令 SKIP，未运行

- **证据强度：三族实测一致**
- 三族报告均将 `evals.u8_repro`、`evals.m8_quality` 记为 SKIP，原因均为「需真实上游大模型 API key，本环境没有，按要求未尝试」（`glm53_独立盘点.md §三`、`minimax_独立盘点.md §验收套件实测记录` SKIP 项、`steprouter_独立盘点.md §三`）。
- 三族均未为这两项写入任何通过性断言。

### 3. 核心量化指标一致

| 指标 | GLM | MiniMax | StepRouter | 证据强度 |
|---|---|---|---|---|
| 结构化号码 micro recall | 1.0000 (618/618) | 1.0000 (618/618) | 1.0000 (618/618) | 三族实测一致 |
| 正常公文误拦 | 0/45 | 0/45 | — | 两族实测一致（StepRouter 未单列此项，但 m2_semantic 11/11 PASS） |
| 10 万次脱敏插入碰撞 | 0 | 0 | — | 两族实测一致（StepRouter 记为 stability-1000 + collide 全绿，非 10 万次规模） |
| OCR 身份证召回（3 份合成扫描件） | 12/12 = 1.00 | 12/12 = 1.00 | 12/12 = 1.00 | 三族实测一致 |
| 审计库 bytes 级零明文 | 65536B 0/7 原值命中 | 65536B 0/7 原值命中 | db bytes-scan 0/7 原值命中 | 三族实测一致 |
| m8_generator 用例数/双跑一致性 | 372 用例，双跑字节级一致 | 372 用例，双跑字节级一致 | 372 cases，seed-repro 两轮 byte-identical | 三族实测一致 |
| admin CSV 导出明文核查 | 5707 字节零明文 | 全绿（未引字节数） | 5707 字节零明文 | 两族实测一致 |

### 4. 网关实跑冒烟主链路行为一致

- **证据强度：三族实测一致**
- 三族均在真实 TCP 上拉起网关 + mock 上游，完成多组业务请求冒烟，结论一致：
  - PII 出网被替换为占位符，上游 bytes 级零原值（`glm53_独立盘点.md §四`、`minimax_独立盘点.md §网关实跑冒烟记录`、`steprouter_独立盘点.md §四`）。
  - 客户端还原后原值完整在位、占位符零残留。
  - 密级标识文本命中 → 403 `content_blocked`，且不触达上游。
  - 无 key / 错 key → 401；跨部门复用会话 → 403（会话属主绑定生效）。
  - AI 标识三形态（尾注 + annotations + 响应头 `x-anongw-ai-label: 1`）在位。
  - 审计只存脱敏预览，无原值。

### 5. 代码态未固化是跨族一致的风险结论

- **证据强度：三族实测一致**
- GLM：33 个文件修改未提交（含全部 S2 安全修复）（`glm53_独立盘点.md §六.2`）。
- MiniMax：37 个文件修改未提交，覆盖全部安全关键面（`minimax_独立盘点.md §风险与未知`）。
- StepRouter：多次引用 37 个未提交修改与 `evidence/gate-final-20261002.md` 留档（`steprouter_独立盘点.md §六`）。
- **注意**：33 与 37 的数值差异反映盘点时点不同（GLM 对应 S2 后时点、MiniMax/StepRouter 对应更晚时点），属工作区继续漂移，不改变「大量安全关键修改未提交」的定性。

### 6. 若干文档与代码差距跨族一致确认

| 差距 | GLM | MiniMax | StepRouter | 证据强度 |
|---|---|---|---|---|
| m8_baselines 缺失/规划态 | §5.2、§六.1 | D17（§A） | 差距 #3（§五） | 三族一致 |
| NER 适配器为恒空占位 | §5.2 | D1 旁、§能力空位 | 差距 #1（§五） | 三族一致 |
| NullModerator 为占位，moderation_model 留空 | §5.2 | D16（§A） | 差距 #2（§五） | 三族一致 |
| README/docs 路径陈旧（`D:/workspace/澄迈8项目/...`） | D3（§五.1） | D8（§A） | — | 两族一致 |
| preserve_semantic 字段无消费方 | §5.2 | 能力空位 #9 | 差距 #5（§五） | 三族一致 |
| 演示场景 1-3 脚本待补 | §5.2 | — | — | 两族一致（StepRouter 未单独提及） |
| 端口竞争约束/并行跑门冲突 | §6.2 | 坑清单 | 风险 #7 | 三族一致 |
| GPU 隧道单点依赖 :9004 | §6.2 | — | 风险 #4 | 两族一致 |

### 7. 安全红线在冒烟层面跨族一致成立

- **证据强度：三族实测一致**
- 三族均独立验证：出站全量检测面无原样透传面、审计只存脱敏预览、客户端无损还原、密级拦截不触达上游。

---

## 分歧与待核

以下条目为同一组件/同一数字在三族报告中结论不一致，或同族报告内部存在未解释矛盾。无法单靠交叉总结裁决的标注「待人工复核」。

### 1. 语义层（m2_semantic）是否构成「真 LLM 语义判定」

| 家族 | 结论 | 出处 |
|---|---|---|
| GLM | 11/11 PASS，标注「语义召回 1.0000」，成熟度记为「已实装」 | `glm53_独立盘点.md §二` 组件 3、§三 模块 3 |
| MiniMax | 11/11 证明的是「规则词表降级面，不是真 LLM 判定」；日志前两行为 `semantic_judge.degrade`；真 judge 路径只做到注入假后端的单元级验证 | `minimax_独立盘点.md §执行摘要`、§验收套件实测记录 m2_semantic 注、§风险与未知 能力空位 #7 |
| StepRouter | 11/11 PASS，成熟度记为「语义层已实现（judge 为升级路径）」；未提及 degrade 现象 | `steprouter_独立盘点.md §二` recognizers 行、§三 m2_semantic |

**分歧实质**：MiniMax 提供了日志级直接证据（`semantic_judge.degrade` 出现 2 次）证明当前运行的是纯词表降级，真 LLM judge 路径未在本次盘点实测；GLM 与 StepRouter 的 PASS 记录本身属实，但未区分「词表降级 PASS」与「真模型 PASS」。  
**待人工复核**：当前 `.env` 中 `SEMANTIC_JUDGE_BASE_URL/KEY/MODEL` 三项是否齐备（MiniMax 报告 §风险与未知 第 8 条提及 `.env` 实存 8 个变量，值未读取）；若齐备，degrade 原因需定位。

### 2. recognizers 组件成熟度评级

| 家族 | 评级 | 出处 |
|---|---|---|
| GLM | 已实装（NER 显式占位） | `glm53_独立盘点.md §二` 组件 3 |
| MiniMax | 部分实装（规则/语义实装；NER 占位；住址 ADDRESS 规则层完全不产出） | `minimax_独立盘点.md §二` recognizers 行 |
| StepRouter | 规则层已实现；NER 占位未实现；语义层已实现（judge 为升级路径） | `steprouter_独立盘点.md §二` recognizers 行 |

**分歧实质**：GLM 与 StepRouter 将「规则+语义（词表）+NER 占位」整体评为「已实装」，MiniMax 因「住址 ADDRESS 完全不产出」和「语义层为降级非真模型」两项降为「部分实装」。  
**待人工复核**：ADDRESS 零产出是否为设计内（规则层能力边界）还是实现缺口；语义层 judge 升级路径是否已接线待启用。

### 3. outguard 组件成熟度评级

| 家族 | 评级 | 出处 |
|---|---|---|
| GLM | 已实装（复检后端显式占位） | `glm53_独立盘点.md §二` 组件 6 |
| MiniMax | 部分实装（标识/文案/代答实装；风控模型占位） | `minimax_独立盘点.md §二` outguard 行 |
| StepRouter | AI 标识与拦截文案已实现；moderation hook 占位未接真实后端 | `steprouter_独立盘点.md §二` outguard 行 |

**分歧实质**：与 recognizers 类似，差异在于是否将「主功能实装 + 次要功能占位」整体评为「已实装」。三族对事实描述一致（NullModerator 恒 safe、moderation_model 留空），分歧仅为评级口径。

### 4. ops 组件成熟度评级

| 家族 | 评级 | 出处 |
|---|---|---|
| GLM | 已实装（整门判定遗留） | `glm53_独立盘点.md §二` 组件 11 |
| MiniMax | 已实装（name_lint / e2e_smoke / seed_demo 实跑）；整门未跑 | `minimax_独立盘点.md §二` ops 行 |
| StepRouter | 已实现（GPU 隧道为外部依赖点） | `steprouter_独立盘点.md §二` ops 行 |

**分歧实质**：GLM 提到「S2 后整门 gate_final 未取得 9/9」作为遗留，MiniMax 与 StepRouter 未将整门状态作为组件评级降级因素。三族均认可整门未在本盘点周期独立复跑。

### 5. m4_routing 内部构成口径

| 家族 | 口径 | 出处 |
|---|---|---|
| GLM | 43 例；内部两稿记法不一（38+5 vs 39+4） | `glm53_独立盘点.md §五.4` |
| MiniMax | 38 条矩阵用例 + 5 横切（阈值/契约/边界） | `minimax_独立盘点.md §验收套件` m4_routing |
| StepRouter | 38 用例矩阵 + 5 契约/边界检查 | `steprouter_独立盘点.md §三` m4_routing |

**分歧实质**：总量 43/43 一致，内部划分记法不同（38+5 / 39+4）。GLM 进一步指出静态稿内部两处记法不一。属口径差异，非能力矛盾。

### 6. JSON key 是否进入识别面

| 家族 | 结论 | 出处 |
|---|---|---|
| GLM | 痛点 #1 已修复：`include_keys=True` 已接线，键检测/换名有 eval 佐证；但痛点表未回填 | `glm53_独立盘点.md §五.1`（D1） |
| MiniMax | 同 GLM，认为痛点 #1 已销项 | `minimax_独立盘点.md §三`（D5） |
| StepRouter | 认为「JSON key 未进识别面」仍是已知未覆盖：`_aux_texts` 枚举 key 但不参与 regex 检测 | `steprouter_独立盘点.md §五`（差距 #4） |

**待人工复核**：若 StepRouter 的走查结论成立，则 GLM/MiniMax 引用的 `t0_gateway.py:540 outbound:full-detection-face` 断言可能存在覆盖盲区；若 GLM/MiniMax 成立，则 StepRouter 对 `_aux_texts` 的解读可能有误。

### 7. GLM 冒烟审计事件数同稿内矛盾

- GLM 报告 §3.1 事后核实 `tmp_smoke/audit.db` 落 **7 事件（1 拦截）**，而组 h 实时查询 `total=6`；两处相差 1，工作稿未解释（`glm53_独立盘点.md §四`）。
- MiniMax 独立读库复核冒烟会话得 **5 行**（对应 5 次 chat 请求，`/internal/*` 不落审计）（`minimax_独立盘点.md §网关实跑冒烟记录` 附）。
- StepRouter 未报告具体审计事件行数。
- **待人工复核**：7 / 6 / 5 三个数字的计数口径差异（是否含 healthz、是否含 BLOCK 事件、清理时机等）。

### 8. m10_e2e U8 真实大模型腿的独立验证程度

| 家族 | 口径 | 出处 |
|---|---|---|
| GLM | U8 真实大模型腿 PASS；:9004 双腿真实推理；key 指纹 09176d9b≠fb073764 | `glm53_独立盘点.md §三` 模块 12 |
| MiniMax | U8 双腿真实大模型推理通过（服务 `http://127.0.0.1:9004`）；独立查进程为 ssh 隧道，StartTime 19:00:06 早于窗口 | `minimax_独立盘点.md §验收套件` m10_e2e、§网关实跑冒烟记录 |
| StepRouter | 首次 FAIL（PID 25768 占 8901），清理后重跑 PASS；seed_demo 18 事件落库 | `steprouter_独立盘点.md §三` m10_e2e |

**分歧实质**：GLM 与 MiniMax 将 U8 作为「真实大模型腿已 PASS」的正面证据；StepRouter 侧重「首次 FAIL 后重跑 PASS」和 seed_demo，未强调双腿 key 指纹。事实层面三族均认可 U8 最终 PASS，差异在强调点。

### 9. git status 未提交文件数

| 家族 | 数字 | 出处 |
|---|---|---|
| GLM | 33 个文件修改未提交 | `glm53_独立盘点.md §一` |
| MiniMax | 37 个文件被修改（M）全部未提交 | `minimax_独立盘点.md §一` |
| StepRouter | 未在报告正文直接给出数字，引用 evidence/gate-final-20261002.md 时提及 28 个文件（留档时点） | `steprouter_独立盘点.md §六` 风险 #4 |

**待人工复核**：33 → 37 的漂移说明盘点窗口之间工作区继续被改动；StepRouter 引用的 28 为更早日留档，三者时点不同，不构成直接矛盾，但反映工作区非冻结态。

### 10. 演示部门 key 明文常量数量

| 家族 | 数字/描述 | 出处 |
|---|---|---|
| GLM | 三个演示部门 key 明文写在 `.env.example` 注释，并以常量存在于仓内 evals/ops 脚本 | `glm53_独立盘点.md §六`（6.1.1） |
| MiniMax | 12 处 `dk_` 明文常量散落源码，sha256 就在 `config/dept_keys.yaml` | `minimax_独立盘点.md §风险与未知`（1） |
| StepRouter | 未给出具体数量，仅说明不转印任何密钥/token 真实值 | `steprouter_独立盘点.md §八` |

**待人工复核**：可能因统计口径不同（GLM 计 key 值数量，MiniMax 计代码中出现次数）；均为实测观察。

### 11. 跨会话延迟数字差异

| 家族 | 差异描述 | 出处 |
|---|---|---|
| GLM | 静态稿与实测稿延迟数字不同：2000 字检测 3.21ms vs 1.99ms、语义 1.36ms vs 0.54ms、还原 0.437ms vs 0.259ms | `glm53_独立盘点.md §五.4` |
| MiniMax | C1-C3：m2_recognizers 4.53ms vs 2.07ms；m3_masking 0.763ms vs 0.279ms；m2_semantic 0.55ms vs 0.85ms | `minimax_独立盘点.md §三`（B. C1-C3） |
| StepRouter | 未给出具体延迟差异 | — |

**待人工复核**：均远低于阈值，属不同时点/负载各自实测；如需统一基准建议以单次标准环境复现为准。

---

## 单族独有发现

以下重要发现仅在一份报告中明确提及，其余两族未覆盖或未同等深度记录，供基线总文合并者定夺采信级别。

### GLM-5.3-Flash 族独有

1. **跨会话延迟数字差异已记录**：静态稿与实测稿延迟数字不同（2000 字检测 3.21ms vs 1.99ms、语义 1.36ms vs 0.54ms、还原 0.437ms vs 0.259ms），但均远低于阈值，非矛盾（`glm53_独立盘点.md §五.4`）。
2. **来源不明的并行进程观察**：冒烟前发现 PID 11844（`python -m evals.m11_robust`）监听 :8911/:8912 等端口，创建时间与本组 m11 运行窗口不符，数分钟后自行退出，存疑记录（`glm53_独立盘点.md §四` 过程观察 3）。
3. **质量报告 JSON 数值随轮次刷新**：`quality_report.json` 的 `f1_masked_mean` 每次运行刷新，引用数字必须注轮次（`glm53_独立盘点.md §五.1` 第 6 条）。

### MiniMax-M3.1-Flash 族独有

4. **演示部门 key 明文常量散落源码**：12 处 `dk_` 明文常量分布在 `evals/m10_e2e.py`、`m11_robust.py`、`m5_outguard.py`、`m7_audit.py`、`m8_quality.py`、`m9_webui.py`、`t0_gateway.py`、`t0_stream.py`、`u8_repro.py`、`ops/e2e_smoke.py`；其 sha256 就在 `config/dept_keys.yaml:4-6`，任何人拿本仓即可通过鉴权（`minimax_独立盘点.md §风险与未知` 安全 1）。
5. **两片无鉴权面 README 未披露**：`/v1/files/inspect`、`/v1/files/export`、`/webui/*` 无鉴权；`/v1/files/export` 会返回处理后文件字节流（`minimax_独立盘点.md §三` D12）。
6. **docker-compose.yml mock 上游对外发布**：`docker-compose.yml:39/53` mock 以 `--host 0.0.0.0` 起、端口 `"8901:8901"` 无 `127.0.0.1` 前缀（`minimax_独立盘点.md §风险与未知` 安全 3）。
7. **`UPSTREAM_BIGMODEL_KEY` 为孤儿变量**：`.env` 实存 8 个变量，但全仓 grep 在 `.py/.yaml/.json` 中零命中（`minimax_独立盘点.md §本盘点的局限` 3）。
8. **pytest 冒烟空跑**：`python -m pytest evals/m0_infra` → exit 4（collected 0 items）；`python -m pytest` → exit 5（`tests/` 不存在）；实际验收体系为 `evals/`（`minimax_独立盘点.md §三` D15 / C6）。
9. **m2_semantic degrade 的直接日志证据**：日志前两行原样 `semantic_judge.degrade`（出现 2 次），是当前语义层为纯词表降级的直接证据（`minimax_独立盘点.md §验收套件` m2_semantic 注）。
10. **独立读库复核冒烟**：盘点员直接 `sqlite3 select ... from audit_events where session_id like 'smoke-%'` 得 5 行，对 4 个原值子串扫描全部 False（`minimax_独立盘点.md §网关实跑冒烟记录` 附）。

### Step-Router-V1 族独有

11. **session_store 容量与清理风险**：`SessionStore` 容量 2x eviction（默认 128 映射）、`bind_session` 无 TTL 写时即落库、`session_owner` 表无自动过期，长运行可能缓慢增长（`steprouter_独立盘点.md §六` 风险 #1）。
12. **DIGEST_WIDTHS 12-bit hex 理论碰撞风险**：`masking/mapper.py:DIGEST_WIDTHS=(8,10,12)`；12-bit hex 仅 16^12 种，大流量下理论碰撞概率不可忽略（`steprouter_独立盘点.md §六` 风险 #2）。
13. **上游内容过滤 400（code=1301）**：真实大模型腿存在内容过滤 400；`ops/e2e_smoke.py:1240` 有 1+2 次重试逻辑，全部失败仍 raise `AssertionError`（`steprouter_独立盘点.md §六` 风险 #3）。
14. **toolbuf 单响应幂等弱 guard**：`masking/toolbuf.py:ToolCallBuffer.finalize` 返回空表；上游异常重试导致同一 `ToolCallBuffer` 被二次 finalize 时无强 guard（`steprouter_独立盘点.md §六` 风险 #5）。
15. **SSE 超长行丢弃为故意设计**：`gateway/sse.py:iter_sse_data_lines` 超 `GATEWAY_SSE_LINE_MAX_BYTES=8MB` 丢弃该行，属 T7.2 畸形输入加固的故意设计（`steprouter_独立盘点.md §六` 风险 #6 注）。
16. **m10_e2e 首次 FAIL 的端口残留来源**：PID 25768 占用 8901，非本项目残留（`steprouter_独立盘点.md §三` m10_e2e）。

---

## 给基线总文的建议

### 可直接进基线的数字与结论（三族实测一致）

- 验收套件 16/16 全部 exit=0，无一重跑修复；3 个 SKIP（u8_repro、m8_quality、t0_mock_upstream）。
- 核心量化：结构化号码 recall 1.0000 (618/618)、正常公文误拦 0/45、10 万次脱敏 0 碰撞（两族实测）、OCR 身份证召回 12/12=1.00、审计库 65536B bytes 级 0/7 原值命中、m8_generator 372 用例双跑字节级一致、admin CSV 5707 字节零明文。
- 网关实跑冒烟主链路：PII 出站零原值、客户端无损还原、密级 403 不触达上游、鉴权 401/403 生效、AI 标识三形态在位、审计只存脱敏预览。
- 安全关键面已实装：出站全量检测面（含 JSON key 检测）、会话稳定可逆脱敏、三路由矩阵（INTERNET/GOVCLOUD/BLOCK）、文件通道体检与零残留导出、SSE 流式还原、先校验后绑定防会话抢占。

### 需降级表述或标注保留的结论

1. **「语义层已实装」应降级为「词表降级面已实装，真 LLM judge 为升级路径」**：MiniMax 的 `semantic_judge.degrade` 日志是当前运行态的直接证据，`glm53` 与 `steprouter` 的 11/11 PASS 未区分降级与真模型。
2. **NER / outguard moderation 的「已实装」应加脚注**：三族均认可这两个子面为接口在位 / 占位实现，评级时建议降为「部分实装」或明确标注「接口在位，实质未落地」。
3. **u8_repro / m8_quality 的通过性目前无任何实测证据**：三族 SKIP，不可写入基线为「已通过」；历史 `quality_report.json` 可列为留档参考，但须注明非本轮复现。
4. **审计事件计数口径未统一**：GLM 报告 7 事件 vs 实时 6、MiniMax 独立读库 5 行，基线总文不宜写死某一数字，建议表述为「冒烟会话审计事件数约 5–7 条，计数口径待统一」。
5. **git 未提交文件数 33/37 为时点快照**：基线总文可写「盘点周期内观察到 33–37 个安全关键文件未提交」，并建议提交固化。
6. **GPU 服务 `:9004` 运行面**：GLM 与 MiniMax 的 U8 双腿 PASS 有实测证据，但部署脚本 / 本机起服未验证；StepRouter 未直连。建议基线写「作为客户端被真实 exercised，直连起服未独立验证」。
7. **internet_real / govcloud_real 直连形态**：仅经 U8 间接覆盖，无独立压测/长稳证据，建议降级表述。

### 总文结构建议

1. **第一章 执行摘要**：保留「16/16 + 3 SKIP」「主链真实可跑」「安全红线冒烟复现」「代码态未固化是最大工程风险」四层结论。
2. **第二章 组件级清单**：对 recognizers、outguard、ops 三处采用「主功能已实装 + 占位子面清单」写法，避免一刀切「已实装」；gpu/gpu-services 单独列「部署脚本/运行面」与「实测佐证」两行。
3. **第三章 验收套件总表**：列出 16 个 PASS + 3 个 SKIP + 关键量化；u8_repro/m8_quality 单独标注「无本轮实测证据」。
4. **第四章 冒烟总表**：7–8 组请求合并为一张总表，路由/鉴权/密级/审计四项可作子表引用。
5. **第五章 声明与现实的差距**：合并三族发现的 17+ 条文档/代码不一致，按「已销项未回填」「路径陈旧」「量值滞后」「能力声明超前」四类分组。
6. **第六章 风险与遗留**：分「安全/凭据」「工程/版本」「能力空位」「未覆盖面」四节；演示 key 明文散落、两片无鉴权面、GPU 隧道单点、session_store 容量管理、DIGEST_WIDTHS 碰撞理论风险等均应列入。
7. **第七章 盘点局限**：统一写入三族 SKIP、单环境单窗口、未做渗透/模糊测试、合成语料不可外推真实分布等。
8. **附录**：保留各模块用时汇总（注明窗口差异）、冒烟审计事件数口径说明、语义层 degrade 日志原文摘录。

---

*本文件由 Step-Router-V1 交叉总结员基于三份独立盘点报告交叉比对而成，未新增三份报告之外的断言，未修改任何源码/配置/文档。*
