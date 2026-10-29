"""Чтение журнала Kernel-PnP. Журнал Security не открываем."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime

CREATE_NO_WINDOW = 0x08000000

_PS = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
try {
    $ev = @(Get-WinEvent -FilterHashtable @{
        LogName = 'Microsoft-Windows-Kernel-PnP/Configuration'
        Id = 400,420
    } -MaxEvents 800 -ErrorAction Stop)
    $ev = @($ev | Where-Object {
        $path = ''
        if ($_.Properties.Count -gt 0) { $path = [string]$_.Properties[0].Value }
        $path -match 'USB|HID\\VID_'
    })
} catch {
    $msg = $_.Exception.Message
    if ($msg -match 'No events were found|не найдено событий') { '[]'; exit 0 }
    Write-Output ('ERR ' + $msg)
    exit 0
}
$ev = @($ev)
if ($ev.Count -eq 0) { '[]'; exit 0 }
$rows = foreach ($e in $ev) {
    $props = @()
    foreach ($p in $e.Properties) { $props += [string]$p.Value }
    $src = 'out'
    if ($e.Id -eq 400) { $src = 'in' }
    [pscustomobject]@{ t = $e.TimeCreated.ToString('o'); id = [int]$e.Id; src = $src; p = @($props) }
}
$rows = @($rows)
if ($rows.Count -eq 1) { '[' + ($rows | ConvertTo-Json -Compress -Depth 6) + ']' }
else { $rows | ConvertTo-Json -Compress -Depth 6 }
"""


class LogError(RuntimeError):
    pass


def parse_payload(text: str) -> list[dict]:
    raw = text.strip()
    if not raw:
        return []
    if raw.startswith("ERR "):
        raise LogError(raw[4:].strip() or "журнал не прочитался")
    start = raw.find("[")
    if start < 0:
        start = raw.find("{")
    if start < 0:
        raise LogError("журнал вернул не список")
    try:
        payload = json.loads(raw[start:])
    except json.JSONDecodeError as exc:
        raise LogError("журнал вернул битый ответ") from exc
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    raise LogError("журнал вернул не список")


def fetch_events(timeout: float = 25.0) -> list[dict]:
    command = [
        "powershell",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        _PS,
    ]
    try:
        done = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
            creationflags=CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired as exc:
        raise LogError("журнал не ответил") from exc
    except OSError as exc:
        raise LogError("powershell не запустился") from exc
    if done.returncode not in (0, None) and not (done.stdout or "").strip():
        message = (done.stderr or "журнал не прочитался").strip().splitlines()
        raise LogError(message[0][:200] if message else "журнал не прочитался")
    return parse_payload(done.stdout or "")


def as_datetime(text: str) -> datetime | None:
    try:
        return datetime.fromisoformat(text.strip())
    except (TypeError, ValueError):
        return None
