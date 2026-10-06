#!/usr/bin/env bash
# anongw-transparent M1-#1 验收（规划 §四M1 验收 #1；测试计划 V3-01 口径）：
#   curl 三轮对话经壳（T1 形态：curl → 壳 :8720 → 引擎网关 :9000 → zhipu 直连上游）
#   断言：同值占位符三轮恒同（值级语义生效）；还原文本与原文归一化等价；
#         运行时泄漏计数 = 0；审计落库零明文（preview 抽检）。
# 红线：key 只经 env 传递（source llm-env），不落任何文件；本脚本零明文输出 key。
# 用法：bash ops/acceptance_zhipu.sh   （可 GW_PORT= PORT= 覆盖端口）
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TOOL_ROOT="$REPO_ROOT/anongw-transparent"
PY="$REPO_ROOT/.venv/bin/python"
GW_PORT="${GW_PORT:-9000}"
SHELL_PORT="${SHELL_PORT:-8720}"
DEPT_KEY="dk_5e6f7a8b"   # 演示部门 key（仓内 .env.example 文档化；YAML 只存 sha256）
MODEL="glm-4-flash"
WORK="$(mktemp -d /tmp/anongw_m1_accept.XXXXXX)"
PIDS=()
cleanup() {
  for pid in "${PIDS[@]:-}"; do kill "$pid" >/dev/null 2>&1 || true; done
  rm -rf "$WORK"
}
trap cleanup EXIT

echo "==[0] key 经 env 获取（不落盘；不回显值）=="
export PATH="$HOME/.local/bin:$PATH"
# llm-env 的用法是 eval 捕获其 stdout 的 export 行（脚本头注「eval "$(llm-env zhipu)"」）；
# source 会把 export 行打印出来而变量不生效——此处按官方用法 eval 执行。
if ! eval "$( /home/pan-ding/workspace/agent-tools/llm-env zhipu )"; then
  echo "FATAL: llm-env zhipu key fetch failed" >&2; exit 2
fi
if [ -z "${LLM_API_KEY:-}" ]; then echo "FATAL: llm-env zhipu key fetch failed" >&2; exit 2; fi
KEY_SHA12="$(printf %s "$LLM_API_KEY" | sha256sum | cut -c1-12)"
export ZHIPU_LLM_KEY="$LLM_API_KEY"
ZHIPU_BASE="${LLM_BASE_URL:-https://open.bigmodel.cn/api/coding/paas/v4}"
echo "key ok (sha256:${KEY_SHA12}…), base=$ZHIPU_BASE, model=$MODEL"

echo "==[1] 起引擎网关（ANONGW_UPSTREAMS 覆盖 → zhipu；F5 推荐 TTL=720h，owner 可推翻）=="
export MASK_KEY="$("$PY" -c 'import secrets;print(secrets.token_hex(32))')"
export ANONGW_UPSTREAMS="[{\"name\":\"internet_zhipu\",\"base_url\":\"$ZHIPU_BASE\",\"api_key_env\":\"ZHIPU_LLM_KEY\",\"models\":[\"$MODEL\"],\"route\":\"INTERNET\"}]"
export ANONGW_SESSION_TTL_H=720
export ANONGW_AUDIT_DB="$WORK/audit.db"
export ANONGW_SESSION_DB="$WORK/session_map.db"
export ANONGW_GATEWAY_KEY="$DEPT_KEY"
(cd "$REPO_ROOT" && PYTHONUTF8=1 "$PY" -m gateway --port "$GW_PORT") >"$WORK/gateway.log" 2>&1 &
PIDS+=($!)

echo "==[2] 起壳（回环 :$SHELL_PORT → 网关 :$GW_PORT；实例标识落 anongw-transparent/data/）=="
(cd "$TOOL_ROOT" && PYTHONUTF8=1 "$PY" -m anongw_shell --port "$SHELL_PORT" \
  --gateway-url "http://127.0.0.1:$GW_PORT") >"$WORK/shell.log" 2>&1 &
PIDS+=($!)

for i in $(seq 1 60); do
  if curl -sf "http://127.0.0.1:$GW_PORT/healthz" >/dev/null 2>&1 \
     && curl -sf "http://127.0.0.1:$SHELL_PORT/healthz" >/dev/null 2>&1; then break; fi
  if [ "$i" = 60 ]; then
    echo "FATAL: services not ready；网关/壳日志尾部："
    tail -n 15 "$WORK/gateway.log" || true
    tail -n 15 "$WORK/shell.log" || true
    exit 2
  fi
  sleep 0.5
done
curl -s "http://127.0.0.1:$SHELL_PORT/healthz" | "$PY" -c 'import json,sys; d=json.load(sys.stdin); print("shell up:", d["service"], "instance:", d["instance_id"])'

echo "==[3] curl 三轮对话（经壳；同值手机号跨轮复现）=="
PHONE_RAW='138 0013 8000'     # 夹具假值（非真实个人信息）
chat() { # $1=请求体文件 $2=输出文件
  curl -sS -X POST "http://127.0.0.1:$SHELL_PORT/v1/chat/completions" \
    -H 'content-type: application/json' --data-binary @"$1" -o "$2"
}
"$PY" - "$WORK" <<'PYEOF'
import json, pathlib, sys
work = pathlib.Path(sys.argv[1])
turn1 = "你好，我叫王建国。我的手机号是138 0013 8000，请帮我登记。"
turn2 = "再确认一下：我叫王建国，手机号是138 0013 8000，对吗？"
turn3 = "最后核对，请把我登记的信息逐字读回来确认：姓名王建国，手机号13800138000。"
hist = []
for i, text in enumerate((turn1, turn2, turn3), 1):
    hist.append({"role": "user", "content": text})
    body = {"model": "glm-4-flash", "stream": False, "messages": hist}
    (work / f"round{i}.json").write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    hist.append({"role": "assistant", "content": "（占位，等回复后填充）"})
PYEOF
declare -a REPLIES=()
for i in 1 2 3; do
  chat "$WORK/round$i.json" "$WORK/reply$i.json"
  code="$("$PY" -c "import json;d=json.load(open('$WORK/reply$i.json'));print(d.get('error',{}).get('code','OK'))")"
  [ "$code" = "OK" ] || { echo "FATAL: round $i error=$code"; cat "$WORK/reply$i.json"; exit 1; }
  REPLIES+=("$("$PY" -c "import json;print(json.load(open('$WORK/reply$i.json'))['choices'][0]['message']['content'])")")
  echo "  round $i reply: ${REPLIES[$((i-1))]:0:80}…"
done

echo "==[4] 断言 A：同值占位符三轮恒同（从网关审计 preview 取占位符）=="
declare -a PHS=()
for i in 1 2 3; do
  curl -sS "http://127.0.0.1:$GW_PORT/admin/api/audit?limit=50" \
    -H "Authorization: Bearer $DEPT_KEY" > "$WORK/audit.json"
  ph="$("$PY" - "$WORK/audit.json" "$i" <<'PYEOF'
import json, re, sys
page = json.load(open(sys.argv[1]))
n = int(sys.argv[2])
events = [e for e in page["events"] if not e["blocked"]]
asc = list(reversed(events))   # /admin/api/audit 固定 ORDER BY id DESC（新→旧），反转后升序
ev = asc[n - 1]                # 第 n 轮（升序第 n 条）
hits = re.findall(r"〔手机号·[0-9a-f]{8,12}〕", ev["prompt_preview"])
assert hits, f"round {n}: no phone placeholder in preview: {ev['prompt_preview'][:120]!r}"
print(hits[0])
PYEOF
)"
  PHS+=("$ph"); echo "  round $i placeholder: $ph"
done
if [ "${PHS[0]}" = "${PHS[1]}" ] && [ "${PHS[1]}" = "${PHS[2]}" ]; then
  echo "  ✓ 三轮恒同（值级语义生效）：${PHS[0]}"
else
  echo "  ✗ 占位符漂移：${PHS[*]}"; exit 1
fi

echo "==[5] 断言 B：还原文本与原文归一化等价（每轮回复含归一化号码 13800138000）=="
ok=0
for r in "${REPLIES[@]}"; do
  case "$r" in *13800138000*) ok=$((ok+1));; esac
done
[ "$ok" = 3 ] || { echo "  ✗ 还原不完整（$ok/3 轮含归一化号码）"; printf '%s\n' "${REPLIES[@]}"; exit 1; }
echo "  ✓ 3/3 轮回复含归一化号码（基线 §2.2 归一化等价口径）"

echo "==[6] 断言 C：运行时泄漏计数 = 0（壳 /anongw/stats）=="
curl -s "http://127.0.0.1:$SHELL_PORT/anongw/stats" > "$WORK/stats.json"
"$PY" - "$WORK/stats.json" <<'PYEOF'
import json, sys
s = json.load(open(sys.argv[1]))
leak = s["leak"]
print(f"  metered={leak['requests_metered']} responses_with_hits={leak['responses_with_hits']} total_hits={leak['total_hits']}")
assert leak["total_hits"] == 0, f"M1-#1 violated: leak counter = {leak['total_hits']}"
print("  ✓ 泄漏计数 = 0（mock/真实腿一致口径，帧组装后计量）")
PYEOF

echo "==[7] 断言 D：审计零明文抽检（audit.db bytes 级扫夹具原值）=="
"$PY" - "$WORK" <<'PYEOF'
import pathlib, sys
work = pathlib.Path(sys.argv[1])
blob = b""
for name in ("audit.db", "audit.db-wal", "audit.db-shm"):
    p = work / name
    if p.exists():
        blob += p.read_bytes()
for raw in ("13800138000", "138 0013 8000", "王建国"):
    assert raw.encode("utf-8") not in blob, f"audit db contains raw value: {raw}"
print("  ✓ 审计库全文件 bytes 级扫描零原值（夹具三值）")
PYEOF

echo
echo "M1-#1 ACCEPTANCE: PASS（curl 三轮：占位符恒同 ✓ / 归一化等价 ✓ / 泄漏计数=0 ✓ / 审计零明文 ✓）"
