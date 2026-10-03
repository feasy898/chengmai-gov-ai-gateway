"""会话存储：内存 LRU + SQLite 落盘双层 + TTL（开发指令 §5.3.3 / §8.4，T1.3）。

双层结构：
- 写路径：:class:`masking.mapper.SessionMapper` 首次插入新映射时经 ``on_insert``
  回调即时写 ``masking_map`` 表（INSERT OR REPLACE，主键 ``(session_id, placeholder)``）；
- 读路径：LRU 未命中（被换出/进程重启）→ 工厂按 ``session_id`` 从库中恢复
  **未过期**行（:meth:`SessionMapper.hydrate`），还原能力随即恢复；
- 会话稳定：占位符 = HMAC(key, session_id|type|normalized)，确定性——重启、
  换出、甚至 TTL 过期后同 session 同值再到达仍得到**同一占位符**，只是过期后
  映射行被删、还原能力失效（lookup 返回 None，占位符原样保留）；
- TTL：默认 24h（config ``session_ttl_h``）；:meth:`SessionStore.cleanup` 删过期行
  并换出空闲会话；:meth:`SessionStore.cleanup_loop` 为事件循环里的清理协程。

库文件边界（有意分文件）：``masking_map`` 按设计必须存归一化原值才能还原，
而审计库有 bytes 级全文件零明文断言（§9 U5 / audit.store.assert_db_no_raw_pii）
——两表不得同文件，故本存储持有独立 db 路径（config ``session_db``）。

线程模型：连接 ``check_same_thread=False`` + 内部锁（网关事件循环线程 get、
清理协程/eval 线程 cleanup 共用一把连接）。
"""
from __future__ import annotations

import asyncio
import sqlite3
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from common.logs import get_logger
from common.timeutil import iso_utc, parse_utc
from masking.mapper import SessionMapper, SessionRegistry
from masking.models import MappingEntry
from recognizers.models import EntityClass

log = get_logger(__name__)

#: masking_map 表 schema（§5.3.3 MappingEntry 行形状；字段只增不改名）
SCHEMA = """
CREATE TABLE IF NOT EXISTS masking_map (
  placeholder       TEXT    NOT NULL,
  type              TEXT    NOT NULL,
  normalized        TEXT    NOT NULL,
  first_seen        TEXT    NOT NULL,   -- 定长 UTC ISO8601（common.timeutil.iso_utc）
  session_id        TEXT    NOT NULL,
  preserve_semantic INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (session_id, placeholder)
);
CREATE INDEX IF NOT EXISTS idx_masking_map_first_seen ON masking_map(first_seen);
CREATE TABLE IF NOT EXISTS session_owner (
  session_id TEXT PRIMARY KEY,
  dept       TEXT NOT NULL,          -- 会话属主部门（先到先得绑定，还原面授权用）
  bound_at   TEXT NOT NULL           -- 定长 UTC ISO8601（common.timeutil.iso_utc）
);
"""

#: TTL 缺省（config/app.yaml session_ttl_h=24）
DEFAULT_TTL = timedelta(hours=24)

_INSERT_SQL = (
    "INSERT OR REPLACE INTO masking_map "
    "(placeholder, type, normalized, first_seen, session_id, preserve_semantic) "
    "VALUES (?, ?, ?, ?, ?, ?)"
)
_SELECT_BY_SESSION_SQL = (
    "SELECT placeholder, type, normalized, first_seen, session_id, preserve_semantic "
    "FROM masking_map WHERE session_id = ? AND first_seen >= ? ORDER BY first_seen"
)


def connect_db(db_path: str | Path) -> sqlite3.Connection:
    """打开（必要时创建）WAL 模式的 SQLite 库并确保 schema 在位。"""
    path = Path(db_path)
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def _row_to_entry(row: tuple) -> MappingEntry:
    return MappingEntry(
        placeholder=row[0], type=EntityClass(row[1]), normalized=row[2],
        first_seen=parse_utc(row[3]), session_id=row[4], preserve_semantic=bool(row[5]),
    )


class SessionStore:
    """占位符映射会话存储：LRU 注册表 + masking_map 落盘 + TTL 清理。

    对网关而言是 ``registry`` 的直接替代品（``store.get(session_id)`` 返回
    :class:`SessionMapper`，其余用法与进程内注册表完全一致）。
    """

    def __init__(self, key: bytes, db_path: str | Path, *, ttl: timedelta | None = None,
                 capacity: int = 1024) -> None:
        if not key:
            raise ValueError("masking key must be non-empty")
        self.ttl = ttl if ttl is not None else DEFAULT_TTL
        if self.ttl <= timedelta(0):
            raise ValueError(f"ttl must be positive, got {self.ttl}")
        self.db_path = Path(db_path)
        self._key = key
        self._conn = connect_db(self.db_path)
        self._sql_lock = threading.Lock()
        self._last_activity: dict[str, float] = {}   # session_id → time.monotonic()
        self._closed = False
        self.registry = SessionRegistry(key, capacity=capacity,
                                        mapper_factory=self._load_session)

    # ── 读路径（网关入口）────────────────────────────────────────
    def get(self, session_id: str) -> SessionMapper:
        """会话映射器（LRU 未命中时经工厂从库恢复未过期行）。"""
        self._last_activity[session_id] = time.monotonic()
        return self.registry.get(session_id)

    # ── 会话属主（部门绑定；还原面授权用）────────────────────────
    def bind_session(self, session_id: str, owner: str) -> str:
        """首次使用即绑定会话属主（先到先得，持久化 ``session_owner`` 表）；返回当前属主。

        审查加固：占位符映射只按 ``(session_id, placeholder)`` 主键存取、无部门
        归属——任一部门 Key 借他部门 session_id 调还原面即可把占位符还原成原值。
        属主表封死该跨部门还原链：首次使用（/v1/chat、/internal/anonymize）即
        绑定，此后只要会话仍有映射行，他部门访问一律拒绝。

        属主行生命周期（与 :meth:`cleanup` 同口径，防随机 session id 喷洒使
        ``session_owner`` 表无界增长）：**与该会话的映射行同生共死，且以一个
        TTL 为下限**——映射行全数过期/删除后，属主绑定在其 ``bound_at`` 早于
        TTL 截断时一并清除。刚绑定、尚未产生映射行的会话（干净文本首次请求）
        不会被下一轮 cleanup 立即解除绑定（先到先得承诺保持一个 TTL 的窗口）；
        无映射行的会话本无还原物，属主行被清后跨部门还原面仍为零；进程内
        ``registry._owners`` 视图亦随 LRU 换出丢失（落库为准）。
        """
        if not session_id:
            raise ValueError("session_id must be non-empty")
        with self._sql_lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO session_owner (session_id, dept, bound_at) "
                "VALUES (?, ?, ?)", (session_id, owner, iso_utc(datetime.now(UTC))))
            self._conn.commit()
            row = self._conn.execute(
                "SELECT dept FROM session_owner WHERE session_id = ?",
                (session_id,)).fetchone()
        # 库为准同步内存视图（registry.bind_session 先到先得，同语义）
        return self.registry.bind_session(session_id, str(row[0]) if row else owner)

    def owner_of(self, session_id: str) -> str | None:
        """会话属主（内存未命中落库查；均无返回 None）。"""
        owner = self.registry.owner_of(session_id)
        if owner is not None:
            return owner
        with self._sql_lock:
            row = self._conn.execute(
                "SELECT dept FROM session_owner WHERE session_id = ?",
                (session_id,)).fetchone()
        if row is None:
            return None
        return self.registry.bind_session(session_id, str(row[0]))

    def _load_session(self, session_id: str) -> SessionMapper:
        """注册表工厂：构造空 mapper 并从库中恢复该会话未过期映射行。"""
        cutoff = iso_utc(datetime.now(UTC) - self.ttl)
        with self._sql_lock:
            rows = self._conn.execute(_SELECT_BY_SESSION_SQL, (session_id, cutoff)).fetchall()
        mapper = SessionMapper(session_id, self._key, on_insert=self._persist)
        restored = mapper.hydrate(_row_to_entry(r) for r in rows)
        if restored:
            log.info("session_store.hydrated", extra={
                "session_id": session_id, "entries": restored,
            })
        return mapper

    # ── 写路径（on_insert 回调，即时落盘）────────────────────────
    def _persist(self, entry: MappingEntry) -> None:
        if self._closed:
            return
        with self._sql_lock:
            self._conn.execute(_INSERT_SQL, (
                entry.placeholder, entry.type.value, entry.normalized,
                iso_utc(entry.first_seen), entry.session_id, int(entry.preserve_semantic),
            ))
            self._conn.commit()

    # ── TTL 清理 ────────────────────────────────────────────────
    def cleanup(self, *, now: datetime | None = None) -> int:
        """删除过期映射行（库+内存同口径）并换出空闲超 TTL 的会话；返回删除行数。"""
        now = now or datetime.now(UTC)
        cutoff_dt = now - self.ttl
        cutoff = iso_utc(cutoff_dt)
        with self._sql_lock:
            deleted = self._conn.execute(
                "DELETE FROM masking_map WHERE first_seen < ?", (cutoff,)).rowcount
            # 属主行随会话行同生命周期（bind_session docstring 同口径）：映射行
            # 全数过期/删除、且绑定时间早于 TTL 截断后属主绑定一并清除（防
            # session_owner 表随喷洒的随机 session id 无界增长，审查 §低危面）。
            # ``bound_at < cutoff`` 下限保证刚绑定、尚未产生映射行的会话（干净
            # 文本首次请求）不被本轮 cleanup 立即解除绑定（先到先得保持一个
            # TTL 窗口）；映射行已过期的会话其 bound_at 必然更早，同轮清除。
            self._conn.execute(
                "DELETE FROM session_owner WHERE bound_at < ? AND session_id NOT IN "
                "(SELECT DISTINCT session_id FROM masking_map)", (cutoff,))
            self._conn.commit()
        # 内存条目与落盘行同口径过期（活跃会话的旧条目也不能再还原）
        self.registry.apply(lambda m: m.purge_expired(cutoff_dt))
        idle_cutoff = time.monotonic() - self.ttl.total_seconds()
        stale = [sid for sid, seen in self._last_activity.items() if seen < idle_cutoff]
        if stale:
            stale_set = set(stale)
            self.registry.evict_where(lambda m: m.session_id in stale_set)
            for sid in stale:
                self._last_activity.pop(sid, None)
        if deleted:
            log.info("session_store.expired_rows_deleted", extra={"rows": deleted})
        return max(0, deleted)

    async def cleanup_loop(self, interval_s: float = 300.0) -> None:
        """TTL 清理协程（app lifespan 启动；取消即退出）。"""
        log.info("session_store.cleanup_loop.start", extra={
            "interval_s": interval_s, "ttl_s": self.ttl.total_seconds(),
        })
        while True:
            await asyncio.sleep(interval_s)
            try:
                self.cleanup()
            except sqlite3.Error as exc:  # 清理失败不致命，下轮重试
                log.error("session_store.cleanup_failed", extra={
                    "exc_type": type(exc).__name__,
                })

    # ── 观测/生命周期 ────────────────────────────────────────────
    def row_count(self) -> int:
        with self._sql_lock:
            return int(self._conn.execute("SELECT COUNT(*) FROM masking_map").fetchone()[0])

    def __len__(self) -> int:
        return self.row_count()

    def close(self) -> None:
        self._closed = True
        with self._sql_lock:
            try:
                self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except sqlite3.Error:
                pass
            self._conn.close()
