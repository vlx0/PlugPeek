"""Сборка записей: подключили или вытащили устройство."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

_FRAC = re.compile(r"(\.\d{6})\d+")
_VID = re.compile(r"VID_([0-9A-F]{4})", re.I)
_PID = re.compile(r"PID_([0-9A-F]{4})", re.I)
_VEN = re.compile(r"VEN_([^&#\\]+)", re.I)
_PROD = re.compile(r"PROD_([^&#\\]+)", re.I)

IN_ID = 400
OUT_ID = 420
_NEAR = timedelta(seconds=3)
_SKIP_PREFIX = (
    "PCI\\",
    "DISPLAY\\",
    "ACPI\\",
    "ROOT\\",
    "HTREE\\",
    "STORAGE\\VOLUME",
    "SWD\\XVDD",
    "SWD\\WINTUN",
)


@dataclass
class Event:
    when: datetime
    id: int
    src: str
    props: tuple[str, ...]


@dataclass
class Plug:
    when: datetime
    kind: str
    title: str
    instance: str
    vid: str
    pid: str
    serial: str
    vendor: str
    product: str


def clean_text(text: str) -> str:
    return "".join(ch for ch in text if unicodedata.category(ch) != "Cf").strip()


def parse_iso(text: str) -> datetime | None:
    raw = clean_text(str(text)).replace("Z", "+00:00")
    if not raw:
        return None
    raw = _FRAC.sub(r"\1", raw)
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _stamp(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def is_plug_device(instance: str) -> bool:
    raw = clean_text(instance)
    upper = raw.upper()
    if "&MI_" in upper or "ROOT_HUB" in upper or "VID_0000" in upper:
        return False
    if any(upper.startswith(prefix) for prefix in _SKIP_PREFIX):
        return False
    return "USB" in upper or upper.startswith("HID\\VID_")


def _serial(raw: str) -> str:
    junk = ("USBSTOR", "DISK", "VOLUME", "WPDBUSENUM", "VID_", "PID_")
    if "#" in raw:
        bits = [bit for bit in raw.replace("\\", "#").split("#") if bit]
        for bit in reversed(bits):
            cand = bit.split("&")[0].strip("_?")
            upper = cand.upper()
            if cand and len(cand) >= 4 and not any(token in upper for token in junk):
                return cand
    chunks = raw.replace("/", "\\").split("\\")
    if chunks:
        last = chunks[-1]
        if last.upper().startswith("5&"):
            return ""
        if last and "VID_" not in last.upper() and "USBSTOR" not in last.upper():
            cand = last.split("&")[0]
            if cand and len(cand) >= 3:
                return cand
    return ""


def parse_instance(instance: str) -> dict[str, str]:
    raw = clean_text(instance)
    upper = raw.upper()
    vendor = _VEN.search(upper)
    product = _PROD.search(upper)
    vid = _VID.search(upper)
    pid = _PID.search(upper)
    ven = vendor.group(1).replace("_", " ").strip() if vendor else ""
    prod = product.group(1).replace("_", " ").strip() if product else ""
    serial = _serial(raw)
    chunks = raw.replace("/", "\\").split("\\")
    title = " ".join(part for part in (ven, prod) if part)
    if not title and vid:
        code = vid.group(1).upper()
        extra = pid.group(1).upper() if pid else ""
        title = f"USB {code}:{extra}" if extra else f"USB {code}"
    if not title:
        title = chunks[0] if chunks else "устройство"
    return {
        "title": title,
        "vid": vid.group(1).upper() if vid else "",
        "pid": pid.group(1).upper() if pid else "",
        "serial": serial,
        "vendor": ven,
        "product": prod,
    }


def _kind(item: Event) -> str | None:
    if item.src == "out":
        return "отключили"
    if item.src == "in":
        return "подключили"
    if item.id == OUT_ID:
        return "отключили"
    if item.id == IN_ID:
        return "подключили"
    return None


def _score(item: Plug) -> tuple[int, int]:
    return (1 if item.vendor else 0, 1 if item.product else 0)


def _same_device(left: Plug, right: Plug) -> bool:
    if left.instance.upper() == right.instance.upper():
        return True
    if left.serial and left.serial == right.serial and "&" not in left.serial:
        return True
    if left.vid and left.pid and left.vid == right.vid and left.pid == right.pid and left.serial and left.serial == right.serial:
        return True
    return False


def build_sessions(events: list[Event]) -> list[Plug]:
    rows: list[Plug] = []
    ordered = sorted(events, key=lambda item: _stamp(item.when), reverse=True)
    for item in ordered:
        instance = clean_text(item.props[0]) if item.props else ""
        if not instance or not is_plug_device(instance):
            continue
        kind = _kind(item)
        if kind is None:
            continue
        parsed = parse_instance(instance)
        plug = Plug(
            when=item.when,
            kind=kind,
            title=parsed["title"],
            instance=instance,
            vid=parsed["vid"],
            pid=parsed["pid"],
            serial=parsed["serial"],
            vendor=parsed["vendor"],
            product=parsed["product"],
        )
        stamp = _stamp(plug.when)
        replaced = False
        for index, other in enumerate(rows):
            if other.kind != plug.kind:
                continue
            if not _same_device(plug, other):
                continue
            if abs((stamp - _stamp(other.when)).total_seconds()) > _NEAR.total_seconds():
                continue
            if _score(plug) > _score(other):
                rows[index] = plug
            replaced = True
            break
        if not replaced:
            rows.append(plug)
    rows.sort(key=lambda item: _stamp(item.when), reverse=True)
    return rows


def clip_sessions(rows: list[Plug], days: int, now: datetime) -> list[Plug]:
    cutoff = _stamp(now) - timedelta(days=days)
    visible = [item for item in rows if _stamp(item.when) >= cutoff]
    visible.sort(key=lambda item: _stamp(item.when), reverse=True)
    return visible


def row_kind(item: Plug) -> str:
    return item.kind


_MONTHS = "янв фев мар апр май июн июл авг сен окт ноя дек".split()


def format_when(moment: datetime) -> str:
    local = moment.astimezone() if moment.tzinfo else moment
    return f"{local.day} {_MONTHS[local.month - 1]}, {local:%H:%M}"
