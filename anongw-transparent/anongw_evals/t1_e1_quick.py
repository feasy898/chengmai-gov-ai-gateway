"""E1 服从性快测（M0-实验报告 §三.3/§五.2 建议「M1 起步即补」；规划 §四 M0 实验表 E1 行的
「10 分钟 HTTPS_PROXY 服从性快测（echo 服务 + 最小客户端）」）。

运行::

    cd anongw-transparent && ../.venv/bin/python -m anongw_evals.t1_e1_quick

exit 0 = 通过。检查项：
1. 装置自检：echo 服务（本地 HTTP 服务，记录全部请求并回显）+ 最小 CONNECT
   代理（记录 CONNECT 目标后建立隧道）；自签证书可用时 echo 服务升 TLS；
2. 负控：curl **不带**代理 env 直连 echo → echo 收到、代理零记录
   （装置没有"凭空看见流量"的假阳性面）；
3. 正例：curl 带 HTTPS_PROXY/https_proxy → 代理记录 CONNECT + （TLS 可用时）
   echo 收到经隧道解密的 HTTPS 请求，端到端回显一致 ⇒ curl 服从 env 代理；
4. Node 默认栈实测（本机在装 node 22；zcode 为 Electron/Node 系的代表性面）：
   node https.get + HTTPS_PROXY env → CONNECT 是否落在代理上，如实记矩阵行
   （Node 核心 https/fetch 默认**不读** env 代理，需 agent 侧显式支持——
   本用例是测量不是门，"不服从"如实登记不判 FAIL）；
5. E1 杀死线核对：可配 endpoint 类（T1，M0 curl 级证据 9ccd52d + 本仓 M1 壳）
   + env 服从类（本快测 curl 行）合计 ≥ 2 → **未被杀死**（开发规划-v1.md:188）。

边界（如实）：本快测只覆盖「最小客户端」与 Node 默认栈；真实桌面/CLI agent
逐个实测（zcode/kimi/…）归 M2 适配矩阵（规划 §四M2；zcode 全局配置改动有
打断当前会话的风险，M0-实验报告 §四.4 已登记，M1 不动）。
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PKG_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(REPO_ROOT), str(PKG_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from anongw_evals._portalloc import free_ports  # noqa: E402
from anongw_evals.thresholds import E1_CHANNEL_KILL_LINE  # noqa: E402

RESULTS: list[tuple[bool, str]] = []


class SkipCase(Exception):
    pass


def _record(name: str, fn) -> None:
    try:
        detail = fn()
        RESULTS.append((True, f"PASS  {name}" + (f" — {detail}" if detail else "")))
    except SkipCase as exc:
        RESULTS.append((True, f"SKIP  {name} — {exc}"))
    except Exception as exc:  # noqa: BLE001 — 汇总所有失败后统一退出
        RESULTS.append((False, f"FAIL  {name} — {type(exc).__name__}: {exc}"))


# ── 装置：echo 服务 ────────────────────────────────────────────────

class _EchoState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.requests: list[dict[str, str]] = []

    def add(self, path: str, body: str) -> None:
        with self.lock:
            self.requests.append({"path": path, "body": body})

    def paths(self) -> list[str]:
        with self.lock:
            return [r["path"] for r in self.requests]


def make_echo_server(state: _EchoState, *, tls_ctx: ssl.SSLContext | None):
    class Handler(BaseHTTPRequestHandler):
        def _handle(self) -> None:
            length = int(self.headers.get("content-length") or 0)
            body = self.rfile.read(length).decode("utf-8", errors="replace") if length else ""
            state.add(self.path, body)
            payload = json.dumps({"echo": body, "path": self.path},
                                 ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        do_GET = do_POST = _handle  # noqa: N815 — http.server 钩子名固定

        def log_message(self, *args: object) -> None:  # 静默（记录在 state）
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    if tls_ctx is not None:
        server.socket = tls_ctx.wrap_socket(server.socket, server_side=True)
    return server


# ── 装置：最小 CONNECT 代理 ────────────────────────────────────────

class _ProxyState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.connects: list[str] = []

    def add(self, target: str) -> None:
        with self.lock:
            self.connects.append(target)

    def has_connect_to(self, port: int) -> bool:
        with self.lock:
            return any(t.endswith(f":{port}") for t in self.connects)


def start_connect_proxy(state: _ProxyState, *, echo_port: int):
    """最小 CONNECT 代理：记录 CONNECT 目标；隧道只放行去 echo 的流量。"""
    banner = b"HTTP/1.1 200 Connection established\r\n\r\n"

    def splice(client: socket.socket, target_host: str, target_port: int) -> None:
        try:
            if target_port != echo_port:
                client.sendall(b"HTTP/1.1 403 forbidden-target\r\n\r\n")
                return
            up = socket.create_connection((target_host, target_port), timeout=5)
            client.sendall(banner)
            client.settimeout(10)
            up.settimeout(10)
            stop = threading.Event()

            def pump(src: socket.socket, dst: socket.socket) -> None:
                try:
                    while True:
                        data = src.recv(65536)
                        if not data:
                            break
                        dst.sendall(data)
                except OSError:
                    pass
                finally:
                    stop.set()
                    try:
                        dst.shutdown(socket.SHUT_WR)
                    except OSError:
                        pass

            t1 = threading.Thread(target=pump, args=(client, up), daemon=True)
            t2 = threading.Thread(target=pump, args=(up, client), daemon=True)
            t1.start()
            t2.start()
            stop.wait(timeout=15)
        except OSError:
            pass
        finally:
            try:
                client.close()
            except OSError:
                pass

    def handle(client: socket.socket) -> None:
        try:
            client.settimeout(5)
            buf = b""
            while b"\r\n\r\n" not in buf:
                chunk = client.recv(65536)
                if not chunk:
                    return
                buf += chunk
            line = buf.split(b"\r\n", 1)[0].decode("latin-1")
            parts = line.split()
            if len(parts) >= 2 and parts[0].upper() == "CONNECT":
                host, _, port_s = parts[1].rpartition(":")
                state.add(f"{host}:{port_s}")
                # 把已缓冲的后续字节也带上（理论上 CONNECT 后客户端才开始 TLS）
                threading.Thread(target=splice, args=(client, host, int(port_s)),
                                 daemon=True).start()
            else:
                client.sendall(b"HTTP/1.1 405 only-connect\r\n\r\n")
                client.close()
        except OSError:
            try:
                client.close()
            except OSError:
                pass

    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(16)
    port = server.getsockname()[1]

    def serve() -> None:
        while True:
            try:
                client, _ = server.accept()
            except OSError:
                return
            threading.Thread(target=handle, args=(client,), daemon=True).start()

    threading.Thread(target=serve, daemon=True).start()
    return server, port


def _mint_self_signed_cert(tmp: Path) -> tuple[Path, Path] | None:
    """openssl 自签证书（装置用，非交付物）；不可用返回 None。"""
    key, cert = tmp / "echo.key", tmp / "echo.crt"
    try:
        subprocess.run(
            ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-keyout", str(key),
             "-out", str(cert), "-days", "2", "-nodes", "-subj", "/CN=127.0.0.1",
             "-addext", "subjectAltName=IP:127.0.0.1"],
            capture_output=True, timeout=30, check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return key, cert


def _node_probe_script(port: int) -> str:
    return (
        "const https = require('https');\n"
        f"const req = https.get({{host:'127.0.0.1', port:{port}, path:'/node-probe', "
        "rejectUnauthorized:false, timeout:4000}, res => {\n"
        "  console.log('OK ' + res.statusCode); process.exit(0);\n"
        "});\n"
        "req.on('error', e => { console.log('ERR ' + (e.code || e.message)); process.exit(0); });\n"
        "req.on('timeout', () => { console.log('TIMEOUT'); req.destroy(); process.exit(0); });\n"
    )


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    echo_port, proxy_port = free_ports(2)
    state, proxy_state = _EchoState(), _ProxyState()
    tmp = Path(tempfile.mkdtemp(prefix="anongw_e1_"))
    cert_pair = _mint_self_signed_cert(tmp)
    tls_ctx = None
    if cert_pair is not None:
        tls_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls_ctx.load_cert_chain(cert_pair[1], cert_pair[0])
    echo = make_echo_server(state, tls_ctx=tls_ctx)
    threading.Thread(target=echo.serve_forever, daemon=True).start()
    echo_port = echo.server_address[1]  # 实际绑定端口（装置内自分配）
    proxy_srv, proxy_port = start_connect_proxy(proxy_state, echo_port=echo_port)
    scheme = "https" if tls_ctx is not None else "http"

    env_no_proxy = {k: v for k, v in os.environ.items()
                    if k.lower() not in ("https_proxy", "http_proxy", "all_proxy")}
    env_with_proxy = dict(env_no_proxy)
    env_with_proxy.update({"HTTPS_PROXY": f"http://127.0.0.1:{proxy_port}",
                           "https_proxy": f"http://127.0.0.1:{proxy_port}"})

    def check_fixture() -> str:
        assert echo_port > 0 and proxy_port > 0
        assert (tls_ctx is not None) == (cert_pair is not None)
        return (f"echo :{echo_port} ({scheme}), CONNECT proxy :{proxy_port}, "
                f"tls={'yes' if tls_ctx is not None else 'no (openssl unavailable)'}")

    def check_negative_control() -> str:
        before = len(proxy_state.connects)
        out = subprocess.run(
            ["curl", "-sS", "-x", "", f"{scheme}://127.0.0.1:{echo_port}/direct-probe",
             "-d", "negative-control", "--insecure" if tls_ctx is not None else "--silent"],
            capture_output=True, text=True, timeout=20, env=env_no_proxy,
        )
        assert out.returncode == 0, f"direct curl failed: {out.stderr[:200]}"
        assert "/direct-probe" in state.paths(), "echo did not see direct request"
        assert len(proxy_state.connects) == before, (
            "negative control violated: proxy recorded CONNECT without proxy env")
        return "direct request reached echo; proxy recorded nothing"

    def check_curl_compliance() -> str:
        before = len(proxy_state.connects)
        cmd = ["curl", "-sS", f"{scheme}://127.0.0.1:{echo_port}/proxied-probe",
               "-d", "proxy-compliance-payload"]
        if tls_ctx is not None:
            cmd += ["--cacert", str(cert_pair[1])]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30,
                             env=env_with_proxy)
        assert out.returncode == 0, f"proxied curl failed (rc={out.returncode}): {out.stderr[:300]}"
        assert proxy_state.has_connect_to(echo_port) and len(proxy_state.connects) > before, (
            "curl with HTTPS_PROXY did not produce a CONNECT at the proxy — not compliant?")
        if tls_ctx is not None:
            assert "/proxied-probe" in state.paths(), (
                "CONNECT seen but the tunneled HTTPS request never reached echo")
            body = json.loads(out.stdout)
            assert body["echo"] == "proxy-compliance-payload", f"echo mismatch: {body}"
            return ("CONNECT observed at proxy + end-to-end TLS round-trip "
                    "(payload echoed byte-identical)")
        raise SkipCase("CONNECT observed (compliance proven at tunnel level); "
                       "openssl unavailable → in-tunnel HTTPS round-trip not verified")

    def check_node_stack() -> str:
        node = shutil.which("node")
        if node is None:
            raise SkipCase("node not installed — Electron/Node-stack compliance row not measurable here")
        before = len(proxy_state.connects)
        script = tmp / "node_probe.js"
        script.write_text(_node_probe_script(echo_port), encoding="utf-8")
        out = subprocess.run([node, str(script)], capture_output=True, text=True,
                             timeout=30, env=env_with_proxy)
        connect_seen = len(proxy_state.connects) > before
        node_direct = "/node-probe" in state.paths()
        verdict = ("COMPLIANT (CONNECT landed at proxy)" if connect_seen
                   else "NON-COMPLIANT (default Node stack ignores env proxy; "
                        "needs agent-side proxy support — matrix row, not a gate)")
        detail = (f"node={Path(node).name} probe={out.stdout.strip() or out.stderr.strip()[:80]!r} "
                  f"connect_seen={connect_seen} echo_saw_direct={node_direct} → {verdict}")
        RESULTS.append((True, f"INFO  node env-proxy compliance — {detail}"))
        return "matrix row recorded (see INFO line)"

    def check_kill_line() -> str:
        channels = 1  # T1 可配 endpoint 类：M0 curl 级证据（9ccd52d）+ 本仓 M1 壳实体
        if any("curl" in r for ok, r in RESULTS if ok and "COMPLIANT" in r or "CONNECT observed" in r):
            channels += 1
        assert channels >= E1_CHANNEL_KILL_LINE, (
            f"kill line hit: only {channels} viable channel(s) < {E1_CHANNEL_KILL_LINE} — "
            "T2 降级/T3 提前评估须重报 owner（开发规划-v1.md:188）")
        return (f"viable channels = {channels} (T1 配置类 + env 服从类) ≥ "
                f"{E1_CHANNEL_KILL_LINE} → E1 未被杀死；agent 级矩阵归 M2")

    checks = [
        ("装置自检（echo + CONNECT 代理 + TLS）", check_fixture),
        ("负控：无代理 env 直连（代理零记录）", check_negative_control),
        ("正例：curl 服从 HTTPS_PROXY", check_curl_compliance),
        ("Node 默认栈服从性实测（矩阵行）", check_node_stack),
        ("E1 杀死线核对", check_kill_line),
    ]
    for name, fn in checks:
        _record(name, fn)
    print(f"\nE1 QUICK (echo+HTTPS_PROXY compliance): "
          f"{sum(1 for ok, _ in RESULTS if ok)}/{len(RESULTS)} checks passed")
    for _ok, line in RESULTS:
        print(line, flush=True)
    echo.shutdown()
    proxy_srv.close()
    return 0 if all(ok for ok, _ in RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
