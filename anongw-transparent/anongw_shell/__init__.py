"""anongw-transparent 壳代理（T1 形态，M1 竖切）。

无感脱敏工具的入口壳：回环 HTTP 监听 + 流式转发中继 + 恒定注入
``x-anongw-session-id``（安装实例标识，值级键语义）+ 本地网关鉴权头注入
+ 运行时泄漏计数器（复用引擎 ``masking.mapper.tolerant_placeholder_hits``
内核，不造平行实现）。

接法（规划 §三h·M1）：OpenAI 形态流量经壳**转发到本机网关端口**——
识别/脱敏/还原/审计/路由全部归引擎网关（零引擎代码改动），壳只做
入口、身份与计量。流式计量在 **SSE 帧组装后** 的客户端可见文本上做
（M0-实验报告 §2.2-1 教训：对原始分片检测会系统性假阴）。

模块：
- :mod:`anongw_shell.config`    环境配置（``ANONGW_SHELL_*`` 前缀）
- :mod:`anongw_shell.identity`  安装实例标识生成与保管
- :mod:`anongw_shell.leakmeter` 运行时泄漏计数器
- :mod:`anongw_shell.relay`     流式转发中继（帧组装 tap）
- :mod:`anongw_shell.server`    回环监听与转发（FastAPI app）
"""
from __future__ import annotations

import sys
from pathlib import Path

#: 仓根（gov-anon-gateway 引擎库所在）：anongw-transparent/anongw_shell/__init__.py → parents[2]
REPO_ROOT = Path(__file__).resolve().parents[2]
#: 本工具根（anongw-transparent/）：壳与其 eval 包（anongw_evals）的导入根
PKG_ROOT = Path(__file__).resolve().parents[1]

# 引擎库（masking/gateway/...）与本工具包（anongw_shell/anongw_evals）同进程可导入。
# 注意：本工具的验收组包名是 ``anongw_evals`` 而非 ``evals``——引擎仓已有顶层
# ``evals`` 包（evals.thresholds 被引擎源码 import），壳 eval 若也叫 evals 会在
# 同进程里与之撞名（规划/测试计划「编排器是否扩展」开放问题的实施裁定：
# 平行包名，各 eval 仍单文件、exit 0 惯例不变）。
for _p in (str(REPO_ROOT), str(PKG_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

__all__ = ["REPO_ROOT", "PKG_ROOT"]
