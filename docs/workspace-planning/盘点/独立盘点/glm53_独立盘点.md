# GLM-5.3-Flash 独立盘点报告（2026-10-03）

**盘点对象**：`D:/new-workspace/澄迈项目/政务AI安全/gov-anon-gateway`（政务 AI 安全网关；git HEAD `d6daffd`，33 个文件修改未提交；约 2.6 万行 Python，26292 行 wc -l 实测）

**材料来源**：本组两份工作稿——`盘点/工作稿/glm53_静态.md`（静态盘点员：14 组件只读走查 + README 18 条量化/能力声明逐条核对 + 6 个 eval 独立复跑）、`盘点/工作稿/glm53_实测.md`（实测验证员：16 个验收模块实跑 + 8 组真实 HTTP 网关冒烟，执行窗口 2026-10-03 20:08–20:45）。本报告为两稿合成产物：标注「实测」的数字出自实测稿会话，标注「走查」的出自静态稿会话；未新增无两稿支撑的断言，两稿口径不一致处如实并列并标注「待核」。

**红线遵守**：未读取 `.env` 内容；本报告不含任何 MASK_KEY / 部门 key / token 的真实值（冒烟所用密钥均为仓库公开演示夹具值，仅以指代方式表述）；未修改任何源码/配置/文档，仅写入 `盘点/` 目录。

---

## 一、执行摘要

「在零真实 API key 依赖下，一个可运行的政务 AI 安全网关已经真实成立」——14 个组件中 12 个已实装、benchmark 部分实装（m8_baselines 为显式规划态）、gpu/gpu-services 为已实装的部署侧件；识别→可逆脱敏→敏感度路由→输出防护→审计闸主链路全部真实实装，所有占位处（NER 适配器、输出复检后端、m8_baselines、docker-compose 实测、演示场景 1-3 脚本）均显式声明，未发现静默假实现。本盘点周期实测：16/16 验收模块一次通过（约 8.7 分钟，无一重跑修复），另加 8 组独立真实 HTTP 冒烟——PII 出不了网（mock 上游 bytes 级零原值）、客户端无损还原、密级直接 403、会话属主闸、AI 标识三形态、审计只存脱敏预览全部复现；关键量化声明（结构化号码召回 1.0000、注入召回 1.0000 且正常公文误拦 0/45、10 万次脱敏插入 0 碰撞、e2e 八用例含真实大模型腿）全部有实测证据。主要差距不在能力而在收官：33 个文件（含全部 S2 安全修复）未提交固化、S2 后整门 gate_final 未取得 9/9、u8_repro/m8_quality 因无真实上游 key 未验证、三处文档滞后。

## 二、组件级清单与结论

| # | 组件 | 声明能力（README/docs 要点） | 实测/走查结论 | 证据 | 成熟度 |
|---|---|---|---|---|---|
| 1 | common 基础设施 | 配置加载、结构化日志等跨模块基础设施（README.md:21）；契约 C7「密钥不入配置文件」 | 走查确认：env 覆盖机制对密钥变量名字段豁免（封死 `ANONGW_ADMIN_KEY_ENV=攻击者变量` 类 fail-open）；部门 key 只存 sha256 且 64 位 hex 校验；resolve_secret 缺失即抛错；JSON 日志禁原文红线 | common/config.py:91,96-97,127-145；common/logs.py:5-7；m0_infra 20/20（含 env-override 负例） | 已实装 |
| 2 | gateway 网关主链 | OpenAI 兼容网关与流式还原；detect→mask→route→转发→还原→outguard→audit 主链；「出站全量检测面——无任何原样透传面」 | 走查确认：主面/辅助面双检测（含 dict 键检测/换名）、先校验后绑定（400 垃圾请求不留属主绑定）、跨部门 403、有界读取、BLOCK/上游不可达/协议错误开流前决出；实测冒烟 8 组行为全部符合设计 | gateway/pipeline.py:19-23,157-257,332-550,909-924；gateway/app.py:117-181,261-266,518-525；t0_gateway 15/15、t0_stream 14/14、m10_e2e 8/0/0、m11_robust 7/0、冒烟 8 组 | 已实装 |
| 3 | recognizers 三层识别 | 规则 + 校验位 + 语义词表已实装；「NER（人名/住址模型化识别）为适配器预留位」（README.md:7） | 实测结构化号码 micro recall=1.0000（618/618）、注入召回 1.0000（直接/间接/工具描述）、正常公文误拦 0/45（含否定句式陷阱）；NER `detect` 恒返回空列表并记 debug 日志（显式声明未加载，非假实现） | recognizers/rule/detect.py:108-117；recognizers/ner/adapter.py:29-31；m2_recognizers 6/6、m2_semantic 11/11 | 已实装（NER 显式占位） |
| 4 | masking 可逆脱敏 | 会话稳定可逆脱敏：占位符按密钥哈希固定、多轮不变号；流式缓冲还原；工具调用参数还原（README.md:8） | 实测 10 万次插入 0 碰撞（同摘要值自动升位 8→10→12）、500 组流式切块还原==整段还原、19 种残缺占位符逐字节还原、工具 hold-to-finish；50 占位符/2004 字还原均值 0.259ms < 20ms | masking/mapper.py:186-220；masking/remap.py:41；masking/toolbuf.py:44-53；m3_masking 9/9、t0_stream 14/14 | 已实装 |
| 5 | routing 敏感度路由 | 普通脱敏走互联网模型，敏感个人信息/工作秘密切政务云，密级标识直接拦截（README.md:9）；R1–R6 矩阵 | 实测 43/43：批量 ≥3 结构化号码→GOVCLOUD、单 PII→INTERNET 脱敏出网、密级→BLOCK、白名单不计数、BLOCK 恒 null upstream；冒烟组 e/g 独立复现拦截与批量路由 | routing/engine.py:69-144；m4_routing 43/43 | 已实装 |
| 6 | outguard 输出侧 | AI 生成标识（显式+隐式元数据）、代答/拒答库（README.md:11） | 实测标识三形态（尾注行/annotations/响应头 `x-anongw-ai-label`）幂等、密级 403 文案与文案库模板流/非流同源、空文案零注入、moderation hook flag 入审计；复检后端为 NullModerator 显式占位（真实审核模型 P1 未接入，接口与调用点已接线） | outguard/label.py:38-51；outguard/moderation.py:48-55；config/app.yaml:27（moderation_model 留空）；m5_outguard 13/13 | 已实装（复检后端显式占位） |
| 7 | filechannel 文件通道 | Word/Excel/PDF/扫描件「公开前体检」、一键导出彻底删除版（README.md:10）；导出零残留为管线内硬闸 | 实测 15 夹具命中 82/82、docx 四位面（正文/表格/页眉/页脚）7/7、xlsx 隐藏列/行/批注 13/13、pdf bbox==charbox 并集、三导出引擎 re-inspect 零残留、50MB/种类/畸形全拒；OCR 身份证召回 12/12=1.00、重栅格化打码再 OCR 零残留、零命中件 pdf-noop 字节原样 | filechannel/inspect.py:1-30；filechannel/sanitize.py:1-23；m6_filesvc 12/12、m6_ocr 6/6 | 已实装 |
| 8 | audit 审计 | 审计看板按部门统计拦截、导出保密自查报告（README.md:12）；「日志只存脱敏内容」（README.md:3） | 实测零明文双闸（泄漏原值事件 pre-enqueue 拒收、0 行入库）、库文件 bytes 级扫描 65536B 0/7 原值命中（覆盖主文件/-wal/-shm/死信）、admin 401 负例/分页钳位/13 项指标手算全等、report.csv 5707 字节零明文+公式注入防护 | audit/store.py:57-83,114-128；audit/writer.py；m7_audit 17/17、冒烟组 h 审计交叉核对 | 已实装 |
| 9 | benchmark 测评基准 | 合成测评集（结构化号码召回 ≥99.5% 实测 100%、CPU 2000 字 <100ms）；「多基线对比与人名/住址 NER 的 F1 验收门为规划项」（README.md:13） | 实测 372 用例双跑字节级一致（seed 20260928）、15 份 docx/xlsx/pdf 夹具 sha256 全中、校验位复算过、26 难负例独立无效；m8_quality 已实现（需 :9004 真实上游，离线=DEFERRED 不计失败）；m8_baselines 未实现（CONTRACTS.md:149 痛点#2 如实登记规划态，evals/ 无该文件） | benchmark/generator/build.py:26；evals/m8_quality.py:6；CONTRACTS.md:149；m8_generator 4/4 | 部分实装（基线对比规划态） |
| 10 | webui 演示前端 | webui/ 演示前端页面（README.md:29），五页 + 双屏对照 + 看板 | 实测 5 页面 200、演示材料下载（docx 往返全等/扫描件走 scan_pdf/HIGH 3 枚身份证全命中）、inspect FileReport risk=MID、export 重开零残留、看板回环闸 403/200、admin key 硬闸、SSE 闭环 25 帧/[DONE]/零占位符泄漏 | webui/pages.py:1-32；webui/dashboard.py:20（SVG 文本 escape）；m9_webui 16/16 | 已实装 |
| 11 | ops 运维/验收 | 名称守卫、克隆脚本、e2e 冒烟、公开导出（README.md:30）；八个门脚本 | e2e_smoke 八用例 U1–U8 实跑全过（31 个 chat 请求，U8 真实大模型腿）；name-lint 146 文件 0 违规（m0 内）；八门脚本结构走查确认（标准库、任意 cwd、超时预算 900–5400s）；遗留：S2 后整门 gate_final 未取得 9/9（evidence/gate-final-20261002.md §7.3 自认）、demo 场景 1-3 脚本待补（ops/demo/README.md:7-14，仅 scene4/5 成文） | ops/e2e_smoke.py；ops/gate_final.py:24-46；m10_e2e 8/0/0 | 已实装（整门判定遗留） |
| 12 | evals 验收入口 | 可执行验收入口（python -m evals.*，exit 0 = 通过）（README.md:31），共 19 个入口 | 19 个入口中 16 个在本盘点周期实跑全绿（见第四节）；u8_repro/m8_quality 因无真实上游 key 未跑（未验证）；t0_mock_upstream 辅助库未单独跑（其能力已被 t0_gateway/t0_stream/m10_e2e 反复行使）；阈值单一来源 evals/thresholds.py（98 行常量）与 spec 一致 | evals/thresholds.py；16/16 模块 PASS（第四节） | 已实装 |
| 13 | gpu 部署脚本 | 「部署/保活见 gpu/」（config/app.yaml:13） | 走查确认：权重经 `LLM_HF_REPO` 环境变量下载、未设置即报错退出（模型名不入仓库）、保活循环装载中不杀护栏；脚本未在本机执行（无 GPU 环境）——**未验证** | gpu/setup_llm_service.sh:9-12；gpu/llm_keepalive.sh:8-10 | 已实装（部署侧；运行未验证） |
| 14 | gpu-services/llm_openai | GPU 机本地大模型 OpenAI 兼容服务（FastAPI，:9004，政务网关批次 6 上游）；internet_real/govcloud_real profiles（config/app.yaml:18-19） | 静态稿判「本会话未起服、运行面未验证」；实测稿记录 m10_e2e U8 经 :9004（ssh 隧道 anolis-gpu-tailnet，服务为既有基础设施、非实测组拉起）真实推理 PASS、双腿 key 指纹 09176d9b≠fb073764、回复占位符零泄漏——服务运行面有实测证据（作为客户端被真实行使），部署脚本本身仍为走查级 | gpu-services/llm_openai/service.py:27-31（Authorization 只记 sha256 前 8 位指纹）；m10_e2e U8 | 已实装（部署侧；U8 实测佐证，部署脚本未验证） |

> 附：`out/public-export/` 按 `ops/export_public.py` 导出产物对待、`_upstream/` 按上游来源快照对待，均未逐文件走查（静态稿声明）。

## 三、验收套件实测记录

执行方式（实测稿）：工作区根执行 `python wf_run.py venv -m evals.<模块名>`——`wf_run.py` 直调 `gov-anon-gateway/.venv/Scripts/python.exe`，cwd=仓库根；stdout 首行 `[wf_run] log=<日志路径> exit=<退出码> secs=<秒>`，详细日志在 `gov-anon-gateway/tmp/wf/`。exit 0 = 通过。执行窗口 2026-10-03 20:08–20:45。

| # | 模块 | 退出码 | 用时 | 关键结论 |
|---|---|---|---|---|
| 1 | m0_infra | 0 | 37s | **PASS 20/20**：config listen=9000、4 上游、ai_label=「本内容由AI生成」；3 部门 sha256 有效；name-lint 146 文件 0 违规；Finding/RouteDecision/AuditEvent/FileReport/ApiError 等契约模型 JSON 往返全过（含 env-override 负例、9+3 契约负例） |
| 2 | m2_recognizers | 0 | <1s | **PASS 6/6**：372 用例；结构化号码 micro recall=**1.0000（618/618）**；白名单 FPR=0/22；2000 字检测均值 **1.99ms** < 100ms |
| 3 | m2_semantic | 0 | 2s | **PASS 11/11**：直接/间接/工具描述注入召回均 **1.0000** ≥0.9；正常公文误拦 **0/45**（含否定句式陷阱）；2000 字 0.54ms < 50ms |
| 4 | m3_masking | 0 | 3s | **PASS 9/9**：1000 值重放一致、跨会话互异、还原往返精确；流式 500 组切块还原==整段；**10 万次插入 0 碰撞**（8→10→12 自动升位）；还原均值 **0.259ms** < 20ms |
| 5 | m4_routing | 0 | <1s（补记复跑实测 0s） | **PASS 43/43**：路由矩阵（批量 ≥3→GOVCLOUD、单 PII→INTERNET 脱敏出网、密级→BLOCK、白名单不计数）+ 纯函数 + §5.2 契约 + 阈值可配（下限钳 1）全过 |
| 6 | m5_outguard | 0 | 9s | **PASS 13/13**：密级 403 文案==文案库模板（流/非流同源）；AI 标识三形态 + 自定义文案生效 + 空文案零注入；工具调用 content=null 标识；moderation hook flag 审计 |
| 7 | m6_filesvc | 0 | 40s | **PASS 12/12**：15 份夹具命中 **82/82**；docx 四位面 7/7 精确定位；xlsx 隐藏列/行/批注 13/13；pdf bbox==charbox 并集；三导出引擎 re-inspect **零残留**；50MB/种类/畸形全拒 |
| 8 | m6_ocr | 0 | 202s | **PASS 6/6**：3 份合成扫描件身份证+手机号命中 12 处，OCR 身份证召回 **12/12=1.00** ≥0.9；bbox 与绘制行 y 带相交；导出「渲染→黑框→整页重栅格化」再 OCR **零残留**；零命中件 pdf-noop 字节原样 |
| 9 | m7_audit | 0 | 6s | **PASS 17/17**：SQLite WAL；泄漏原值事件 pre-enqueue 拒收（0 行入库）；库文件 bytes 级扫描 65536B **0/7 原值命中**；会话 LRU 复活/TTL 过期；admin API 401 负例/分页/13 项指标手算全等；report.csv 5707 字节零明文 + 公式注入防护 |
| 10 | m8_generator | 0 | 5s（补记复跑实测） | **PASS 4/4**：372 用例双跑**字节级一致**（seed 20260928）；15 份 docx/xlsx/pdf 夹具 sha256 全中；身份证/USCC/Luhn 校验位复算全过；26 难负例独立无效 |
| 11 | m9_webui | 0 | 34s（补记复跑实测） | **PASS 16/16**：5 页面 200；材料下载（docx 往返全等/扫描件 pdf→scan_pdf/HIGH 3 枚身份证全命中）；inspect risk=MID；export 重开**零残留**（X-Report-Id=file_3edc23d9bb7f5290）；看板回环闸 403/200；admin key 硬闸；SSE 闭环 25 帧/[DONE]/零占位符泄漏 |
| 12 | m10_e2e | 0 | 86s | **PASS 8/0/0**：e2e_smoke 八用例 U1–U8 全过，共发 **31 个 /v1/chat/completions**——U1 非流式往返（上游全文=原文脱敏版）/U2 流式+20 次随机切块重放全等/U3 真实文件三路由/U4 工具参数还原+历史 tool_calls 藏密级 403/U5 审计 27 行+库级 77824B 零明文+report.csv/metrics 交叉核对/U6 文件体检导出零残留/U7 注入拦截（干净版放行、埋注版 403 INJECTION+flag）/U8 **真实大模型腿 PASS**（:9004 双腿真实推理、key 指纹 09176d9b≠fb073764、回复占位符零泄漏） |
| 13 | m11_robust | 0 | 66s | **PASS 7/0**：>10MB 两形态 413（chunked 排空后应答）；深嵌套/数组体/非法 JSON→400；超帽单行 400、帽内 15 万字符 200；50MB 上传三闸 413；非法 SSE 四模式有界终止（12MB 行洪泛客户端仅收 292 字节）；**50 并发零串扰**（批 27.7s，库 73728B 零明文）；事后 healthz+流式全链仍绿 |
| 14 | t0_gateway | 0 | 15s | **PASS 15/15**：401 信封/400 校验/普通往返（上游 bytes 级零原值）/会话稳定占位符（同会话恒同、跨会话互异）/批量 GOVCLOUD 走 8902/密级 403 两 mock 零感知/审计预览占位符版/零明文硬闸/出站全量检测面/会话属主绑定/上游不可达 502 |
| 15 | t0_stream | 0 | 10s | **PASS 14/14**：流式还原 byte-exact+标识三形态；stream=true 密级→403 JSON（非 SSE）；工具参数 hold-to-finish 单 delta 还原；500 组切块 fuzz==整段还原；mid-UTF-8 字节级切分；19 种残缺占位符形态逐字节还原 |
| 16 | t0_labels | 0 | 21s | **PASS 8/8**：docs/contracts/labels.md 结构/19 实体类中文标签/9 子类型/词表与加载器引用/国标对齐/不确定性标注（12 处显式标记）全过；name-lint 0 违规 |

**合计：16 通过 / 16 尝试**（模块总用时约 8.7 分钟），无一失败、无一重跑修复；m4/m8_generator/m9_webui 为补记精确用时复跑 1 次，结果一致。

**按要求跳过项（SKIP，未计入尝试）**：
- `evals.u8_repro`、`evals.m8_quality`：**SKIP**——需真实上游大模型 API key，本环境没有，按要求未尝试（**未验证**）。
- `evals.t0_mock_upstream`：辅助库，按要求未单独跑（其能力已被 t0_gateway/t0_stream/m10_e2e 反复行使）。

**跨会话佐证注**：静态盘点会话另独立复跑 6 个模块（m0_infra 20/20、m2_recognizers 6/6、m2_semantic 11/11、m3_masking 9/9、m4_routing 43/43、m7_audit 17/17，均 exit 0），结论与实测稿一致。两会话延迟类数字略有差异（2000 字检测 3.21ms vs 1.99ms、语义检测 1.36ms vs 0.54ms、还原 0.437ms vs 0.259ms），属不同时点各自实测，均远低于阈值，非矛盾。

## 四、网关实跑冒烟记录

独立于验收套件，真实进程 + 真实 TCP（实测稿第三节的 8 组业务请求；样例文本/号码全部取自 `evals/t0_gateway.py` 公开合成夹具，非真实个人信息）。

**环境与启动（读码确定，未改任何配置文件）**：
- 网关 `python -m gateway --host 127.0.0.1 --port 18731`（改端口无需改配置，gateway/__main__.py:26-38；亦支持 `ANONGW_LISTEN` env 覆盖，common/config.py:94-105）；mock 上游 `python -m gateway.mock_upstream --port 8901 / --port 8902`（独立进程，端口隐含实例名与模型名）。
- `MASK_KEY` 为环境变量必需（缺失即 RuntimeError，gateway/app.py:225-229）；本次注入 64 位演示掩码值（evals/t0_gateway.py:66 声明的公开夹具同款，值不写入本报告）。部门 key 采用 `.env.example` 文档化的公开演示值；「演示明文的 sha256 与 config/dept_keys.yaml 中民政局摘要一致」的断言在 t0_gateway fixtures 步骤执行且 PASS。上游 `MOCK_KEY` 为公开夹具值。
- 落库重定向：经 `ANONGW_AUDIT_DB` / `ANONGW_SESSION_DB` 官方覆盖机制（common/config.py:94-105，m0 有专项验证）指向 `盘点/工作稿/tmp_smoke/`，避免写仓库 data/。
- 启动实测：netstat 确认 8901/8902/18731 均 LISTENING；gateway.log 首条 `gateway.start ... upstreams=[internet_mock, govcloud_local, internet_real, govcloud_real]`。

**逐请求实测（0 为健康检查/模型列表，a–h 共 8 组业务请求，全部真实 HTTP）**：

| # | 输入要点 | 路由/处理 | 结果 |
|---|---|---|---|
| 0 | GET /healthz、/v1/models | — | 200/200；`{"ok":true,"service":"gov-anon-gateway"}`；models 含 mock-chat(INTERNET)/gov-chat(GOVCLOUD)/local-chat-8b×2（带 route 标签、仅名字） |
| a | 普通对话：全镇防汛工作会议通知类文本（合成夹具） | **INTERNET**→:8901 | 200；响应头 `x-anongw-ai-label: 1`；正文尾注「本内容由AI生成」在位；首请求时延 682.8ms（含会话建库） |
| b | 居民信息文本，含身份证+手机号（合成夹具） | **INTERNET**→:8901 | 200；`/internal/detect` 识别明细 PERSON/ID_CARD/PHONE_MOBILE（手机号分隔符写法已归一化）；客户端拿到**还原版**（原值在位、占位符形状零残留）；mock 上游 bytes 级实测：原身份证/手机号**零命中**，收到 `〔人名·…〕〔身份证·…〕` 类占位符 |
| c | `/internal/anonymize` → `/internal/restore` 往返（session=smoke_roundtrip） | 调试端点（部门 key 鉴权） | 200/200；masked 含 2 条映射；restored 与原文**逐字全等** |
| d | 同 b 文本，stream=true | **INTERNET**，SSE | 200；`text/event-stream` 28 帧；逐 delta 拼接后原值完整在位、占位符零残留、尾注在位；finish 帧原始 JSON 带 `annotations:[{"type":"ai_generated","text":"本内容由AI生成"}]` |
| e | 密级标识文本（合成夹具「机密★…不得外传」） | **BLOCK**，不转发：8901/8902 delta 均 0 | **403**；`error.code=content_blocked`；reasons 含 CLASSIFICATION_MARK 两条（命中「机密★」「不得外传」） |
| f | 无 key / 错 key / 跨部门复用会话 | 鉴权闸 | **401/401/403**：无 key、错 key→401 unauthorized 信封；民政局先绑定会话后另一部门 key 复用→403（会话属主绑定生效） |
| g | 批量：3 个合法身份证+1 手机号（合成夹具） | **GOVCLOUD**，仅 :8902 +1（8901 零新增） | 200；客户端还原完整；:8902 bytes 级原身份证**零命中**、`〔身份证·` 占位符在位 |
| h | `/admin/api/audit` 审计交叉核对 | 管理面 | 401/200：无 key 401；部门 key 200，`total=6` 与本次 6 个审计型 chat 请求一致；BLOCK 事件 blocked=true；GOVCLOUD/INTERNET 路由分布正确；预览均为占位符版、无原值 |

**冒烟结论**：全部 8 组请求行为与设计一致——PII 出不了网（上游 bytes 级零原值）、客户端无损还原、密级直接拦截、鉴权与会话属主闸生效、AI 标识三形态在位、审计只存脱敏预览。

**待核数字注**：实测稿 §3.1 事后核实 `tmp_smoke/audit.db` 落 **7 事件（1 拦截）**，而组 h 实时查询 `total=6`；两处相差 1，工作稿未解释，**待核**。

**进程清理（按 PID，实测确认）**：taskkill 网关与 mock 进程；终态 netstat 过滤 8901/8902/18731 无任何残留（SMOKE_PORTS_ALL_FREE）；本机遗留 3 个 python 进程经 wmic 核实为 `python -m pytest`（非本组拉起，未动）；:9004 的 ssh 隧道为既有基础设施，未动。

**过程观察（如实记录）**：
1. 8901 首次绑定失败（TIME_WAIT 残留，winerror 10048），约 1 分钟后重试成功——测试环境端口时序问题，与被测代码无关。
2. 流式 annotations 首跑经冒烟客户端采集为 None，与 t0_stream 14/14 PASS 矛盾；以帧级原始 JSON 复核确认 annotations 确在 finish 帧——客户端采集写法问题，产品行为正常（以原始帧证据为准）。
3. 冒烟前发现 :8911/:8912/:8913/:9012/:9013 仍被 PID 11844（`python -m evals.m11_robust`）监听，其创建时间 20:34:47 与本组 m11 运行窗口（20:23:14–20:24:20，据 wf 日志时间戳）不符、来源不明（非本组进程）；数分钟后自行退出、端口全部释放，未干预，存疑记录。

## 五、声明与现实的差距

### 5.1 文档与代码不一致（静态稿实测核对，共 6 条）

1. **CONTRACTS.md 痛点#1 已过时**：docs/assets/CONTRACTS.md:148 仍称「`_iter_string_leaves` 只递归 dict 的 values，字符串键不进检测面」为待批变更候选；但代码已实现键检测/换名（gateway/pipeline.py:172-192 的 `include_keys` 参数、:220/:231/:238 调用、:242-257 键换名），S2 修复 #2 亦声明「保留，行为有 eval 佐证」。契约痛点表未按其自身变更流程（CONTRACTS.md:153-162）回填裁决。
2. **labels.md 流式缓冲字长滞后**：docs/contracts/labels.md:149 写「≤32 字符缓冲」；代码与 masking spec 均为 48（masking/mapper.py:63-65、masking/remap.py:39-41、docs/assets/REGENERATE.md:106-108）。
3. **REGENERATE.md 旧仓库路径**：docs/assets/REGENERATE.md:17,55,61-63 写旧路径 `D:/workspace/澄迈8项目/政务AI脱敏网关/repo`；当前实际为 `D:/new-workspace/澄迈项目/政务AI安全/gov-anon-gateway`，命令需换路径执行。
4. **pyproject.toml 的 tests 痕迹**：pyproject.toml:65（packages.find include `"tests*"`）与 :77（`testpaths=["tests"]`）指向不存在的 `tests/` 目录（实测无该目录）；实际验收体系为 `evals/`。轻微不一致，不影响运行。
5. **README.md:15「仓库结构（建设中）」**：与 manifest.md 各模块全部 `frozen` 的状态表述存在时态差——陈旧措辞，非错误声明。
6. **quality_report.json 数值随轮次刷新**：evidence/gate-final-20261002.md:197 记 9/9 认证运行 f1_masked=0.9971、S2-A 记 1.0；在盘文件实读 `f1_masked_mean=0.9943`（mtime 2026-10-03 19:49，evals/m8_quality.py:93 每次运行刷新）。属设计行为，但引用数字必须注轮次。

### 5.2 声明为「未实装/规划/未实测」且与代码一致（如实声明，列出供对照，非差距）

- NER 适配器恒空（recognizers/ner/adapter.py:29-31）——README 如实声明预留位；开放域人名/住址现依赖 4 个演示名词表+姓氏启发式 0.5 置信度（docs/assets/feedback.md:91-95 R1 自认「演示人名现场穿帮」风险）。
- m8_baselines 未实现——README.md:13、CONTRACTS.md:149、benchmark-generator.md:49-55 三处如实登记规划态。
- 输出复检后端 NullModerator 恒 safe、`moderation_model` 留空（config/app.yaml:27）——outguard spec 声明 P0 占位/P1 规划，接口与调用点已接线。
- docker-compose.yml 未实测——文件头 :6-7 自报（构建环境无 Docker），README.public.md §4 同步声明。
- preserve_semantic 字段无消费方（恒 False）——CONTRACTS.md:150 痛点#3 自认「形同虚设」，语义保留替换为 P1 规划。
- 演示场景 1-3 脚本待补（ops/demo/README.md:7-14，仅 scene4/5 成文）。
- 公开导出面的 `_BY_DEPLOYER_` 占位为导出语义设计，非缺陷（README.public.md:103-106）。

### 5.3 README 量化声明核对总结论

静态稿对 README 全部 18 条量化/能力声明逐条核对（静态稿 §4 表），结论均为「有测试支撑」或「如实声明的未实装项」，**未发现声明与实测相悖的能力夸大**；其中召回 100%、延迟、会话稳定、流式还原、工具还原、注入拦截、审计零明文、路由矩阵 8 项在静态会话实跑复现，其余各条的支撑在本实测会话 16 模块全量复跑中覆盖（含 e2e、webui、OCR、健壮性）。

### 5.4 两稿差异对照（如实并列，待核）

| 事项 | 静态稿口径 | 实测稿口径 | 判定 |
|---|---|---|---|
| m4_routing 内部构成 | 「38 矩阵格 + 5 横切」 | 「路由矩阵 39 例 + 纯函数 + 契约 + 阈值可配」 | 两稿总量均 43/43 PASS；内部分项记法不一致（38+5 vs 39+4），**待核** |
| 延迟数字 | 2000 字 3.21ms / 语义 1.36ms / 还原 0.437ms | 1.99ms / 0.54ms / 0.259ms | 不同会话各自实测，均远低于阈值，非矛盾 |
| gpu-services 运行面 | 「本会话未起服、运行面未验证」 | m10_e2e U8 经 :9004 真实推理 PASS | 互补而非矛盾：服务运行有实测证据（客户端行使），部署脚本/本机起服仍未验证 |
| 时间线交叠 | 观察到 tmp/wf 最新日志为 20:20 的 evals.m10_e2e（无结果行）与 19:49 的 quality_report.json 刷新，判「工作区非静态快照」 | 本组 16 模块运行窗口 20:08–20:45 | 时间窗重叠，静态稿所见并行活动**很可能即实测组的运行**——此为推断，两稿未互相指认，**待核**；实测稿自身亦记录一个来源不明的 m11 进程（PID 11844，创建 20:34:47），存疑如实记录 |
| gpu-services 代码行数 | §2 表记 737 行，§3.14 记 732 行 | — | 静态稿内部两处记法不一，不影响结论，**待核** |
| 冒烟审计事件数 | — | §3.1 事后核实库文件 7 事件（1 拦截）；组 h 实时查询 total=6 | 同稿内两处相差 1，未解释，**待核** |

## 六、风险与未知

### 6.1 安全/配置隐患（静态稿 §5.3，均为设计内或已声明缓解，如实记录）

1. **演示凭据入仓**：三个演示部门 key 明文写在 `.env.example:21-24` 注释，并以常量存在于仓内 evals/ops 脚本；README.public.md:122-128（S2 修复 #8）已声明「生产部署必须更换哈希」——风险成立与否取决于部署纪律。
2. **会话库明文原值**：`data/session_map.db` 按设计必须存归一化原值（masking/session_store.py:14-17），落盘为**未加密 SQLite**；文件泄露=占位符全量反查。缓解=与审计库分文件（审计库可零明文扫描）、跨部门还原 403、TTL 24h；at-rest 无静态加密为残余风险。
3. **MASK_KEY 全零占位**：`.env.example:7` 提供全零占位；resolve_secret 只查存在性（common/config.py:140-144），部署者忘改不报错，占位符密钥即退化为可预测值。
4. **/v1/files/* 两端点不鉴权**（gateway/app.py:285-364）：向任意调用方提供检测能力（findings 明细含 raw 回显）与导出能力；设计口径为报告 raw 是上传者自带文件回显、生产部署应置于管理面/内网（README.public 与 gateway-main-chain.md §5 注明）；若绑外网地址即为暴露面。
5. **/internal/* 含还原原文**：已有部门 key+属主绑定+SESSION_ID_RE 形态闸（gateway/app.py:101-104,518-525），README.md:38-41 明示不得直接暴露公网——依赖部署纪律。

### 6.2 工程脆弱点（静态稿 §5.4）

6. **33 个文件修改未提交（最高优先）**：含全部 S2 安全修复（gateway/pipeline.py、masking/mapper.py、audit/store.py、common/config.py 等）与 GPU 服务脚本；evidence/gate-final-20261002.md:268 自认漂移风险——工作区一次误操作即丢失已验收代码态。
7. **整门 gate_final 在 S2 修复后未取得 9/9**：S2-A 1/9 FAIL（瞬时 U1 ConnectTimeout+U5 KeyError）、S2-B 2/9 FAIL（:9004 隧道中途掉线→DEFERRED 政策连环）（evidence §7.3 表）；11 条修复的逐模块 eval 全绿（含本实测 16/16），但「9/9 整门+四项质量指标写入验收 JSON」的遗留动作未完成。
8. **真实链路单点依赖 :9004 隧道**：隧道掉线已两次导致整门 FAIL（evidence 留档）；docs/assets/feedback.md F4 自认并给出 mock 主口径+预录兜底缓解。
9. **规则层固有边界**：WEAK 语义注入靠位置启发、词表类为静态词表（密级词表仅 6 词、人名词表仅 4 个演示名+姓氏启发式 0.5 置信度，labels.md §9-6 与 feedback.md R1 自认）；词表外新词漏检属规则层边界。
10. **端口竞争约束**：9000/8901/8902 等端口独占，多批次并行跑门冲突（REGENERATE.md §4）；本盘点期间两处端口残留/来源不明进程的观察佐证其现实性。

### 6.3 未知/未覆盖面

11. **u8_repro 与 m8_quality 未验证**（需真实上游大模型 key，本环境没有）——质量比承诺（thresholds QUALITY_RATIO_MIN）与真实模型质量面本轮无直接实测；历史轮次落盘 quality_report.json（ratio=1.0、f1_masked_mean=0.9943、50 对）为留档证据，非本轮复现。
12. **internet_real / govcloud_real 直连形态未单独验证**（无 key）；其能力经 m10_e2e U8 的 :9004 真实推理腿覆盖。
13. **OCR 泛化未验证**：召回基于 3 份合成扫描件（12 处身份证），真实扫描件未测。
14. **e2e 离线 DEFERRED 分支未实测**：本轮两稿记录的 e2e 运行 U8 均真实跑通（0 DEFERRED），「无真实上游时 U8 如实 DEFERRED」的离线分支行为未在本盘点出现/验证。
15. **性能数字为单机单次实测**（1.99ms/0.259ms/50 并发批 27.7s 等），未多机复现。
16. **docker compose 未实测**（本机无 Docker，项目自报未实测）；gpu/gpu-services 部署脚本未执行。
17. **webui 页面人工交互与 admin CSV 人工点验未做**（由 m9_webui 16 项/m7_audit 17 项自动化覆盖）。

## 七、本盘点的局限

1. **eval 覆盖**：19 个入口中 16 个实跑全绿（16 尝试/16 通过）；3 个未跑——`u8_repro`、`m8_quality`（需真实上游 key，环境没有，按要求未尝试）、`t0_mock_upstream`（辅助库，按要求未单独跑）。前两者相关能力为**未验证**。
2. **未执行**：docker compose（环境无 Docker）；gpu/gpu-services 部署脚本与 :9004 服务的本机起服（无 GPU 机）；`ops/gate_final.py` 整门（小时级墙钟且明示勿在窄窗口启动；其判定以 evidence/gate-final-20261002.md 留档为准，S2 后未取得 9/9）。
3. **未读取/未走查**：`.env` 内容（红线：真实密钥值不入报告）；`_upstream/`（上游来源快照）与 `out/public-export/`（导出产物镜像）未逐文件走查。
4. **两稿互补关系**：静态稿曾留「11 个 eval 未复跑」的缺口，已被实测稿 16 模块全量实跑补齐；静态稿独立复跑的 6 个模块与实测稿结论一致，互为佐证。两稿均无「为通过而改代码/配置」情形（实测稿 16/16 一次通过，无重跑修复记录）。
5. **工作区非静态快照**：盘点期间存在并行 eval 活动（静态稿观察）与一次来源不明进程（实测稿观察），各数字归属各自会话，未做跨会话归一；交叠推断见 §5.4，待核。
6. **冒烟覆盖范围**：冒烟覆盖 chat/流式/内部端点/审计主链路，未含文件通道入口（/v1/files/*）的人工点验（由 m6_filesvc 12 项、m6_ocr 6 项、m9_webui 16 项自动化覆盖）。
7. **本报告为合成产物**：所有「实测/走查」证据均出自两稿会话，本合成会话未重新执行任何 eval 或冒烟；文中行号为静态稿实读时点。
