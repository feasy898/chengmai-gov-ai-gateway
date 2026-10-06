"""anongw-transparent 验收组（T1 竖切）：t1_shell / t1_roundtrip / t1_e1_quick / t4_perf_ttft。

包名裁定（规划/测试计划开放问题「编排器是否扩展到新仓」的实施口径）：
引擎仓顶层已有 ``evals`` 包且被引擎源码 import（``gateway/app.py`` →
``evals.thresholds``），壳 eval 若同名会在同进程撞名——故本工具验收组
平行命名 ``anongw_evals``，各模块仍守引擎惯例：**单文件、exit 0 = 过、
检查项编号写 docstring、阈值只取 anongw_evals.thresholds**。

运行::

    cd anongw-transparent && ../.venv/bin/python -m anongw_evals.t1_shell
    cd anongw-transparent && ../.venv/bin/python -m anongw_evals.t1_roundtrip
    cd anongw-transparent && ../.venv/bin/python -m anongw_evals.t1_e1_quick
    cd anongw-transparent && ../.venv/bin/python -m anongw_evals.t4_perf_ttft [--upstream mock|zhipu]
"""
from __future__ import annotations

# 导入即完成 sys.path 布置（仓根 + anongw-transparent/）——见 anongw_shell.__init__
from anongw_shell import PKG_ROOT, REPO_ROOT  # noqa: F401
