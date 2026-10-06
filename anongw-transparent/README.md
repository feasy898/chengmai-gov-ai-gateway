# anongw-transparent（无感脱敏壳代理）· M1 T1 竖切

> 对象：把 gov-anon-gateway 引擎（本仓，识别-可逆脱敏-路由-审计）包成**客户端无感**的本机工具。
> 依据：`docs/workspace-planning/规划/开发规划-v1.md` §四 M1（改动面/验收）与 `规划/测试计划-v1.md`
> （T1·A 接入层 / V3-01 / V4-01 口径）；通道可行性前置证据：`docs/workspace-planning/M0-实验报告.md`（9ccd52d）。
> 本 README 不含任何密钥明文；key 只经环境变量传递。

## 形态与拓扑（T1：回环 baseURL 直配）

```
agent/curl ──HTTP(明文回环)──▶ anongw-transparent 壳(:8720) ──▶ 引擎网关(:9000) ──▶ 上游(zhipu/mock)
                                │ 恒定注入 x-anongw-session-id = 安装实例标识
                                │ 注入本地网关鉴权头（值取 env ANONGW_GATEWAY_KEY）
                                │ SSE 字节零改写中继；泄漏计量在帧组装后
                                └─ /anongw/stats：运行时泄漏计数器出口
```

- 识别/脱敏/还原/路由/审计**全部归引擎网关**（规划 §三h「零引擎代码改动、多一跳回环」；本竖切对引擎
  仅动配置层：运行脚本以 env 覆盖 `ANONGW_SESSION_TTL_H=720`）。
- 值级键语义（规划 §三b）：安装实例标识喂进引擎 digest 公式的 session 槽——**同值在本机任何时候恒同
  占位符**，跨轮/跨进程/跨重启不漂移（跨重启持久化归 M3，本阶段实例标识已持久化）。

## 目录

```
anongw-transparent/
  anongw_shell/            壳包
    config.py              env 配置（ANONGW_SHELL_* 前缀；key 只存「环境变量名」不存值）
    identity.py            安装实例标识生成与保管（data/instance.json，0600，原子写；
                           损坏即报错不静默换新——静默换标识=旧占位符全变孤儿）
    leakmeter.py           运行时泄漏计数器（内核=引擎 masking.mapper.tolerant_placeholder_hits，
                           复用不造平行实现；证据串只含占位符形状键，零明文）
    relay.py               流式转发中继：数据面字节零改写；计量面 SSE 组帧 →
                           delta.content 按到达顺序拼接（通道级组装）→ 流收尾一次计量
                           （M0-实验报告 §2.2-1 教训：对原始分片/单帧检测会系统性假阴）
    server.py              回环监听（V1-01：非回环默认拒绝）+ 恒定头注入 + 转发 + 计量
    __main__.py            python -m anongw_shell
  anongw_evals/            验收组（包名裁定见下「与测试计划的偏差」）
    thresholds.py          本工具阈值唯一来源（V2-06：每常量被消费；无单机单次实测数作阈值）
    _portalloc.py _harness.py   基床：端口自分配 + 三层栈 fixture
    t1_shell.py            T1·A 接入层壳单测（V1-01/02/03/04/06/07 + stats 可见性）
    t1_roundtrip.py        V3-01 三轮值级恒同 / 归一化等价 / 泄漏=0 / V0-05 计数链 /
                           V1-11 错还原负例 / V7-01(lite) 审计零明文
    t1_e1_quick.py         E1 服从性快测（echo 服务 + CONNECT 代理 + HTTPS_PROXY 服从性）
    t4_perf_ttft.py        TTFT 增量差值法（V4-01：A/B 交错配对、每请求新建连接、排空纪律）
  ops/
    run_local.sh           本地一键演示（mock 腿，零 key 零外呼）
    acceptance_zhipu.sh    M1-#1 验收：curl 三轮对话（zhipu 直连上游）
  data/                    运行态（instance.json 等；仓 .gitignore data/ 规则覆盖，不进仓）
```

## 快速开始

```bash
cd <仓根>
python3 -m venv .venv && .venv/bin/pip install fastapi uvicorn[standard] httpx pydantic \
    pyyaml jinja2 python-multipart python-docx openpyxl   # 或对照 constraints.txt 钉版本

# mock 腿演示（零 key）：
bash anongw-transparent/ops/run_local.sh

# M1-#1 验收（zhipu 直连上游；key 经 agent-tools/llm-env 取，不落盘）：
bash anongw-transparent/ops/acceptance_zhipu.sh
```

Agent 接入（T1）：把 agent 的 endpoint/baseURL 配到 `http://127.0.0.1:8720/v1` 即可——客户端
不需要知道会话头、部门 key、脱敏的任何存在。

## 验收组运行

```bash
cd anongw-transparent
../.venv/bin/python -m anongw_evals.t1_shell        # exit 0 = 过（1 项显式 SKIP：V1-05 属 M2）
../.venv/bin/python -m anongw_evals.t1_roundtrip    # exit 0 = 过
../.venv/bin/python -m anongw_evals.t1_e1_quick     # exit 0 = 过（Node 服从性行为如实矩阵行）
../.venv/bin/python -m anongw_evals.t4_perf_ttft --upstream mock --pairs 200   # 预算对照
```

**包名裁定**（测试计划遗留开放问题「wf_run.py 是否扩展到新仓」）：引擎仓顶层已有 `evals` 包
（`gateway/app.py` 等引擎源码 `import evals.thresholds`），壳验收组若同名会同进程撞名——故平行
命名 `anongw_evals`，单文件 / exit 0 / 阈值单源三惯例不变；`wf_run.py` 本仓不存在（基线编排器
未随迁移），不另造。

## F1–F8 分叉：本阶段采纳规划推荐默认（**owner 可推翻**）

出处：开发规划-v1.md §5.2。下表「默认」即本仓当前行为；owner 拍板推翻时改对应配置/代码即可，
不用动引擎内核。

| # | 分叉 | 本阶段采纳（=规划推荐） | 落点 |
|---|---|---|---|
| F1 | 买方形态：统管 vs 自装 | **按单用户自装工具做 v1** | 全局（无部门绑定面进壳层） |
| F2 | 值级键隐私让步（本机内跨会话可关联） | **接受**（每安装实例独立命名空间；跨实例恒异已由引擎 digest 语义保证） | `anongw_shell/identity.py` + 引擎 session 槽 |
| F3 | 拦截/状态可见性 | 透传形态不注 AI 标识、密级显式拦截（引擎既有行为透传）；托盘提示 M5 | 引擎 outguard 原样 |
| F4 | 目标 agent 清单 | 种子清单 zcode、kimi + Claude Code/Cursor BYO/Cline/Aider 各一；**M1 未接入任何真实 agent**（见下「M1 未做」） | M2 矩阵 |
| F5 | 映射保留期/托管 | **TTL 720h（30 天）+ 容量上限（引擎 SessionStore 1024 会话）**；DPAPI 静态加密归 M3 | `ops/*.sh` 的 `ANONGW_SESSION_TTL_H=720` |
| F6 | 占位符形态 bake-off | **维持全角标签·digest 现状**（M2 实测形态差异为噪声） | 引擎 mapper 原样 |
| F7 | 真实语料/词表授权 | 未授权 → E3/M4 冻结，对外口径按合成实测 | 不适用本阶段 |
| F8 | 还原失败自动补救 | **暂不**：壳只计量+留痕+stats 可见（`leakmeter.py`），不重问不重放 | `anongw_shell/leakmeter.py` |

另：F9 候补（壳故障 fail-open/closed，测试计划登记未裁决）——本阶段按 **fail-closed 默认**实现
（网关 key 未配置 → 503 拒绝转发、上游不可达 → 502 信封，皆可判别不静默，`server.py`），owner 可改。

## M1 验收记录（先测先记，2026-10-06 本机会话）

### M1-#1 curl 三轮对话（zhipu 直连上游，`ops/acceptance_zhipu.sh`）— **PASS**

- 三轮（历史累积多轮、同值手机号跨轮复现）：占位符三轮恒同 `〔手机号·a619c412〕`（值级语义生效）；
- 3/3 轮回复含归一化号码 `13800138000`（基线 §2.2 归一化等价口径，非逐字）；
- 壳泄漏计数：`metered=3 responses_with_hits=0 total_hits=0`；
- 审计库全文件 bytes 级扫描零原值（夹具三值）。
- 运行注记：第 3 轮曾用「原样复述号码」措辞，glm-4-flash 拒绝复述并把占位符改写为
  `435-02d-66`（模型行为边界，非工具缺陷；该形态不具占位符结构，计量面如实 0 命中）——
  改为「读回确认」措辞后 3/3 通过。真实模型的占位符改形/拒答面归 E2 定标（M0 实验）。

### 引擎回归（M1-#3 口径）— **全部 exit 0**

`cd <仓根> && PYTHONUTF8=1 .venv/bin/python -m evals.<模块>`：m3_masking **10/10**、
t0_stream **15/15**、t0_gateway **15/15**、m7_audit **17/17**（2026-10-06，本竖切改动
零引擎源码，回归即冻结基线复核）。

### TTFT 增量（M1-#4，`t4_perf_ttft.py` V4-01 差值法，20KB=bytes 口径）— **p50 达标 / p95 如实红**

| 腿 | n | Δ p50 | Δ p95 | Δ p99 | 判定（规划 §三e：p50≤20ms / p95≤50ms） |
|---|---|---|---|---|---|
| mock（配臂对齐 keepalive=off） | 200 对 | **18.4ms** | **102.6ms** | 197.1ms | p50 ✓ / p95 ✗（如实红） |
| mock（生产形态 keepalive=on） | 200 对 | **14.7ms** | **126.6ms** | 170.5ms | p50 ✓ / p95 ✗（如实红；该轮与 zhipu 验收并发跑，尾部受争用） |
| zhipu 真实腿（keepalive=off） | 100 对 | **14.2ms** | **1610.1ms** | 2550.8ms | p50 ✓ / p95 ✗（p95 被上游方差支配，见下） |

- zhipu 腿注记（如实）：绝对 TTFT 本身在秒级（A p50=2105ms / B p50=2110ms，两臂中位几乎重合），
  配对差值 min/max 跨 -7314～+2972ms——**p95 及以上的尾部被 zhipu 上游方差支配**，在本机/本 n 下
  不构成壳开销的有效测量；p50 是该腿唯一可与预算对照的分位，**14.2ms ≤ 20ms 预算**。

- 方法：A=客户端直连引擎网关、B=经壳，逐对交错采样、每请求新建连接（两臂对齐）、TTFT=首响应
  字节、响应**排空后**才进入下一对（实测教训：只读首字节即断开会把网关流收尾成本甩进下一个
  请求，Δ 系统性假阴 50ms+）、预热 20 对丢弃；预算值取规划 §三e（非单机单次实测数）。
- 如实登记：本机为共享开发机（非测试计划基准门的「专用机」），p95 尾部含 GC/争用噪声
  （min/max 跨度 -357～+257ms）；**不重跑到过**。20ms p50 线的余量问题（测试计划 M3§7.2：
  相对 19ms 实测证据余量仅 1ms）已登记，owner 裁定前按规划原值执行。
- 结论口径：M1 阶段门要的是「V4-01 首批数字」（测试计划 §4.3），预算门终验在 M5 发版前——
  本批数字即为首批，p95 未达标不掩饰。

### E1 服从性快测（`t1_e1_quick.py`，M0 报告 §五.2 建议随手补）— **装置 6/6 过；杀死线未触发**

- 负控：无代理 env 直连 → echo 收到、代理零记录（装置无假阳性面）；
- curl + HTTPS_PROXY：CONNECT 落代理 + 自签 TLS 端到端回显逐字节一致 ⇒ **服从**；
- Node 22 默认栈（zcode 为 Electron/Node 系的代表性面）：`HTTPS_PROXY` 下直连目标、零 CONNECT
  ⇒ **不服从**（Node 核心不读 env 代理；矩阵行如实登记，非门）；
- 杀死线核对：可配 endpoint 类（T1：M0 curl 级证据 9ccd52d + 本仓壳实体）+ env 服从类（curl）
  合计 2 ≥ 2 ⇒ **E1 未被杀死**（开发规划-v1.md:188）。真实桌面/CLI agent 逐个实测归 M2 矩阵。

## M1 未做（如实登记，非本任务范围）

- **M1-#2「zcode/kimi 至少其一 ≥20 轮真实使用」未做**：接入需改 zcode 全局 provider 配置
  （`~/.zcode/v2/config.json`），当前自动化会话自身依赖该配置运行，中途改写有打断风险
  （M0-实验报告 §四.4 同款理由）——按任务指示留给 M1-#2 后续执行。
- V1-05（T2 形态安装/卸载系统快照）SKIP：T2 属 M2；T1 按设计零系统写入（无 CA、无信任库、
  无持久 env），t1_shell 中显式 SKIP 登记不静默。
- V1-08 跨重启档、V1-14（TTL 淘汰）依赖 M3 持久化：本阶段实例标识已持久化，映射持久化未做，
  对应用例未写（非 SKIP 冒充）。

## 安全与卫生

- key 只经 env：`ANONGW_GATEWAY_KEY`（本地网关鉴权）、`ZHIPU_LLM_KEY`（上游）、`MASK_KEY`
  （占位符密钥，运行脚本每次随机生成）——不入配置文件、不入日志、不入审计；泄漏计数器证据串
  只含占位符形状键（`〔标签·hex〕`），零明文。
- 壳只听回环（`127.0.0.1`；非回环 bind 默认拒绝，`ANONGW_SHELL_ALLOW_NON_LOOPBACK=1` 显式
  放行时响亮告警）。
- 实例标识文件 `data/instance.json` 权限 0600；损坏即拒启（不静默换新）。
