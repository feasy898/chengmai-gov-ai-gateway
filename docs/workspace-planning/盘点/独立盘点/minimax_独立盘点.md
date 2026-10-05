# MiniMax-M3.1-Flash 独立盘点报告（2026-10-03）

> **盘点组**：独立盘点组 · MiniMax-M3.1-Flash 族（静态盘点员 + 实测验证员 + 报告合成员）
> **对象**：`D:/new-workspace/澄迈项目/政务AI安全/gov-anon-gateway/`（下称「主仓」，路径均相对主仓根）
> **代码态**：`git log -1` = `d6daffd chore: import chenmai-gov-ai-gateway from feasy898/agentic-factory-projects@main (2026-10-01 snapshot)`；`git status --short` 实测 **37 个文件被修改（M）全部未提交**。本报告对应「HEAD + 未提交工作区」，**不是可按 git 复现的单一快照**。
> **执行环境**：本机 windev-01，Windows Server 2022；实际执行解释器 `gov-anon-gateway/.venv/Scripts/python.exe`（Python 3.12.10），经工作流包装器 `wf_run.py` 调用（`wf_run.py:99-102` 走 `venv` 分支，`cwd` = 仓库根，日志落 `gov-anon-gateway/tmp/wf/<毫秒时间戳>_<slug>.log`，`wf_run.py:82,84`）。

## 关于本报告的证据口径（请先读）

1. **本报告是合成稿，报告合成本人未执行任何命令、未打开任何源码文件。** 全部执行证据来自同组两份工作稿的实测记录：
   - `盘点/工作稿/minimax_静态.md`（静态只读走查，§1.1 列其亲自跑过的 9 条命令）
   - `盘点/工作稿/minimax_实测.md`（20:51–21:22 独占验收窗口，§1.2 列 16 个模块实跑、§2 记网关实跑冒烟）
   文中每条「文件:行号」均按工作稿原文转录，**合成本人未逐行复核行号**；行号若已漂移，以代码为准。
2. **未跑的一律标「未验证」**；失败与缺失如实记录，未为任何「通过」修改过源码/配置/文档。
3. **红线自证**（转述自 `minimax_实测.md` §7）：本组会话窗口为 20:51–21:22，按 `stat -c %Y > 1791031050` 筛选「窗口内被改动的源码/配置」结果为**空**；非 `盘点/` 路径的唯一写入是运行时工件目录 `tmp/smoke/`。仓内现存的一批未提交改动**在本组之前就已存在**（最新 mtime 为 `evals/t0_stream.py` @ 20:27:15，早于会话窗口）。
4. **本报告不含** `.env` 内容、`MASK_KEY`、任何 key/token 明文。涉及凭据处只写「文件位置」与「sha256 摘要机制」。
5. 盘点员全程未读取 `盘点/独立盘点/` 与 `盘点/交叉总结/` 下其他组的任何文件，也未读取 `盘点/工作稿/` 下非 `minimax_` 前缀的工作稿。

---

## 执行摘要

这是一个**工程完成度高、契约与验收纪律扎实**的政务 AI 安全网关：OpenAI 兼容入口，主链「识别 → 脱敏 → 路由 → 输出防护 → 审计」逐层实装，16 个验收模块在 2026-10-03 20:51–21:22 的独立窗口内**全部 exit=0 通过**（自报合计 234 项断言，累计约 724 秒），另在 127.0.0.1:18732 拉起真实网关 + 两个 mock 上游完成了 11 类请求的实跑冒烟。真实能做的事包括：19 类政务敏感实体识别（结构化号码 micro 召回 **618/618 = 1.0000**、白名单误报 **0/22**）、占位符脱敏（10 万次插入零碰撞、跨会话稳定/互异）、三路由决策（INTERNET / GOVCLOUD / BLOCK，密级直接 403 且**不触达上游**）、出站 bytes 级零原值、流式 23 帧零占位符残留还原、审计库（含 WAL）零明文、docx/xlsx/pdf/扫描件 OCR 四条文件通道零残留导出。

但必须同时说清三件事：①**两处「能力」是接口位不是实现**——NER 适配器 `recognizers/ner/adapter.py:29-31` 恒返回 `[]`（人名仅靠 4 条演示名词表 + 前 100 姓启发式，住址规则层完全不产出），输出侧内容风控 `outguard/moderation.py:48-55` `NullModerator` 恒 safe 且 `config/app.yaml:27 moderation_model: ""`；②**`m2_semantic` 的 11/11 证明的是词表降级面，不是真 LLM 判定**——全程日志带 `semantic_judge.degrade`，真 judge 路径只做到注入假后端的单元级验证；③**当前最大工程风险不在代码而在版本与文档**——37 个未提交修改覆盖了全部安全关键面（`gateway/pipeline.py`、`masking/mapper.py`、`common/config.py` 等），任何「按 git 复现」拿到的都是 HEAD 的旧代码，且 `docs/assets/` 已落后代码一轮（13 处不符），而项目内又把它定位为「spec+eval 驱动」的唯一权威（`README.md:43`）。

---

## 组件级清单与结论

成熟度口径（沿用静态稿 §2）：**已实装** = 声明能力在代码中有实现且有 eval 断言支撑；**部分实装** = 主干实装但存在规划态子面/占位实现；**占位/未落地** = 接口在位、恒空或恒降级。

| 组件 | 声明能力（README/docs 要点） | 实测 / 走查结论 | 证据（文件:行号 或 验收模块） | 成熟度 |
|---|---|---|---|---|
| `common/` | 配置加载、结构化日志等跨模块基础设施（`README.md:20`）；C7「字段即契约、密钥不入配置」（`CONTRACTS.md:134-142`） | 密钥只存环境变量**名**，运行时解析；部门 Key 只存 sha256（实测 3 个 64 位小写 hex，摘要对得上但不打印明文）；`admin_key_env`/`mask_key_env` 被移出 `ANONGW_<K>` 覆盖命名空间（防 fail-open 改指），负例断言 PASS | `common/config.py:52-83`（`AppConfig`，`extra="forbid"`）、`:91` 豁免表、`:119-132 load_dept_keys`、`:135-145 resolve_secret`、`:148-166 load_env_file`；`common/logs.py:34-54`；验收 `m0_infra` 20/20（**两稿均实跑，均 exit 0**） | **已实装** |
| `gateway/` | OpenAI 兼容网关与流式还原（`README.md:21`）；主链 8 步序（`specs/gateway-main-chain.md:9-14`）；出站**全量**检测面（`pipeline.py` docstring `:19-23`） | 非流式 + SSE 流式双形态实跑 200；四个协议头齐备（`x-anongw-route / -request-id / -session-id / -ai-label`）；`include_keys=True` 形参已使检测面覆盖 dict 键位（契约痛点已修复，见「差距」D5） | `gateway/pipeline.py:332 handle_chat`、`:414 handle_chat_stream`、`:573 _prepare`、`:172-192 _iter_string_leaves(include_keys=True)`、`:195-239 _aux_texts`、`:315-329 _bind_session`、`:407-410` 注入 AI 标识；`gateway/app.py:202 create_app`（端点全表 `:271-537`）、`gateway/sse.py:61/149`；`gateway/deps.py:30-38`（`hmac.compare_digest` 常量时间）；验收 `t0_gateway` 15/15、`t0_stream` 14/14、`m10_e2e` 8/8、冒烟 §(a)(b)(d)(f)(g) | **已实装** |
| `recognizers/` | 「三层识别引擎」（`README.md:22`）；README.md:7 已改口「规则 + 校验位 + 语义词表已实装，**NER 为适配器预留位**」 | 规则层与语义层实装且强：结构化号码 micro=1.0000、12 类逐类 recall 全 1.0、白名单 0/22、26 条难负例零满置信误判。**但 NER 恒空**；人名只靠 `config/person_names.txt` 的 **4 条**演示名 + 前 100 姓启发式（confidence=0.5）+ 静态停用词；**住址 ADDRESS 规则层完全不产出**（实测 grep `EntityClass.ADDRESS` 在 `recognizers/rule/detect.py` 零命中） | `recognizers/rule/detect.py:433-561 detect`、`:365-399 _classify_token`、`:89-91` 姓氏启发式、`:95-102` 停用词；`recognizers/pipeline.py:18-29 detect_full`；`recognizers/models.py:19-48 EntityClass`（19 值）、`:52-55`（9 子类型）；`recognizers/ner/adapter.py:29-31 detect` 恒 `[]`、`:23-27 model_path` 只记不加载；`recognizers/rule/whitelist.py:1-17`（`public_title_before` 自陈为 NER 接入前的休眠路径）；验收 `m2_recognizers` 6/6、`m2_semantic` 11/11 | **部分实装**（规则/语义实装；NER 占位） |
| `masking/` | 可逆脱敏（`README.md:23`）；「会话稳定可逆脱敏：占位符按密钥哈希固定、号码归一化、流式缓冲还原、工具调用参数还原」（`README.md:8`） | 四项声明全部有测试支撑：1000 值×重复/重放占位符不变、跨会话全异；6 类 18 变体归一到同一占位符；500 例分块流式 == 整段还原且缓冲 ≤48 字符；工具参数 hold-to-finish 三项断言全过。**注意：往返是「归一化等价」不是「逐字还原」** | `masking/mapper.py:222-224`（HMAC-SHA256）、`:226-256 placeholder_for`（8/10/12 位升位）、`:110-135 canonical_placeholder`（**四步**，含 `_strip_prefix_segments` `:97-107`）、`:138-200` 容错还原、`:312-386 SessionRegistry`（LRU + `_owners` 按 2×容量裁剪）；`masking/normalize.py:52-84`；`masking/remap.py:50-119 StreamRestorer`；`masking/toolbuf.py:99-145`；`masking/session_store.py:91-248`（SQLite + TTL）；验收 `m3_masking` 9/9、`t0_stream` 14/14 | **已实装** |
| `routing/` | 敏感度路由（`README.md:24`）；R1–R6 矩阵「BLOCK > GOVCLOUD > INTERNET」（`specs/routing-matrix.md:9-18`） | 43/43 通过：38 条矩阵用例三路由全覆盖；冲突序成立（密级词单命中即 BLOCK，白名单不豁免拦截）；批量阈值可配（冒烟实测 3 条身份证 + 手机号 → GOVCLOUD，且只走 8902 腿） | `routing/engine.py:69-144 decide`（纯函数）、`:36-50` 类别集合、`:61-66 _bucket_block`；`routing/models.py:20-32 RouteReason`、`:47-49` BLOCK 恒 null；`config/app.yaml:25 thresholds.batch_pii_to_govcloud: 3`；验收 `m4_routing` 43/43、`t0_gateway` 15/15 | **已实装** |
| `outguard/` | 输出侧防护（AI 标识、拦截文案、代答）（`README.md:25`）；AI 标识三面（`specs/outguard.md:8-13`）；「内容风控与代答拒答」（`README.md:3,11`） | AI 标识三处（末 delta 尾注 + finish annotations + 响应头 `x-anongw-ai-label: 1`）实跑确认；403 文案与文案库模板逐字相等；flagged → 403 `OUTPUT_MODERATION`。**但「内容风控」本身是 P0 空后端**：`NullModerator` 恒 safe（`m5_outguard` 的 moderation 断言即断言这一点），真实审核模型未接 | `outguard/label.py:38-51 apply_message_label`（尾注+annotations+幂等）；`outguard/fallback.py:62-115`（YAML 文案库 + 关键词代答）；`outguard/service.py:24-71`（按后端签名决定是否传 `redact`）；`outguard/moderation.py:48-55 NullModerator`、`:58-75 verdict_of`；`config/app.yaml:27 moderation_model: ""`；验收 `m5_outguard` 13/13 | **部分实装**（标识/文案/代答实装；风控模型占位） |
| `filechannel/` | 文档解析与彻底删除导出（`README.md:26`）；「Word/Excel/PDF/扫描件公开前体检，一键导出彻底删除版」（`README.md:10`） | 两条通道均实跑通过：文本层（docx 四位面 / xlsx 隐藏行列 / pdf 三引擎回退链）12/12；**扫描件 OCR 通道 6/6（302 秒）**——3 份合成扫描件判 `kind=scan_pdf`，身份证召回 12/12=1.00，12 处 bbox 全在页内且与绘制行 y 带相交，导出重栅格化后再 OCR 零残留，零命中件走 `pdf-noop` 字节原样 | `filechannel/inspect.py:82-116 inspect_bytes`、`:64-79 risk_level_of`；`filechannel/parsers.py`；`filechannel/ocr.py:158-202`（引擎名经 config importlib）；`filechannel/sanitize.py`（三条删除式重写 + **re-ingest 零残留是管线内硬闸，非仅验收断言**）；`filechannel/pdf_engine.py:500-520 load_engine_chain`；`filechannel/service.py:97-119 export_bytes`；验收 `m6_filesvc` 12/12、`m6_ocr` 6/6、`m9_webui` 16/16 | **已实装**（文本层 + OCR 层均有实测） |
| `audit/` | 审计日志与看板（`README.md:27`）；「日志只存脱敏内容，全程可审计」（`README.md:3`） | 17/17 通过：journal_mode=wal；库文件（含 `-wal`/`-shm`）65536B bytes 级扫描 **0/7 原值命中**；投毒行负控被 `db_file_scan` 抓住；admin API 分页/筛选/指标聚合/CSV（含公式注入防护）全绿。盘点员另**独立读库复核**冒烟会话：5 行预览对 4 个原值子串扫描全部 False | `audit/store.py:57-83 assert_no_raw_pii`（归一化值+表面形式同查+截断边界守护）、`:86-111 safe_preview`、`:114-141 assert_db_no_raw_pii`（含 wal/shm/死信）；`audit/writer.py:39-58 audit_events` schema；`audit/query.py`；`audit/models.py:22-45 AuditEvent`（**无 raw 字段**）；`gateway/pipeline.py:909-924 _audit`；验收 `m7_audit` 17/17、冒烟附「审计落账独立复核」 | **已实装** |
| `benchmark/` | 合成测评集与基线对比（`README.md:28`）；「结构化号码召回 ≥99.5%，实测 100%；CPU 2000 字 <100ms」（`README.md:13`） | **生成器已实装并实跑**：4/4，产出 372 用例（detect 300 / 白名单 46 / 难负例 26）、14 类政务文书模板、7 类扰动、澄迈区划码 60 项；双跑**字节级一致**（seed 20260928）；15 份 docx/xlsx/pdf 夹具 sha256 与 seeded PII 回环全中。**但 `evals/m8_baselines.py` 不存在**，多基线对比与 F1 验收门为规划态（`CONTRACTS.md:149` 已如实登记） | `benchmark/generator/build.py:31 build_all`；`cases.py`/`fixtures.py`/`numbers.py`（自研 GB11643/GB32174/Luhn 校验位生成）/`templates.py`/`geo.py`；`config/synthetic_corpus.yaml`（经 importlib 加载）；验收 `m8_generator` 4/4 | **已实装（生成器）**；基线对比为**规划态** |
| `webui/` | 演示前端页面（`README.md:29`） | 16/16 通过：体检页 / 演示控制页 / 聊天双屏 / 看板均 200；**看板回环闸成立**（`192.0.2.111` → 403、回环 → 200）；admin key 硬闸成立（部门 Key 401 / admin 200）；SSE 26 帧还原零占位符泄漏。**注意 `/webui/*` 整体无鉴权**（看板另有回环闸） | `webui/pages.py:152 mount`（六条路径）、`:191-208` 回环闸（`_LOCAL_CLIENT_HOSTS={127.0.0.1,::1}`）；`webui/dashboard.py`（纯函数聚合 + 手写 SVG，`html.escape` 防注入）；`webui/demo_api.py:52-62` admin key 硬闸、`:69-101 /admin/api/demo/*`；`webui/templates/*.html` 五页；验收 `m9_webui` 16/16 | **已实装** |
| `ops/` | 运维工具：名称守卫、克隆脚本、e2e 冒烟、公开导出（`README.md:30`） | **部分实跑**：`name_lint` 标准档（146 文件 0 违规）由静态盘点员实跑、`m0_infra` 内亦校验；`e2e_smoke.py` 八用例 U1–U8 经 `m10_e2e` 实跑通过（8 PASS / 0 FAIL / 0 DEFERRED）；`seed_demo.py` 经 T5.3 产出 18 事件三部门可查、90112 字节复扫 0 命中。**整门（gate_d0/b1–b6/gate_final）与 `export_public.py` 未跑** | `ops/name_lint.py:44-50` 后缀与排除目录、`:33-35`（库名只许在 `config/`）；`ops/e2e_smoke.py:1-70`；`ops/gate_d0.py`+`gate_b1..b6.py`+`gate_final.py`（`gate_final.py:64-77` 含 ⑦ gate_b6）；`ops/export_public.py:73 DEPLOYER_PLACEHOLDER="_BY_DEPLOYER_"`、`:315` 对导出树跑 strict；`ops/seed_demo.py`；`ops/tunnel_gpu.sh`；验收 `m0_infra`、`m10_e2e` | **已实装**（name_lint / e2e_smoke / seed_demo 实跑）；**整门未跑** |
| `evals/` | 「可执行验收入口（`python -m evals.*`，exit 0 = 通过）」（`README.md:31`） | 19 个 eval 模块 + `evals/thresholds.py`（阈值单一来源，98 行）。**本次 16 个全部 exit 0**；但另有 2 个按指令未跑（`u8_repro`、`m8_quality`），`m8_baselines` 根本不存在 | `evals/thresholds.py:15 RULE_LATENCY_MS_2000CH=100`；本报告「验收套件实测记录」全表；日志索引见 `minimax_实测.md` §7 | **已实装** |
| `gpu/` | **不在 README 组件表内**，`docs/assets/manifest.md` 也未列 | 仅 2 个 shell 脚本。`gpu/setup_llm_service.sh` 的 `LLM_HF_REPO` **必须经环境变量提供、不入仓库**（红线做对）；`gpu/llm_keepalive.sh` 为 GPU 机侧保活。无 Python 入口 | `gpu/setup_llm_service.sh`、`gpu/llm_keepalive.sh` | **辅助脚本**（非 Python 组件） |
| `gpu-services/` | 同上，**不在 README 组件表内** | 732 行 FastAPI、OpenAI 兼容子集，模块 docstring 写明接口口径；模型真实名不入仓库（经 `LLM_HF_REPO`/`LLM_MODEL_DIR` 注入）。**本机侧 `/health` 联通性未验证**；但经 `m10_e2e` U8 实跑证明该服务在本机 `127.0.0.1:9004` **可达且能出真实中文长文回复** | `gpu-services/llm_openai/service.py:1-40`、`:run_gpu.sh`；`config/app.yaml:12-13`（本机经 `ops/tunnel_gpu.sh` 隧道访问）；验收 `m10_e2e`（U8 双腿真实推理） | **已实装**（本机经隧道联通性由 U8 间接证实；直连未验证） |

---

## 验收套件实测记录

调用方式（全程统一，`minimax_实测.md` §1.1）：

```bash
cd "D:/new-workspace/澄迈项目/政务AI安全"
python wf_run.py venv -m evals.<模块名>
```

| # | 模块 | 退出码 | 用时 | 关键结论（自报原文摘录 + 关键数字） |
|---|---|---|---|---|
| 1 | `m0_infra` | 0 | 34s | `M0 INFRA: 20/20 checks passed`；13+7 个依赖 dists 校验通过；146 文件名称检查 0 违规；9 契约模型 `extra=forbid` 负例生效。**静态盘点员独立复跑同名模块亦 exit 0**（双跑） |
| 2 | `m2_recognizers` | 0 | 0s | `M2 RECOGNIZERS: 6/6`；结构化号码 micro=**1.0000 (618/618)**；白名单 FPR=**0/22=0.0000**；26 条难负例零满置信误判；2000 字×10 均值 **2.07ms** <100ms |
| 3 | `m2_semantic` | 0 | 2s | `M2 SEMANTIC: 11/11 (injection×34, normal×45)`；直接/间接/工具描述三类注入召回均 **1.0000**；正常公文误拦 **0/45**；均值 0.85ms。**⚠ 见下方「通过了但有前提」(1)** |
| 4 | `m3_masking` | 0 | 3s | `M3 MASKING: 9/9`；10 万次插入 **0 冲突**（2 例升位 8→10 位）；15 形态 + 6 负例；50 占位符/2004 字符还原均值 **0.279ms** <20ms |
| 5 | `m4_routing` | 0 | 0s | `M4 ROUTING: 43/43`；38 条矩阵用例三路由全覆盖；批量阈值可配（2→批量 / 5→单 PII）且下限钳 1；冲突序 BLOCK > GOVCLOUD > 单 PII 成立 |
| 6 | `m5_outguard` | 0 | 10s | `M5 OUTGUARD: 13/13`；流式末 delta 尾注 + finish annotations + 响应头三处 AI 标识；403 文案 == 文案库模板；flagged 后端 → 403 `OUTPUT_MODERATION`；`NullModerator` 恒 safe |
| 7 | `m6_filesvc` | 0 | 39s | `M6 FILESVC(text-layer+export): 12/12`；15 份夹具命中 82/82；docx 四位面（正文/表格/页眉/页脚）7/7；xlsx 隐藏列 D 整列删后零隐藏维度；PDF 三引擎回退链逐个零残留 |
| 8 | `m6_ocr` | 0 | **302s** | `M6 OCR(scan-pdf): 6/6`；3 份合成扫描件 `kind=scan_pdf`；身份证召回 **12/12=1.00**（≥0.9）；12 处 bbox 全在页内且与绘制行 y 带相交；导出重栅格化后再 OCR 零残留；零命中件 `pdf-noop` 字节原样 |
| 9 | `m7_audit` | 0 | 5s | `M7 AUDIT: 17/17`；`journal_mode=wal`；库文件（+wal/shm）65536B bytes 级扫描 **0/7 原值命中**；投毒行负控被 `db_file_scan` 抓住；admin API 分页/筛选/CSV 公式注入防护全绿 |
| 10 | `m8_generator` | 0 | 5s | `M8 GENERATOR: 4/4`；372 用例（detect 300 / 白名单 46 / 难负例 26）、14 模板、7 类扰动、澄迈区划 60；**双跑字节级一致（seed 20260928）**；15 份 docx/xlsx/pdf 夹具 sha256 与 seeded PII 回环全中 |
| 11 | `m9_webui` | 0 | 35s | `m9_webui: 16/16 检查通过`；体检页/演示控制页/聊天双屏/看板全 200；**看板回环闸**（`192.0.2.111`→403 / 回环→200）；**admin key 硬闸**（部门 Key 401 / admin 200）；SSE 26 帧还原零占位符泄漏 |
| 12 | `m10_e2e` | 0 | 108s | `e2e_smoke: 8 PASS / 0 FAIL / 0 DEFERRED`；U1–U7 mock 链全绿（审计落库 27 行、库 77824 字节零明文）；**U8 双腿真实大模型推理通过（服务 `http://127.0.0.1:9004`）**；T5.3 `seed_demo` 18 事件三部门可查、90112 字节复扫 0 命中 |
| 13 | `m11_robust` | 0 | 88s※ | `M11 ROBUST: 7/7`；10MB×2 → 413；深嵌套/数组体/非法 JSON → 400 且**上游零感知**；非法 UTF-8 与 12MB 超长 SSE 行有界（只回 292 字节）；**50 并发全 200 零串扰**（批 36.3s）；库 73728 字节零明文。**⚠ 日志内 `RuntimeError` 来自 `evals/m11_robust.py:275` 故意的坏上游中途断连夹具，对应检查项 PASS，非失败** |
| 14 | `t0_gateway` | 0 | 15s | `T0 GATEWAY NONSTREAM: 15/15`；无 key / 错 key → 401 信封；普通样例上游全占位符（bytes 级零原值）+ 客户端还原；批量名单仅走 8902；密级 → 403 `CLASSIFICATION_MARK` 且双 mock 环缓冲零增长；会话属主绑定跨部门 403 |
| 15 | `t0_stream` | 0 | 17s | `T0 GATEWAY STREAM: 14/14`；SSE 回显逐字节还原、零占位符残留、尾注 + annotations + `ai-label` 头齐备；23 种已知改形逐字节还原、8 负例原样放行；流式密级 → 403 JSON（**非 SSE**）且上游零感知 |
| 16 | `t0_labels` | 0 | 21s | `T0 LABELS: 8/8`；`docs/contracts/labels.md` 172 行 8580 字符、10 章节齐备；19 个 EntityClass 值 + 9 子类型 + 4 政务身份与代码值域逐一一致；**含 12 处不确定项显式标注**（「GB/T 45574-2025 标准全文未逐字核对」等，`docs/contracts/labels.md:36-44`）；name-lint 146 文件 0 违规 |

**※** `m11_robust` 的 88 秒为盘点员用「日志文件名内嵌的启动毫秒时间戳 vs 文件 mtime」推算所得（该次 `wf_run` 打印 secs 的首行被 `tail -50` 截掉）。同一算法在 `m6_ocr` 上算出 302 秒、与 `wf_run` 自报值完全吻合，故采信。其余 15 个模块的用时均为 `wf_run` 首行原值。

**SKIP 项（未运行，无任何通过性证据，不做任何推断）**

| 模块 | 状态 | 原因（如实记录） |
|---|---|---|
| `evals.u8_repro` | **SKIP（未运行）** | 编排指令要求 SKIP，理由「需真实上游大模型 key，本环境没有，不要尝试」。实测员**遵守了「不要尝试」**，但指出该理由与实测证据冲突：① `m10_e2e` 的 U8 腿已实跑通过**真实大模型推理**（`netstat` 实测 `127.0.0.1:9004` LISTENING，`Get-Process` 显示该监听是 `ssh` 进程、StartTime 2026/10/3 19:00:06，早于验收窗口，与 `config/app.yaml:12-13` 所述隧道一致）；② `.env` 中 `REAL_LLM_KEY`/`GOVCLOUD_LLM_KEY` 有值（值未读取、未记录）。**故本项 SKIP 的真实含义是「按指令不跑」，而非「环境不具备条件」** |
| `evals.m8_quality` | **SKIP（未运行）** | 同上指令与同一冲突理由。该模块对应「多基线质量比」验收，同样**无任何实测证据** |

**合计：16 通过 / 16 尝试（另 2 项按指令 SKIP 未运行，0 失败、0 需重跑）。**

### 三个必须随「通过」一起引用的前提

1. **`m2_semantic` 跑的是纯规则降级，不是真 LLM 语义判定。** 日志前两行原样是 `semantic_judge.degrade`（出现 2 次）。按 `.env.example` 语义层说明与 `evals/m2_semantic.py` 的 `judge-adapter` 检查项：`SEMANTIC_JUDGE_BASE_URL/KEY/MODEL` 三项齐备才启用，否则降级为纯词表。故 **11/11 证明的是「规则词表拦截面 + 降级不炸」，不是「真模型能判注入」**；真 judge 路径（补判 / 故障降级 / env 驱动）只做到注入假后端的单元级验证。
2. **`m11_robust` 日志里的 Python traceback 不是失败**（见上表备注）。
3. **`m8_generator` 会重写 `data/`**（`data/` 已被 `.gitignore` 覆盖，实测 `git check-ignore` 命中），属运行时工件，非源码改动。

---

## 网关实跑冒烟记录

盘点员在 `127.0.0.1:18732` 起了**真实网关**（读真实 `config/app.yaml` + 真实 `.env`）+ 两个 mock 上游（`:8901` `internet_mock`/`mock-chat`、`:8902` `govcloud_local`/`gov-chat`，与 `config/app.yaml:9-10` 一一对应），全程真实 HTTP over TCP。全程只用**一把演示部门 key**（明文见 `.env.example` 注释与 `evals/t0_gateway.py:63-65`，**本报告不复述**）；盘点员独立复核了该 key 的 sha256 命中 `config/dept_keys.yaml`（digest-ok count: 3），不打印明文。

启动/就绪：`python -m gateway.mock_upstream --host 127.0.0.1 --port 8901|8902`（`mock_upstream.py:407 main()`）、`python -m gateway --host 127.0.0.1 --port 18732`（`__main__.py:16 main()`，`:35` `--port` 优先于 `cfg.listen`，`:31` 先 `load_env_file()` 再 `load_app_config()`）。就绪探针 `:8901/healthz → {"ok":true,"instance":"internet_mock",...}`、`:8902/healthz`、`:18732/healthz → {"ok":true,"service":"gov-anon-gateway"}`，并 `POST :8901/admin/reset → cleared:0`。

> 计数口径备注：工作稿 §0/§2.3 记为「11 类请求」，逐小节展开为 (a)(b1)(b2)(c1)(c2)(d)(e)(f×4)(g) 共 12 次业务请求 + 4 次 `/healthz` + 1 次 `/admin/reset` + 若干 mock 观察。**两种计数口径并列存疑，未深究**（下表以小节逐条为准）。

| # | 输入要点 | 路由 / 处理 | 结果 |
|---|---|---|---|
| a | 普通对话：「今天下午三点召开全镇防汛工作会议，请各村干部参加。」（无 PII） | `INTERNET` | **200**；头 `x-anongw-request-id: req_67fad537a60d`、`x-anongw-session-id: smoke-a`、**`x-anongw-ai-label: 1`**；content 尾行 `本内容由AI生成`；`annotations:[{"type":"ai_generated","text":"本内容由AI生成"}]`；`usage.total_tokens=74`。标识文案与 `config/app.yaml:22 ai_label` 一致 |
| b1 | `POST /internal/detect`：「居民张三的身份证号11010519491231002X，手机号138 0013 8000，请核对低保申领材料。」 | 规则层 detect | **200**，findings=3：`f_0001 PERSON layer=rule raw='张三'`；`f_0002 ID_CARD layer=rule`；`f_0003 PHONE_MOBILE layer=rule raw='138 0013 8000' normalized='13800138000'`。手机号 raw 留分隔符、normalized 去空格 = 归一化等价口径 |
| b2 | 同文本走 `/v1/chat/completions` | `INTERNET` | **200**；客户端收到**还原后的**原文 + `本内容由AI生成` 尾注 |
| b3 | 旁证：查上游 `:8901/admin/text`（280 字节） | 上游实收 | 两条 messages 全文：第 1 条原文；第 2 条为 `居民〔人名·a0e1c61d〕的身份证号〔身份证·ece5a6d2〕，手机号〔手机号·49140cc5〕，…` |
| b4 | 旁证：对 280 字节做 UTF-8 子串判定 | bytes 级原值扫描 | `contains '11010519491231002X' → False`；`'13800138000' → False`；`'张三' → False`；`contains 〔身份证· → True`。**出站零原值在盘点员侧独立复核成立** |
| c1 | `POST /internal/anonymize`，`session_id=smoke-c` | 脱敏 | **200**；`masked` 三处占位符；`mappings` 3 条，键集 `[first_seen, normalized, placeholder, preserve_semantic, session_id, type]` |
| c2 | `POST /internal/restore` | 还原 | **200**；`restored` 为原文。**严格逐字一致 = False**（手机号由 `138 0013 8000` 变回 `13800138000`），**归一化等价 = True** |
| d | 同 (b) 文本 + `"stream":true`，`curl -N` 抓全流 | SSE 流式 | **200**、`text/event-stream; charset=utf-8`、`chunked`；头 `x-anongw-route: INTERNET`、`x-anongw-ai-label: 1` 齐全；**23 帧**，`data: [DONE]` 正常收尾；delta 拼接后**三个原值全部在流中**（True/True/True）；正则 `〔[^〕]*·[0-9a-f]{8,12}〕` 扫描**零占位符残留**；尾注 True、finish 帧 delta 带 annotations True。同时刻上游 `:8901/admin/text` 仍是全占位符 |
| e | 密级：「机密★项目纪要：居民张三，手机号13800138002，不得外传。」 | **`BLOCK`** | **403**；头 `x-anongw-route: BLOCK`（非 INTERNET/GOVCLOUD）；信封 `code=content_blocked` + 保密拦截文案；`reasons[0]={CLASSIFICATION_MARK, fid:f_0001, detail:"命中 机密★"}`、`reasons[1]={… "命中 不得外传"}`。**是否转发：否** —— `:8901/admin/records` count 仍为 3（未 +1），`:8902` count 仍为 0，`:8902/admin/text` 中 `机密★` 出现 **0** 次 |
| f1 | `POST /v1/chat/completions` **不带** Authorization | 鉴权闸 | **401**，`{"error":{"code":"unauthorized","message":"无效部门 Key（Authorization: Bearer dk_***）","reasons":[]}}`（key 值在信封中本就是打码的） |
| f2 | 同上，带**错** key | 鉴权闸 | **401**，同一信封 |
| f3 | `POST /internal/detect` 不带 key | 鉴权闸 | **401** |
| f4 | `POST /internal/restore` 带错 key | 鉴权闸 | **401**。鉴权闸在 `gateway/app.py:369-373`（chat）与 `:441-444/:459-463/:500-504`（三个 internal 端点） |
| g | 批量名单：3 个身份证 + 1 手机号 | **`GOVCLOUD`** | **200**，头 `x-anongw-route: GOVCLOUD`，响应 `model: gov-chat`；转发切分：`:8901` count 保持 3 未变，`:8902` count 由 0 → **1**（**只走政务云腿**）；客户端 3 个身份证 + 手机号全量还原 + AI 尾注。依据 `config/app.yaml:25 thresholds.batch_pii_to_govcloud: 3` |
| 附 | 盘点员**直接读库**复核（不看自测报告）：`sqlite3 select dept,route,blocked,upstream,reasons,prompt_preview from audit_events where session_id like 'smoke-%' order by id` | 审计落账 | `data/audit.db` 中 `smoke-%` 共 **5 行**（正好对应 5 次 chat 请求；`/internal/*` 不落审计）：`INTERNET/0/internet_mock/NO_FINDING`（无 PII 原文）；`INTERNET/0/internet_mock/SINGLE_STRUCTURED_PII` ×2（预览仅占位符形态）；**`BLOCK/1/None/CLASSIFICATION_MARK×2`**（预览 `〔密级·已拦截〕…`）；`GOVCLOUD/0/govcloud_local/BATCH_STRUCTURED_PII`。对 4 个原值（身份证/手机号/人名/密级词）做子串扫描**全部 False** |

**旁证与隔离性**：冒烟全程 `:8901/admin/records` 的 count 精确等于盘点员发出的请求数（a/b/d 后=3，e 拦截后仍=3，g 之后=3），`:8902` 从 0→1 只出现在 g，且 `/admin/text` 全文只含盘点员自己的两条 messages —— 若有外来流量混入会污染这两个计数，故可反推**冒烟结果未被他人流量污染**。

**踩坑（非项目缺陷）**：Windows 下 `curl -d` 内联中文使服务端返回 `400 bad_request / "request body is not valid JSON"`；改为 UTF-8 写文件 + `--data-binary @file` 后即 200。**网关对畸形 JSON 的拒绝行为本身是正确的**，这是 curl 在 Windows 的传参编码问题。

**进程清理**：`taskkill //PID {25760,23636,8436} //T //F` 成功（三个真实持有监听 socket 的子进程），三个启动器 PID 随子进程终止已自行退出；3 秒后复核 `netstat` 显示 `8901/8902/18732` 均无 LISTENING，无残留 gateway/mock 进程。审计库与 `session_map.db` 因冒烟新增 5 条审计事件与若干会话映射，属网关正常运行时写入（`gateway/app.py:232-237`）。

---

## 声明与现实的差距

### A. README/docs 声明了但实测未支撑 / 与代码不符

| # | 差距 | 声明出处 | 实际 | 影响 |
|---|---|---|---|---|
| D1 | 「冻结 **11 形态 + 4 负例**」 | `docs/assets/specs/masking-placeholder.md:131,:249`；`manifest.md:25` | `evals/m3_masking.py:255-273` 实际 **15 形态 + 6 负例**（多出 `prefix-merged`/`prefix-ascii-colon`/`prefix-multi-segment`/`prefix-combo-noise` 四种「前缀文案并入括号内」形态）；两稿实跑输出均为 15/6 | 文档形态目录缺 U8 新增 4 种，复刻者会漏 |
| D2 | `canonical_placeholder`「规范化**三步**，顺序固定」 | `specs/masking-placeholder.md:91-99` | `masking/mapper.py:110-135` 实际**四步**（多出第 ④ 步 `_strip_prefix_segments` 前缀段剥离，`:97-107`） | 同上 |
| D3 | 冻结常量表列 4 个常量 | `specs/masking-placeholder.md:86` | 缺 `PLACEHOLDER_PREFIX_COLONS`（`mapper.py:74`）、`KNOWN_LABELS`（`:94`） | 同上 |
| D4 | 主链文档行号 `pipeline.py:144-158 / 131-141 / 161-191 / 194-202` | `specs/gateway-main-chain.md:22/26/32/34/44` | 实测 `_iter_string_leaves` 在 **172**、`_content_segments` 在 **157**、`_aux_texts` 在 **195**、`_apply_aux_masked` 在 **242**，全部偏移 28–48 行 | 按行号导航落空 |
| D5 | 契约痛点 #1：「`_iter_string_leaves` 只递归 dict 的 values，字符串键不进检测面 → PII 藏 JSON 键位时漏检漏替换」 | `CONTRACTS.md:148` | **该痛点已修复**：`pipeline.py:172-192` 已有 `include_keys` 形参，`:220/:231/:238` 三处调用均传 `include_keys=True`；`evals/t0_gateway.py:540 outbound:full-detection-face` 有断言 | 契约痛点表未回填「已销项」，读者会误判仍有泄漏面 |
| D6 | 验收项数冻结于 2026-09-29 基线：「t0_gateway 13/13、t0_stream 11/11、m9_webui 14/14、m7_audit 16/16、m8_generator 4/4」 | `docs/assets/manifest.md:8` | 实测代码与本次实跑均为：t0_gateway **15**、t0_stream **14**、m9_webui **16**、m7_audit **17**、m8_generator 4 | 文档项数落后后续 S2 修复 |
| D7 | 门清单「标准库 Python 门脚本 ×6（gate_d0 + gate_b1..b5）」 | `docs/assets/manifest.md:32` | 实际 **7 个门 + 1 终检门**：`gate_d0/b1/b2/b3/b4/b5/b6` + `gate_final`（`gate_final.py:64-77` 明确含 ⑦ gate_b6）；`specs/gates.md:19-26` 门项表同样无 G-B6 行 | 门清单不全 |
| D8 | 整门命令写死旧路径 `D:/workspace/澄迈8项目/政务AI脱敏网关/repo/ops/gate_b5.py` | `specs/gates.md:55`；`REGENERATE.md:17/61-63` | 仓库已迁至 `D:/new-workspace/澄迈项目/政务AI安全/gov-anon-gateway/` | 按文档复制粘贴的路径不存在 |
| D9 | 出站辅助面「只列 3 类覆盖（tools / 历史 tool_calls / 非 text 多模态段）」 | `specs/gateway-main-chain.md:34-42` §2.2 | 代码已扩到**顶层其余全部字段 + dict 键 + 消息级非 content 字段**（`pipeline.py:195-239`） | 描述不完整，安全评审会**低估**覆盖面（此条是文档落后于实现） |
| D10 | 反馈台账仍引旧 README 口径：「三层识别…NER（人名/住址/敏感身份）」「F1 ≥95%」 | `docs/assets/feedback.md:14-16`（引 `README.md:7`、`:13`） | README 已改口（现行 `README.md:7` 明确「NER 为适配器预留位」，`:13` 已删 F1）；但 `docs/assets/specs/benchmark-generator.md:49-51`、`manifest.md:24` 仍写「人名/住址（NER 层计分）」，且把 NER F1 列为待落地验收门 | 读者会以为 README 仍在承诺 F1 |
| D11 | 契约写「`python -m ops.name_lint --strict` 零命中」 | `CONTRACTS.md:161` | 静态盘点员实跑 `--strict` → **exit 1，193 文件 19 处命中**，全部在 `config/`（`app.yaml:31 pymupdf`、`filechannel.yaml:5/10/12/19/20`、`install_check.json:13-16/21`、`synthetic_corpus.yaml:5/6/9`）。**这符合设计**（`ops/name_lint.py:33-35` 注释：配置文件默认不扫、库名只许在 `config/`；strict 只用于导出树终检，`ops/export_public.py:315`） | 契约措辞与本仓实跑结果**字面冲突**；开发者照做会拿到 exit 1 |
| D12 | README 安全注记只提 `/v1/chat/completions` 与 `/internal/*` 需部门 Key | `README.md:38-41`；`README.public.md:112-114` | `/v1/files/inspect` 与 `/v1/files/export`（`gateway/app.py:285-364` 确认只有体积/种类闸、无 `authenticate`）与 `/webui/*`（`webui/pages.py:152 mount`）**同样无鉴权**；spec 侧已如实标注（`specs/gateway-main-chain.md:72-73`）与给了理由（`filechannel/service.py:20-22`），看板另有回环闸（`webui/pages.py:202`） | **文档层面的安全面缺口**：README 未提这两片无鉴权，而 `/v1/files/export` 会返回处理后文件字节流 |
| D13 | 「结构化号码召回 ≥99.5%，实测 100%」与「CPU 2000 字 <100ms」 | `README.md:13` | 召回 618/618 = 1.0000 成立；时延两稿均 <100ms（实测 2.07ms，静态 4.53ms max 11.47ms） | **无差距**（此条列出以示已核） |
| D14 | 引用了仓根不存在的文件 `DEPS.txt` | `README.public.md:96` | 实测员在仓根 `ls` 中**未看到** `DEPS.txt`（实有 `.env`/`.env.example`/`README.md`/`README.public.md`/`constraints.txt`/`docker-compose.yml`/`pyproject.toml` 等）。**原因未深究**（可能是公开导出时排除） | 交付方按 README 找不到该文件 |
| D15 | 「`python -m evals.*`，exit 0 = 通过」 | `README.md:31` | 成立（16/16）。**但** `evals.m8_baselines.py` 根本不存在，`u8_repro`/`m8_quality` 存在却未运行 | 部分差距：eval 覆盖面 ≠ 全部声明 |
| D16 | 「语义层」能力 | `README.md:7`（规则 + 校验位 + 语义词表已实装） | `m2_semantic` 11/11 成立，但**跑的是纯词表降级**（日志头两行 `semantic_judge.degrade`），真 LLM judge 能力**未验证** | 「语义层已实装」在真模型口径下**未支撑** |
| D17 | 往返还原「一致性」的表述口径 | 工作稿按归一化等价理解 | 冒烟 (c) 实测：**严格逐字一致 = False**，归一化等价 = True（手机号由 `138 0013 8000` → `13800138000`） | 盘点员判定为**设计口径非缺陷**（对应 `m2_recognizers` 的 `normalization-equivalence`），但对外表述必须按归一化等价讲 |

**两处「诚实加分项」（如实记录）**：`docs/contracts/labels.md:36-44` **主动声明**「GB/T 45574-2025 标准全文未逐字核对」并把每条内容标注「已核实（摘要）/推断/项目自定义」，`evals/t0_labels.py:167` 还有 `labels:uncertainty-marked` 断言把这条纪律**钉进 eval**（本次 8/8 通过）；`README.public.md:82-89` 与 `docker-compose.yml:3-5` 对 docker compose 明写「⚠ 未实测声明」——本次同样未实测，**不构成新的冲突**。

### B. 两稿之间的差异（如实并列，标注待核）

| # | 项 | 静态稿记载 | 实测稿记载 | 处置 |
|---|---|---|---|---|
| C1 | `m2_recognizers` 2000 字×10 均值 | `4.53ms (max 11.47ms)` | `2.07ms` | 两者均远低于 `evals/thresholds.py:15` 的 100ms 阈值，**两次都通过**；差异归因**未核实**（实测期间本机有他人进程，见「环境干扰」）。**待核** |
| C2 | `m3_masking` 还原均值 | `0.763ms < 20ms` | `0.279ms < 20ms` | 同上，**两次都通过**；**待核**（负载/用例规模差异未知） |
| C3 | `m2_semantic` 2000 字均值 | `0.55ms < 50ms` | `0.85ms` | 同上，**两次都通过**；**待核** |
| C4 | 未跑模块清单 | 静态盘点员未跑 `m5_outguard`/`m7_audit`/`m9_webui`/`t0_gateway`/`t0_stream`/`m10_e2e`/`m11_robust`/`m8_generator`/`m6_ocr`/`t0_labels` 等 | 全部 16 个实跑 exit 0 | **非矛盾**，是范围/时序差异（静态盘点员只跑 6 个）。**以实测稿为准** |
| C5 | 静态稿内部交叉引用 | §1.1 表格把「README.public §2 冒烟命令实为空跑」指向「详见 §4-⑪」，但 §4 只有 8 条、⑪ 实际是 §3 表第 11 行（NER 预留位） | — | 疑为「§3-⑪」笔误；该条结论本身（`pytest` 空跑）证据在 §1.1 的 exit 4/5 输出，**结论不受影响**。**待核** |
| C6 | `pytest` 冒烟 | 实跑 `python -m pytest evals/m0_infra` → **exit 4**、`collected 0 items / no tests ran`；`python -m pytest`（无参）→ **exit 5**，`testpaths=["tests"]` 但 `tests/` 目录不存在 | 未涉及 | **实测稿未复现**。判为：README.public §2 的 pytest 冒烟命令在本仓**实为空跑**；**待核**（是否为命令笔误） |

---

## 风险与未知

**安全与凭据**

1. **演示部门 Key 的明文常量散落源码（最高优先级横向访问面）**：实测 12 处 `dk_` 明文常量（`evals/m10_e2e.py:54`、`m11_robust.py:100`、`m5_outguard.py:71`、`m7_audit.py:492/613`、`m8_quality.py:79`、`m9_webui.py:499/534`、`t0_gateway.py:64/65/178`、`t0_stream.py:84`、`u8_repro.py:197`、`ops/e2e_smoke.py:135`），**其 sha256 就在 `config/dept_keys.yaml:4-6`** —— 即任何人拿到本仓即可通过鉴权。`README.public.md:122-129` 已如实声明并要求「生产部署必须更换哈希」，属**已知且已披露**的演示凭据；但若交付对象未逐字读该节，这就是实打实的鉴权旁路。**建议把「更换 `dept_keys.yaml` 哈希」列为部署阻断项。**
2. **两片无鉴权但 README 未提的面**：`/v1/files/inspect`、`/v1/files/export`、`/webui/*`（见 D12）。代码行为有 spec 支撑，**缺的是文档层的告知**。
3. **mock 上游端口对外发布**：`docker-compose.yml:39/53` 中 mock 以 `--host 0.0.0.0` 起、端口 `"8901:8901"`（**无 `127.0.0.1` 前缀**）对外发布，而网关是 `"127.0.0.1:9000:9000"`。mock 只回显收到的 prompt、不含真实数据；compose 整体已标注**未实测**。

**工程/一致性风险**

4. **代码态未固化是当前最大工程风险**：37 个未提交修改覆盖全部安全关键面（`gateway/pipeline.py` 出站检测面、`masking/mapper.py` 容错还原、`common/config.py` 覆盖豁免、`outguard/moderation.py` redact 承接、`gpu-services/llm_openai/*`）。**任何「按 git 复现」的动作拿到的都是 HEAD `d6daffd` 的旧代码。** 留档 `evidence/gate-final-20261002.md:38-70` 记的是「28 个文件被修改」，现已漂移到 37（留档为时点快照，非错误，但已明显失配）。
5. **`docs/assets/` 落后代码一轮以上**（D1–D10 共 10 处），而 README.md:43 又把它定位为「spec+eval 驱动开发」的**唯一权威**。按现文档复刻会得到行为不同的系统，且安全评审会同时**高估**（D5）**低估**（D9）风险面。
6. **公开导出后配置被占位符替换**：`config/app.yaml:31 pdf_engine_module`、OCR 引擎、合成语料库坐标在导出后变为 `_BY_DEPLOYER_`（实测 `out/public-export/config/app.yaml:32`），**未配置前 PDF 导出/OCR/夹具生成显式失败**。`README.public.md:100-106` 已如实声明。**该导出树本次未生成、未验证。**

**能力空位（接口在位、实质未落地）**

7. **NER（人名/住址）**：`recognizers/ner/adapter.py:29-31` 恒返回 `[]`。人名只靠 4 条演示名词表（`config/person_names.txt` 实测非注释行 **4** 行：张三/李四/王五/赵六）+ 前 100 姓启发式（`recognizers/rule/detect.py:89-91`，confidence=0.5）+ 静态停用词（`:95-102`）；**住址 ADDRESS 规则层完全不产出**。**连带影响**：`masking/normalize.py:11,:84` 对 PERSON/ADDRESS 只做半角化 + strip，不做串级归一化 —— 一旦开放域 NER 接入，归一化等价面需重新设计。`Whitelist.public_title_before()` 在 NER 接入前是**休眠路径**（`whitelist.py:1-17` 自陈）。验收侧也没有对应门（F1 阈值、`m8_baselines` 都不存在）。
8. **输出侧内容风控**：`outguard/moderation.py:48-55 NullModerator` 恒 safe，`config/app.yaml:27 moderation_model: ""`。真实审核模型未接、**未验证**。README 已改口，但验收层无对应门。
9. **保留字段形同虚设**：`preserve_semantic` 全仓 grep 只出现在模型定义（`masking/models.py:28`）、SQLite 列（`masking/session_store.py:46/62/66/87/183`）与 eval 断言，**无任何读取该标志改变替换行为的代码**。`CONTRACTS.md:150` 已自认「字段形同虚设」。

**代码面脆弱点（走查记录，均有既有防线）**

| # | 位置 | 脆弱点 | 现有防线 |
|---|---|---|---|
| F1 | `gateway/pipeline.py:336-341,:418-420` | 「先校验后绑定」是后加的加固：`_validate_body` 失败前若已 `_bind_session`，垃圾请求可按先到先得抢占任意 `session_id` | 已修（先校验后绑定）+ `masking/mapper.py:363-364` `_owners` 按 2×LRU 容量裁剪；`evals/t0_gateway.py:541 session:owner-binding` 断言（本次 PASS） |
| F2 | `gateway/pipeline.py:792-802` | 审计 `response_preview` 对**真实大模型自由文本**做规则层再脱敏；docstring 自陈「人名等 NER 层实体规则层不可见，属 open-vocabulary 残余，由 U8 的命中宿主裁定兜底」 | 已接 `_safe_response_preview`；残余靠 e2e U8 裁定（本次 U8 PASS，但仅 1 次双腿） |
| F3 | `masking/toolbuf.py:47` | hold-to-finish 是流式路径**唯一无上界缓冲点**，上限 1,000,000 字符 | 绊线式抛 `ToolArgumentsOverflowError`（非静默截断）；`gateway/pipeline.py:505-515` 以 SSE 错误事件收尾 |
| F4 | `gateway/sse.py:79,:93-108` | 上游畸形 SSE「无换行的超长行」会撑内存 | `GATEWAY_SSE_LINE_MAX_BYTES=8MB` 超限丢弃 + WARNING；`t0_stream` / `m11_robust` 实测 12MB 超长行只回 292 字节 |
| F5 | `masking/mapper.py:363-364` | `_owners` 裁剪是 O(n) 的 `next(iter(...))` + `pop`，且与 LRU 是**两套**淘汰口径 | 有界（2×capacity） |
| F6 | `gateway/app.py:385-388`、`app.py:104` | 客户端可自带 `x-anongw-session-id` 直作存储键 | 形态闸 `SESSION_ID_RE` 限 `[A-Za-z0-9._-]{1,128}`；但仍允许任意持证部门预占（F1 同源，先到先得语义） |
| F7 | 验收基础设施 | `m5_outguard`/`m7_audit` 等需独占 9000/8901/8902 | 已知项，写在 `REGENERATE.md:90-95` 坑清单第 3 条；各模块自带端口占用断言（`evals/t0_gateway.py:98-102 _assert_port_free`） |

**环境与外部未知**

8. **本机在验收窗口内并非空闲**：观察到他人/其他会话进程 `ops/gate_b5.py`(PID 25740 @21:08:16)、`ops/gate_b4.py`(PID 22000 @21:11:17)、`ops/gate_b3.py`(PID 25216 @21:16:08)，以及跑 `t0_labels` 期间两个**非盘点员启动**的 mock 上游（PID 21152/25832 @21:09:53/21:09:55，随后自行退出）。**盘点员一律没有杀**（非其拉起）。对冒烟无影响（计数可反证，见上）；对 16 个模块**无 PASS 被污染的迹象**（各模块自带端口占用断言，且 7 个需独占端口的模块都真实起了自己的 mock 与网关并 PASS）。
9. **SKIP 两项的通过性完全未知**：`u8_repro`、`m8_quality` 未运行，**不做任何推断**。且 SKIP 指令给出的「环境没有真实 key」理由与实测证据冲突（隧道已在、`:9004` 在监听、U8 已跑通真实推理），**理由本身待核**。
10. **长稳与真实 profile 稳定性未验**：`internet_real`/`govcloud_real` 两个 profile 本次只经 `m10_e2e` U8 各跑 1 次双腿，**无重复压测/长稳证据**。

---

## 本盘点的局限

1. **报告合成本人是合成者，未执行任何命令、未逐行读代码。** 本报告全部执行结论转录自同组 `minimax_静态.md` / `minimax_实测.md`；**文件:行号引用未由合成本人复核**，若已漂移以代码为准。这是本报告最大的方法论局限。
2. **未由本组任何成员运行的检查（一律「未验证」）**：
   - 整门：`ops/gate_d0.py`、`gate_b1..b6.py`、`gate_final.py`（小时级）—— 两稿均未跑；
   - `ops/export_public.py`（会写 `out/`）、导出树 strict lint；
   - `docker compose up`（`README.public.md:82-89` 自述「构建环境无 Docker，未在容器环境实测」）；
   - `evals.u8_repro`、`evals.m8_quality`（按指令 SKIP）；
   - `evals.m8_baselines`（文件不存在，规划态）；
   - `:9004` GPU 服务**直连**联通性（仅由 U8 经隧道间接证实）；
   - `wf_run.py` / `wf_env.py` 逐文件走查（工作稿只按任务单一句话带过，判为工作流包装器非业务代码）。
3. **未做安全渗透测试**：无端口扫描、无越权矩阵穷举、无 `MASK_KEY` 强度评估、无 `.env` 内容审计（`.env` 实存 8 个变量，**值全程未读取、未记录**：MASK_KEY / MOCK_KEY / UPSTREAM_BIGMODEL_KEY / REAL_LLM_KEY / GOVCLOUD_LLM_KEY / SEMANTIC_JUDGE_BASE_URL / SEMANTIC_JUDGE_KEY / SEMANTIC_JUDGE_MODEL）。顺带发现：**`UPSTREAM_BIGMODEL_KEY` 是孤儿变量**——全仓 grep 在 `.py/.yaml/.json` 中零命中，`config/app.yaml` 的 `api_key_env` 只有 `MOCK_KEY`/`REAL_LLM_KEY`/`GOVCLOUD_LLM_KEY` 三个（无害，属配置面噪声）。
4. **未测覆盖面**：NER 开放域能力（恒空）、输出侧真实审核模型（`NullModerator`）、`internet_real`/`govcloud_real` 长稳、非 docx/xlsx/pdf 之外的文档格式（doc/ppt/图片等未列入任何 eval）、多语言/繁体/少数民族姓名与住址、真实政务文书语料（合成语料是模板生成，非真实数据）。
5. **用例规模的局限**：`m2_recognizers` 618 条结构化号码、`m2_semantic` 34 注入 + 45 正常、`m3_masking` 10 万次合成插入、`m6_ocr` 3 份合成扫描件 —— 均为**合成/自生成**样本，**不能外推为真实分布下的召回率与误报率**。
6. **计数器与口径差异未深究**：C1–C3 的时延差异、C6 的 pytest 空跑、以及冒烟「11 类请求」的计数口径，均并列存疑（见「B. 两稿之间的差异」）。
7. **单一环境、单一时间窗**：全部结论来自 windev-01 一台机器、2026-10-03 20:51–21:22 一个窗口；未做跨平台/跨 Python 版本验证。

---

## 结论（给交付决策用）

1. **主链是真的能跑的**：识别 → 脱敏 → 路由 → 还原 → 审计五段在真实 TCP 上复现成功，出站 bytes 级零原值、审计库零明文两条红线在盘点员独立复核时同样成立（不是只信自测报告）。
2. **验收纪律是本项目最大的资产**：阈值单一来源（`evals/thresholds.py`）、契约 + eval 驱动、把不确定性（labels.md 12 处标注）钉进 eval、37 项 M 未提交仍能跑通 16/16 —— 这套纪律建议原样保留。
3. **交付前阻断项（建议）**：① 更换 `config/dept_keys.yaml` 的三个 sha256（其明文在同仓 `evals/` 里）；② 提交那 37 个未提交修改并冻结快照；③ README 补写 `/v1/files/*` 与 `/webui/*` 无鉴权；④ 修正 `CONTRACTS.md:161` 的 `--strict` 措辞与 `CONTRACTS.md:148` 的已销项痛点；⑤ 同步或标注 `docs/assets/specs/` 的 D1–D10 全部 10 处。
4. **两处能力要在交付话术里说清是接口位**：NER（人名/住址）与输出侧内容风控。README 已改口是好事，但验收层没有对应门，交付方若按「已实装」理解会形成预期落差。
5. **两项 SKIP 需重新安排**：`u8_repro` 与 `m8_quality` 的通过性**目前无任何证据**，且指令给出的 SKIP 理由已被本组实测证据推翻（真实上游可达），建议在可跑条件下补跑。

---

*本报告由独立盘点组「MiniMax-M3.1-Flash」合成，仅依据本组 `盘点/工作稿/minimax_静态.md` 与 `盘点/工作稿/minimax_实测.md` 两份工作稿。全程未修改任何源码/配置/文档文件（仅 `盘点/独立盘点/` 下本文件可写），未为任何「通过」跳过断言或改动配置，失败与缺失如实记录，无法完成的检查一律标「未验证」。报告全文不含 `.env` 内容、`MASK_KEY` 或任何 key/token 明文。*
