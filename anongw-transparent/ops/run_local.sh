#!/usr/bin/env bash
# anongw-transparent 本地一键演示（mock 腿，零 key 依赖、零外呼）：
#   mock 上游 :8901/:8902 → 引擎网关 :9000 → 壳 :8720
# 起完后给一条可直接粘贴的 curl。Ctrl+C 全停。key 全走 env（不落盘）。
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TOOL_ROOT="$REPO_ROOT/anongw-transparent"
PY="$REPO_ROOT/.venv/bin/python"
GW_PORT="${GW_PORT:-9000}"
SHELL_PORT="${SHELL_PORT:-8720}"
WORK="$(mktemp -d /tmp/anongw_m1_local.XXXXXX)"
PIDS=()
cleanup() { for pid in "${PIDS[@]:-}"; do kill "$pid" >/dev/null 2>&1 || true; done; rm -rf "$WORK"; }
trap cleanup EXIT INT TERM

export MOCK_KEY="mock-demo-key"
export MASK_KEY="$("$PY" -c 'import secrets;print(secrets.token_hex(32))')"
export ANONGW_GATEWAY_KEY="dk_5e6f7a8b"     # 演示部门 key（仓内文档化）
export ANONGW_SESSION_TTL_H=720              # F5 推荐默认（owner 可推翻）
export ANONGW_AUDIT_DB="$WORK/audit.db"
export ANONGW_SESSION_DB="$WORK/session_map.db"

(cd "$REPO_ROOT" && PYTHONUTF8=1 "$PY" -m gateway.mock_upstream --port 8901) >/dev/null 2>&1 &
PIDS+=($!)
(cd "$REPO_ROOT" && PYTHONUTF8=1 "$PY" -m gateway.mock_upstream --port 8902) >/dev/null 2>&1 &
PIDS+=($!)
(cd "$REPO_ROOT" && PYTHONUTF8=1 "$PY" -m gateway --port "$GW_PORT") >"$WORK/gateway.log" 2>&1 &
PIDS+=($!)
(cd "$TOOL_ROOT" && PYTHONUTF8=1 "$PY" -m anongw_shell --port "$SHELL_PORT" \
  --gateway-url "http://127.0.0.1:$GW_PORT") >"$WORK/shell.log" 2>&1 &
PIDS+=($!)

for i in $(seq 1 60); do
  ok=1
  for port in 8901 8902 "$GW_PORT" "$SHELL_PORT"; do
    curl -sf "http://127.0.0.1:$port/healthz" >/dev/null 2>&1 || { ok=0; break; }
  done
  [ "$ok" = 1 ] && break
  [ "$i" = 60 ] && { echo "FATAL: services not ready"; tail -5 "$WORK"/*.log; exit 2; }
  sleep 0.5
done

INSTANCE="$(curl -s "http://127.0.0.1:$SHELL_PORT/healthz" | "$PY" -c 'import json,sys;print(json.load(sys.stdin)["instance_id"])')"
echo
echo "anongw-transparent 栈已就绪："
echo "  mock 上游 :8901/:8902 → 引擎网关 :$GW_PORT → 壳 :$SHELL_PORT"
echo "  实例标识（恒定会话号，落 anongw-transparent/data/instance.json）：$INSTANCE"
echo
echo "试一下（agent 的 baseURL 直配 http://127.0.0.1:$SHELL_PORT/v1 即接入）："
echo "  curl -s http://127.0.0.1:$SHELL_PORT/v1/chat/completions \\"
echo "    -H 'content-type: application/json' \\"
echo "    -d '{\"model\":\"mock-chat\",\"messages\":[{\"role\":\"user\",\"content\":\"我的手机号是138 0013 8000，请登记\"}]}'"
echo
echo "泄漏计数器：curl -s http://127.0.0.1:$SHELL_PORT/anongw/stats"
echo "（Ctrl+C 全停）"
wait
