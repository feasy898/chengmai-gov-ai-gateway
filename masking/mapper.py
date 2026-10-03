"""会话稳定占位符与可逆还原（开发指令 §5.3，冻结算法）。

占位符算法（§5.3.1，一字不差）::

    digest  = HMAC-SHA256(key=MASK_KEY, msg=f"{session_id}\\x1f{type}\\x1f{normalized}").hexdigest()
    digest8 = digest[:8]；同 session+type 内碰撞则升 10 位（插入时检测）
    placeholder = "〔" + 中文标签 + "·" + digest8 + "〕"     # 例：〔人名·7f3a2b1c〕

- 会话稳定：同 session 同值 → 恒同占位符；跨 session 因 session_id 参与摘要 → 不同；
- 归一化等价：同一实体的不同写法 → 同 normalized → 同占位符（见 masking/normalize.py）；
- 还原：正则扫描占位符形状，查会话映射替换为原值；未知形状原样保留。

会话存储（内存 LRU + SQLite 落盘 + TTL）见 masking/session_store.py；本模块的
SessionMapper 通过 ``on_insert`` 回调向外暴露新条目、``hydrate`` 支持从落盘行恢复，
自身不感知存储介质。
"""
from __future__ import annotations

import hashlib
import hmac
import re
import threading
import unicodedata
from collections import OrderedDict
from collections.abc import Callable, Iterable
from datetime import UTC, datetime

from masking.models import MappingEntry
from recognizers.models import EntityClass

PLACEHOLDER_OPEN = "〔"
PLACEHOLDER_SEPARATOR = "·"
PLACEHOLDER_CLOSE = "〕"

#: 摘要截断位数：首选 8 位；同 session+type 冲突时逐级升位（插入时检测）
DIGEST_WIDTHS: tuple[int, ...] = (8, 10, 12)

#: 占位符形状（还原扫描用）：中文标签非空、摘要 8–12 位小写 hex
RESTORE_PATTERN = re.compile(
    re.escape(PLACEHOLDER_OPEN) + r"([^" + re.escape(PLACEHOLDER_OPEN)
    + re.escape(PLACEHOLDER_CLOSE) + PLACEHOLDER_SEPARATOR + r"]+)"
    + re.escape(PLACEHOLDER_SEPARATOR) + r"([0-9a-f]{8,12})"
    + re.escape(PLACEHOLDER_CLOSE)
)

#: 还原时单条映射查找键（type 归一为字符串值，与摘要 msg 一致）
_DIGEST_SEPARATOR = "\x1f"

# ── 容错改形匹配（T8.4；gate_final b6 一轮 U8 GOVCLOUD 腿实锤增补）─────────
# 真实大模型回复会把占位符 token **改形**（模型输出随机性）：反引号/代码样式
# 包裹、空白与换行插入拆开、hex 大小写与全半角转写、同形括号（〔→【[）与
# 间隔号（·→・•.）替换。改形一旦超出 RESTORE_PATTERN 的匹配面（或形状匹配但
# 查表键不等，如 ``〔人名 ·…〕``），还原即漏配，改形残留直达客户端。
# 容错还原的判定链：候选括号对 → 剥噪声规范化 → 规范键查会话映射表 →
# **命中才替换**。结构〔标签·hex8-12〕本身足够特异，加上映射表命中这道
# 终审闸，普通文本（【注·见附件】、markdown 链接等）不可能被误替。
#
# 前缀段并入（U8 INTERNET 腿实锤增补）：模型还会把占位符**括号外的前缀文案**
# 挪进括号内——「主号：〔手机号·9cfd96c0〕」→「〔主号：手机号·9cfd96c0〕」，
# 多出「前缀段：」一节，规范键查表必然未命中（泄漏三样本：主号：手机号·
# 9cfd96c0 / 备用号：手机号·1522ba0d / 备用号：手机号·b44eb16e）。容错面扩为
# 「括号内 [任意前缀段：]*已知标签·hex8-12」：剥前缀段**只认已知标签集**
# （KNOWN_LABELS，剥不出已知标签不剥）——普通〔中文：…〕文本不会被误还原
# （映射表命中终审闸不变；并入的前缀段视为模型排版噪声，随括号对一并被
# 替换为原值，不参与正文保真）。

#: 括号与间隔号的同形变体（模型转写常见面；命中映射表才替换，放宽无害）
PLACEHOLDER_OPEN_VARIANTS = "〔【〖［["
PLACEHOLDER_CLOSE_VARIANTS = "〕】〗］]"
PLACEHOLDER_SEP_VARIANTS = "·・•‧⋅﹒．."

#: 前缀段分隔冒号（全/半角）：模型把括号外前缀文案并入括号内的分段符
#: （U8 INTERNET 腿实测为全角「：」：〔主号：手机号·9cfd96c0〕）
PLACEHOLDER_PREFIX_COLONS = "：:"

#: 改形候选最大扫描窗（字符）：规范形状 ≤32（标签2-3 + hex8-12），容忍反引号/
#: 空白/换行改形放宽到 48；流式缓冲上限（remap.MAX_PLACEHOLDER_LEN）与之同源
PLACEHOLDER_TOLERANT_MAX_LEN = 48

#: hex 部分转写易混字符兜底（仅 digest 应用；规范化后须是 8-12 位 hex 且
#: 命中映射表才替换——无误替面）。O→0 / I·l→1 是模型转写最常见混淆。
_DIGEST_CONFUSABLE = str.maketrans({"o": "0", "i": "1", "l": "1"})

_OPEN_VARIANTS_RE = re.compile("[" + re.escape(PLACEHOLDER_OPEN_VARIANTS) + "]")
_CLOSE_VARIANTS_RE = re.compile("[" + re.escape(PLACEHOLDER_CLOSE_VARIANTS) + "]")
_SEP_VARIANTS_RE = re.compile("[" + re.escape(PLACEHOLDER_SEP_VARIANTS) + "]")
_MANGLE_NOISE_RE = re.compile(r"[\s`]+")  # 改形噪声：空白/换行/反引号
_DIGEST_SHAPE_RE = re.compile(r"[0-9a-f]{8,12}")
_PREFIX_COLON_RE = re.compile("[" + re.escape(PLACEHOLDER_PREFIX_COLONS) + "]")

#: 已知中文标签集（EntityClass 全部 label）：前缀段剥离只认它——标签含冒号段时
#: 剥到已知标签才容错还原，剥不出已知标签保持原样（普通〔中文：…〕文本绝不因
#: 剥前缀而误入还原面；映射表命中仍是终审闸）
KNOWN_LABELS: frozenset[str] = frozenset(member.label for member in EntityClass)

# ── 裸 digest 检测面（§三g 补丁 2）────────────────────────────────────
# 括号锚被剥掉时上面那条括号扫描整条看不见，而「已知标签 + 间隔号 + hex 串」
# 这一段结构仍在（M1§2.5 实测 `手机号·f8808372` 零命中；M2§0.3 把它列为
# 7 坏形态之一「括号被剥」）。第二正则补的就是这个面。
#: hex 下限取 4 而非 8：8–12 是**规范**宽度（:data:`DIGEST_WIDTHS`），不是泄漏
#: 形态的宽度——M2§0.3 的 6 位幻觉 ``〔身份证·dead〕`` 与 16 位扩写都落在
#: 8–12 之外，按 8–12 卡死等于把本补丁要修的形态挡在门外。
#: 命中一律是**形状级**证据（披露口径，进计数）；告警仍以查表命中为闸
#: （M2§0.2：否则误报泛滥会把用户训练成忽略一切提示）。真值上限交给
#: digest 反查 oracle——两者并集才是披露口径（M1§4.1 互补盲区）。
_BARE_DIGEST_RE = re.compile(
    "(" + "|".join(re.escape(lbl) for lbl in sorted(KNOWN_LABELS, key=len, reverse=True)) + ")"
    "[" + re.escape(PLACEHOLDER_SEP_VARIANTS) + "]+"          # 间隔号变体与还原面同集
    r"\s*([0-9a-fA-F]{4,})"                                   # 改形/幻觉出来的 hex 串
)

#: 裸形证据串的非规范标记：hex 长度不在 DIGEST_WIDTHS 内时加此后缀，
#: 报告可据此区分「可规范化的占位符残留」与「不可辨的坏形」
NONCANON_MARK = "~noncanon"


def _bare_evidence(label: str, digest: str) -> str:
    """裸形命中 → 规范键形状的证据串（长度非 8–12 位者加 :data:`NONCANON_MARK`）。"""
    canon = f"{PLACEHOLDER_OPEN}{label}{PLACEHOLDER_SEPARATOR}{digest}{PLACEHOLDER_CLOSE}"
    return canon if len(digest) in DIGEST_WIDTHS else canon + NONCANON_MARK


# ── 标签副索引键面（§三g 补丁 1）──────────────────────────────────────
# 模型把占位符的中文标签翻译成英文后，digest 仍是同一个——digest 才是身份，
# 标签只是给模型看的装饰（M1§2.3 实测 EN 翻译标签频次最高）。副索引按
# ``(ascii 化标签, digest)`` 记账，让 EN 标签占位符从「泄漏」变回「还原」。
#: EN/ASCII 标签别名表：按 EntityClass.label 分组；模型用什么拼法都算同一类，
#: 归一后由 :func:`ascii_label_token` 折叠（大小写/下划线/空格/全角差异全消）。
LABEL_ALIASES: dict[str, tuple[str, ...]] = {
    "人名": ("person", "name", "person_name", "personname"),
    "住址": ("address", "home_address", "residence", "addr"),
    "身份证": ("id_card", "idcard", "identity_card", "id_no", "idno", "id_number"),
    "手机号": ("phone", "phone_number", "mobile", "mobile_phone", "phone_no", "cellphone"),
    "座机": ("landline", "telephone", "tel", "fixed_phone", "landline_phone"),
    "银行卡": ("bank_card", "bankcard", "card_no", "credit_card", "bankcard_no"),
    "信用代码": ("uscc", "credit_code", "unified_social_credit_code"),
    "车牌": ("plate", "license_plate", "car_plate", "plate_no", "vehicle_no"),
    "邮箱": ("email", "mail", "email_address", "mailbox"),
    "地址": ("ip", "ip_address", "ipaddr", "host_ip"),
    "密钥": ("secret", "secret_key", "api_key", "apikey", "token"),
    "出生日期": ("birth_date", "birthdate", "date_of_birth", "dob", "birthday"),
    "敏感属性": ("sensitive_attr", "sensitive_attribute", "attribute"),
    "工作秘密": ("work_secret", "job_secret", "worksecret"),
    "密级标识": ("classification", "classification_mark", "secret_level", "level_mark"),
    "注入指令": ("injection", "prompt_injection", "inject"),
    "内部机构": ("internal_org", "org_internal", "organization", "agency"),
    "文号": ("doc_number", "doc_no", "document_number", "ref_no"),
    "其他": ("other", "misc"),
}


def ascii_label_token(label: str) -> str | None:
    """占位符标签 → 副索引键；非 ASCII（中文）标签返回 ``None``。

    归一三步：NFKC 全半角归一 → 小写 → 去非字母数字字符（``ID_CARD`` 与
    ``Phone Number`` 分别折叠为 ``idcard`` / ``phonenumber``）。中文标签走
    :attr:`SessionMapper._by_placeholder` 主索引，不经本函数。
    """
    token = unicodedata.normalize("NFKC", label).lower()
    if any(ord(ch) > 127 for ch in token):
        return None
    token = "".join(ch for ch in token if ch.isalnum())
    return token or None


def _strip_prefix_segments(label: str) -> str:
    """「[任意前缀段：]*标签」改形 → 已知标签；末段非已知标签则原样返回。

    模型把括号外前缀文案（「主号：」「备用号：」等）并入括号内后，标签段变多节
    （``主号：手机号``）；按冒号变体取末段，末段是已知标签才剥（多节逐段以冒号
    分隔，``备用联系方式：主号：手机号`` → ``手机号``）。
    """
    if not _PREFIX_COLON_RE.search(label):
        return label
    tail = _PREFIX_COLON_RE.split(label)[-1]
    return tail if tail in KNOWN_LABELS else label


def canonical_placeholder(inside: str) -> str | None:
    """候选括号内文本 → 规范占位符键（``〔标签·hex〕``）；不可规范化返回 ``None``。

    规范化四步（顺序固定）：①剥除改形噪声（空白/换行/反引号）；②按间隔号
    变体切成「标签+摘要」两段（多段/单段=不是占位符）；③摘要经 NFKC 全半角
    归一 + 小写 + 易混字符兜底后须为 8–12 位 hex；④标签含冒号前缀段时剥至
    已知标签（:func:`_strip_prefix_segments`，只认 :data:`KNOWN_LABELS`——
    「主号：手机号」→「手机号」；剥不出已知标签保持原样）。标签须不含任何
    括号变体。
    """
    compact = _MANGLE_NOISE_RE.sub("", inside)
    if not compact:
        return None
    parts = _SEP_VARIANTS_RE.split(compact)
    if len(parts) != 2:
        return None
    label, digest = parts
    if not label or not digest:
        return None
    if _OPEN_VARIANTS_RE.search(label) or _CLOSE_VARIANTS_RE.search(label):
        return None
    digest = unicodedata.normalize("NFKC", digest).lower().translate(_DIGEST_CONFUSABLE)
    if not _DIGEST_SHAPE_RE.fullmatch(digest):
        return None
    label = _strip_prefix_segments(label)
    return f"{PLACEHOLDER_OPEN}{label}{PLACEHOLDER_SEPARATOR}{digest}{PLACEHOLDER_CLOSE}"


def restore_tolerant(text: str, lookup: Callable[[str], str | None]) -> str:
    """整段容错还原扫描：改形占位符 → 规范键查表 → 命中替换为原值。

    与 :class:`masking.remap.StreamRestorer` 的流式状态机共用同一判定链
    （canonical_placeholder + lookup），fuzz 断言保证整段与流式严格等价。
    不可还原的候选（查表未命中/形状不足）逐字原样放行——未知形状不放行也
    不吞掉，与既有契约一致。
    """
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        m = _OPEN_VARIANTS_RE.search(text, i)
        if m is None:  # 其后不再有开括号变体 → 全部普通文本
            out.append(text[i:])
            break
        open_at = m.start()
        if open_at > i:
            out.append(text[i:open_at])
        cm = _CLOSE_VARIANTS_RE.search(
            text, open_at + 1, min(n, open_at + PLACEHOLDER_TOLERANT_MAX_LEN - 1))
        if cm is not None:
            key = canonical_placeholder(text[open_at + 1:cm.start()])
            if key is not None:
                value = lookup(key)
                if value is not None:
                    out.append(value)
                    i = cm.end()
                    continue
            # 完整括号对但不可还原 → 放行开括号字符本身，其余重扫
            # （内部若再出现开括号自然开启新候选）
            out.append(text[open_at])
            i = open_at + 1
            continue
        # 窗内无闭合 → 放行开括号，其余重扫（含正文里孤立的开括号变体）
        out.append(text[open_at])
        i = open_at + 1
    return "".join(out)


def tolerant_placeholder_hits(text: str) -> list[str]:
    """检测文本中全部「可规范化为占位符形状」的候选（规范键，不去重）。

    泄漏检测面（比 RESTORE_PATTERN 宽）：还原正则不可见的改形残留（静默泄漏）
    也能抓到。真实大模型腿的「占位符零泄漏」断言以此为准——改形残留只要形状
    可辨即算泄漏，无论是否仍在会话映射表内。

    两条扫描面（§三g 补丁 2 后）：

    1. **括号面**：同形括号/同形间隔号/前缀段并入的候选，走
       :func:`canonical_placeholder` 规范化为键；
    2. **裸 digest 面**：括号锚被剥掉后残留的「已知标签·hex」串（M1§2.5 实测
       零命中的那一族）。

    命中一律是形状级证据（披露口径）；处置/告警口径只认查表命中（M2§0.2），
    digest 反查 oracle 承担第二判据（M1§4.1：两判据互补，谁都不覆盖谁）。
    """
    out: list[str] = []
    seen: set[str] = set()
    i, n = 0, len(text)
    while i < n:
        m = _OPEN_VARIANTS_RE.search(text, i)
        if m is None:
            break
        open_at = m.start()
        cm = _CLOSE_VARIANTS_RE.search(
            text, open_at + 1, min(n, open_at + PLACEHOLDER_TOLERANT_MAX_LEN - 1))
        if cm is not None:
            key = canonical_placeholder(text[open_at + 1:cm.start()])
            if key is not None:
                if key not in seen:
                    seen.add(key)
                    out.append(key)
                i = cm.end()
                continue
        i = open_at + 1
    # 裸 digest 面：NFKC 归一后扫全串（模型转写面的大小写/全半角一并吃掉）
    for m in _BARE_DIGEST_RE.finditer(unicodedata.normalize("NFKC", text)):
        evidence = _bare_evidence(m.group(1), m.group(2).lower())
        if evidence not in seen:
            seen.add(evidence)
            out.append(evidence)
    return out


def _utc_now() -> datetime:
    return datetime.now(UTC)


class SessionMapper:
    """单个会话的占位符 ↔ 原值映射（内存态，形状即 MappingEntry）。

    ``on_insert``：新条目首次插入后的回调（会话存储借此即时落盘；
    复用命中与 hydrate 恢复不触发）。
    """

    def __init__(self, session_id: str, key: bytes,
                 *, on_insert: Callable[[MappingEntry], None] | None = None) -> None:
        self.session_id = session_id
        self._key = key
        self._on_insert = on_insert
        self._by_placeholder: dict[str, MappingEntry] = {}
        self._by_value: dict[tuple[str, str], str] = {}  # (type值, normalized) → placeholder
        self._by_ascii_label: dict[tuple[str, str], str] = {}  # §三g 补丁1 副索引

    def _digest_of(self, placeholder: str) -> str:
        """占位符 → 其摘要段（去掉两侧括号锚与标签段）。"""
        inner = placeholder
        if inner.startswith(PLACEHOLDER_OPEN):
            inner = inner[1:]
        if inner.endswith(PLACEHOLDER_CLOSE):
            inner = inner[:-1]
        return inner.partition(PLACEHOLDER_SEPARATOR)[2]

    def _index_label_aliases(self, entry: MappingEntry) -> None:
        """把条目登记进标签副索引（§三g 补丁 1）。

        键 ``(ascii 化别名标签, 摘要)``、值原值；摘要与占位符内逐字相同，
        故 EN 标签改形只要摘要没被模型改写就必然命中。标签别名表未覆盖的
        英文写法（如 ``Tel No.``）按「查表未命中」原样放行——宁残留不错还。
        """
        digest = self._digest_of(entry.placeholder)
        for alias in LABEL_ALIASES.get(entry.type.label, ()):
            token = ascii_label_token(alias)
            if token is not None:
                self._by_ascii_label[(token, digest)] = entry.normalized

    def _digest(self, type_value: str, normalized: str) -> str:
        msg = f"{self.session_id}{_DIGEST_SEPARATOR}{type_value}{_DIGEST_SEPARATOR}{normalized}"
        return hmac.new(self._key, msg.encode("utf-8"), hashlib.sha256).hexdigest()

    def placeholder_for(self, entity_type: EntityClass, normalized: str) -> tuple[str, MappingEntry]:
        """返回该 (类别, 归一化值) 的占位符；首次插入，重复命中复用（含 first_seen 不变）。"""
        value_key = (entity_type.value, normalized)
        existing_ph = self._by_value.get(value_key)
        if existing_ph is not None:
            return existing_ph, self._by_placeholder[existing_ph]
        digest = self._digest(entity_type.value, normalized)
        for width in DIGEST_WIDTHS:
            placeholder = (
                f"{PLACEHOLDER_OPEN}{entity_type.label}{PLACEHOLDER_SEPARATOR}"
                f"{digest[:width]}{PLACEHOLDER_CLOSE}"
            )
            holder = self._by_placeholder.get(placeholder)
            if holder is None:
                entry = MappingEntry(
                    placeholder=placeholder, type=entity_type, normalized=normalized,
                    first_seen=_utc_now(), session_id=self.session_id,
                )
                self._by_placeholder[placeholder] = entry
                self._by_value[value_key] = placeholder
                self._index_label_aliases(entry)
                if self._on_insert is not None:
                    self._on_insert(entry)
                return placeholder, entry
            if holder.normalized == normalized and holder.type is entity_type:
                # 极端小概率：低宽度位与异值同串碰撞后，同值再次到达——直接复用既有条目
                self._by_value[value_key] = placeholder
                return placeholder, holder
            # 不同值占用了同宽度占位符 → 升位重试（§5.3.1 插入期碰撞检测）
        raise RuntimeError(
            f"placeholder digest collision unresolved for session={self.session_id}"
        )  # pragma: no cover — 8/10/12 位 hex 碰撞概率可忽略

    def mask(self, text: str, spans: Iterable[tuple[int, int, EntityClass, str]]) -> tuple[str, list[MappingEntry]]:
        """把 (start, end, 类别, normalized) 列表替换为占位符；返回 (脱敏文本, 新增/复用条目)。"""
        entries: list[MappingEntry] = []
        masked = text
        for start, end, entity_type, normalized in sorted(spans, key=lambda s: s[0], reverse=True):
            placeholder, entry = self.placeholder_for(entity_type, normalized)
            masked = masked[:start] + placeholder + masked[end:]
            entries.append(entry)
        entries.reverse()  # 恢复为正文顺序
        return masked, entries

    def restore(self, text: str) -> str:
        """占位符 → 原值（normalized）；映射表外的占位符形状原样保留。

        T8.4 起走 :func:`restore_tolerant` 容错扫描：模型对占位符的改形
        （反引号/空白/换行/全半角/同形括号·间隔号）先规范化再查表，命中才
        替换——非流式响应与流式（StreamRestorer）同一判定链。
        """
        return restore_tolerant(text, self.lookup)

    def lookup(self, placeholder: str) -> str | None:
        """单条占位符 → 原值；映射表外返回 None（流式还原状态机的查找入口）。

        主索引未命中时走标签副索引（§三g 补丁 1）：EN 标签的规范键按
        ``(ascii 化标签, 摘要)`` 复查——摘要逐字相等且标签别名命中才还原，
        两道闸任一不过即原样放行（错还原率=0 硬不变量）。
        """
        entry = self._by_placeholder.get(placeholder)
        if entry is not None:
            return entry.normalized
        token = ascii_label_token(self._digest_label(placeholder))
        if token is None:
            return None
        return self._by_ascii_label.get((token, self._digest_of(placeholder)))

    def _digest_label(self, placeholder: str) -> str:
        """占位符 → 标签段（去括号锚与摘要段）；无间隔号时返回整串（查表必未命中）。"""
        inner = placeholder
        if inner.startswith(PLACEHOLDER_OPEN):
            inner = inner[1:]
        if inner.endswith(PLACEHOLDER_CLOSE):
            inner = inner[:-1]
        return inner.partition(PLACEHOLDER_SEPARATOR)[0]

    def hydrate(self, entries: Iterable[MappingEntry]) -> int:
        """从落盘行恢复映射（进程重启/会话被 LRU 换出后）；返回实际恢复条数。

        已在内存中的占位符不覆盖（内存态为准）；恢复行不触发 ``on_insert``。
        """
        restored = 0
        for entry in entries:
            if entry.placeholder in self._by_placeholder:
                continue
            value_key = (entry.type.value, entry.normalized)
            self._by_placeholder[entry.placeholder] = entry
            self._by_value.setdefault(value_key, entry.placeholder)
            self._index_label_aliases(entry)
            restored += 1
        return restored

    def purge_expired(self, cutoff: datetime) -> int:
        """删除内存中 ``first_seen < cutoff`` 的条目（与落盘 TTL 同口径）；返回删除数。"""
        doomed = [ph for ph, entry in self._by_placeholder.items() if entry.first_seen < cutoff]
        for ph in doomed:
            entry = self._by_placeholder.pop(ph)
            key = (entry.type.value, entry.normalized)
            if self._by_value.get(key) == ph:
                del self._by_value[key]
        if doomed:  # 副索引按存活条目重建（TTL 与落盘同口径，防已删条目被 EN 标签复活）
            self._by_ascii_label = {}
            for entry in self._by_placeholder.values():
                self._index_label_aliases(entry)
        return len(doomed)

    def entries(self) -> list[MappingEntry]:
        return list(self._by_placeholder.values())


class SessionRegistry:
    """会话 → SessionMapper 的进程内 LRU 注册表（容量防失控）。

    ``mapper_factory``：LRU 未命中时的构造工厂（会话存储借此在构造时从
    SQLite 恢复该会话的映射行）；缺省为纯内存构造（v0 形态）。

    会话属主（审查加固）：``bind_session``/``owner_of`` 记录会话首个使用部门——
    还原面（/internal/restore 等）据此拒绝跨部门还原他人会话（先到先得绑定，
    会话被换出/淘汰时属主记录一并清除；SQLite 形态的持久属主见
    masking/session_store.py 的 ``session_owner`` 表）。
    """

    def __init__(self, key: bytes, capacity: int = 1024,
                 *, mapper_factory: Callable[[str], SessionMapper] | None = None) -> None:
        if not key:
            raise ValueError("masking key must be non-empty")
        self._key = key
        self._capacity = max(1, capacity)
        self._mapper_factory = mapper_factory
        self._lock = threading.Lock()
        self._sessions: OrderedDict[str, SessionMapper] = OrderedDict()
        self._owners: dict[str, str] = {}

    def get(self, session_id: str) -> SessionMapper:
        with self._lock:
            mapper = self._sessions.get(session_id)
            if mapper is None:
                mapper = (self._mapper_factory(session_id) if self._mapper_factory
                          else SessionMapper(session_id, self._key))
                self._sessions[session_id] = mapper
            self._sessions.move_to_end(session_id)
            while len(self._sessions) > self._capacity:
                stale, _ = self._sessions.popitem(last=False)
                self._owners.pop(stale, None)
            return mapper

    # ── 会话属主（部门绑定；还原面授权用）────────────────────────
    def bind_session(self, session_id: str, owner: str) -> str:
        """首次使用即绑定会话属主（先到先得）；返回该会话当前属主。

        容量路径（审查加固）：正常流每条属主条目同请求即随 :meth:`get` 进 LRU
        （换出时一并清除，见 :meth:`get`）；「校验通过但 prepare 阶段异常」等
        边界会留下无 mapper 的属主条目——按 2×LRU 容量裁掉最老条目，
        ``_owners`` 恒有界（与 LRU 换出同一「最旧先出」口径）。
        """
        if not session_id:
            raise ValueError("session_id must be non-empty")
        with self._lock:
            existing = self._owners.get(session_id)
            if existing is None:
                self._owners[session_id] = owner
                while len(self._owners) > self._capacity * 2:
                    self._owners.pop(next(iter(self._owners)))
                return owner
            return existing

    def owner_of(self, session_id: str) -> str | None:
        """会话属主（未绑定返回 None）。"""
        with self._lock:
            return self._owners.get(session_id)

    def evict_where(self, predicate: Callable[[SessionMapper], bool]) -> int:
        """按条件换出会话（TTL 清理用）；返回换出数。"""
        with self._lock:
            doomed = [sid for sid, mapper in self._sessions.items() if predicate(mapper)]
            for sid in doomed:
                del self._sessions[sid]
                self._owners.pop(sid, None)
            return len(doomed)

    def apply(self, fn: Callable[[SessionMapper], None]) -> None:
        """对全部在册会话映射器就地应用 ``fn``（TTL 条目清理用）。"""
        with self._lock:
            for mapper in self._sessions.values():
                fn(mapper)
