"""安装实例标识：生成与保管（规划 §四M1；值级键的命名空间根）。

语义（规划 §三b）：把**恒定的安装实例标识**喂进基线 digest 公式的 session 槽
（``digest = HMAC(MASK_KEY, f"{instance_id}\\x1f{type}\\x1f{normalized}")``），
映射表即成为本机全局字典——同值在本机任何时候恒同占位符，回写层不需要知道
会话。换机器/重装 = 新实例文件 = 新的、不可关联的命名空间。

保管纪律：
- 缺省落 ``anongw-transparent/data/instance.json``（仓 .gitignore ``data/``
  规则覆盖，不进仓）；文件 0600（POSIX，尽力而为）；
- 写入原子（tmp + os.replace），损坏/半写文件不静默吞——报错让人修，
  绝不静默换新标识（静默换标识 = 全部旧占位符变孤儿，映射尽失）；
- 标识值必须过引擎网关的会话头形态闸（``gateway.app.SESSION_ID_RE``，
  此处直接 import 同一正则——单一事实源，不造平行实现）。
"""
from __future__ import annotations

import json
import os
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from anongw_shell.config import ShellSettings
from gateway.app import SESSION_ID_RE

#: 标识前缀（与引擎自生成 ``sess_`` 形态区分——审计里一眼分清两种键域）
INSTANCE_ID_PREFIX = "anongw-inst-"

#: 保管文件格式版本（字段只增不改名）
_STORE_FORMAT = 1


class InstanceIdentityError(RuntimeError):
    """实例标识文件损坏/非法（不静默换新——旧占位符会全部变孤儿）。"""


@dataclass(frozen=True)
class InstanceIdentity:
    """一个安装实例的恒定身份。"""

    instance_id: str
    created_at: str
    store_path: Path | None   # env 覆盖态（测试）时为 None


def new_instance_id() -> str:
    """新安装实例标识：前缀 + uuid4 hex（``[a-z0-9-]`` 天然过网关形态闸）。"""
    return INSTANCE_ID_PREFIX + uuid.uuid4().hex


def _validate(instance_id: str) -> str:
    if not isinstance(instance_id, str) or not SESSION_ID_RE.fullmatch(instance_id):
        raise InstanceIdentityError(
            f"instance id must match {SESSION_ID_RE.pattern!r}, got {instance_id!r}")
    return instance_id


def load_or_create(
    settings: ShellSettings, *, env: Mapping[str, str] | None = None
) -> InstanceIdentity:
    """装载（或首装生成）安装实例标识。

    优先级：``ANONGW_SHELL_INSTANCE_ID`` 显式覆盖（测试/CI；不落盘）>
    保管文件 > 新建并落盘。created_at 只在首装时生成，此后原样回读。
    """
    raw_env = os.environ if env is None else env
    override = settings.instance_id or raw_env.get("ANONGW_SHELL_INSTANCE_ID")
    if override:
        return InstanceIdentity(instance_id=_validate(override),
                                created_at="", store_path=None)

    store = settings.resolve_instance_file()
    if store.exists():
        try:
            data = json.loads(store.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise InstanceIdentityError(
                f"instance file unreadable/corrupt ({store}): {exc} — "
                "refusing to silently mint a new identity (old placeholders would orphan)"
            ) from exc
        if not isinstance(data, dict) or data.get("format") != _STORE_FORMAT \
                or not isinstance(data.get("instance_id"), str):
            raise InstanceIdentityError(f"instance file has unexpected shape: {store}")
        return InstanceIdentity(
            instance_id=_validate(data["instance_id"]),
            created_at=str(data.get("created_at", "")),
            store_path=store,
        )

    identity = InstanceIdentity(instance_id=_validate(new_instance_id()),
                                created_at=datetime.now(UTC).isoformat(timespec="seconds"),
                                store_path=store)
    _persist(store, identity)
    return identity


def _persist(store: Path, identity: InstanceIdentity) -> None:
    """原子落盘 + 0600（POSIX 尽力而为；Windows 忽略 chmod）。"""
    payload = {
        "format": _STORE_FORMAT,
        "instance_id": identity.instance_id,
        "created_at": identity.created_at,
    }
    store.parent.mkdir(parents=True, exist_ok=True)
    tmp = store.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, store)
    try:
        os.chmod(store, 0o600)
    except OSError:  # noqa: PERF203 — 非 POSIX 文件系统（如 Windows FAT）尽力而为
        pass
