"""Сборка подключений, без настоящего settings.json."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from plugpeek.log import parse_payload
from plugpeek.sessions import (
    Event,
    build_sessions,
    clip_sessions,
    is_plug_device,
    parse_instance,
    parse_iso,
)
from plugpeek.settings import load_days, save_days

TZ = timezone(timedelta(hours=5))


def at(day: int, hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(2026, 10, day, hour, minute, second, tzinfo=TZ)


class ParseTests(unittest.TestCase):
    def test_usb_and_skip_pci(self) -> None:
        parsed = parse_instance(r"USB\VID_04E8&PID_6860\R5GL433Y6HT")
        self.assertEqual(parsed["vid"], "04E8")
        self.assertEqual(parsed["pid"], "6860")
        self.assertEqual(parsed["serial"], "R5GL433Y6HT")
        self.assertEqual(parsed["title"], "USB 04E8:6860")
        self.assertTrue(is_plug_device(r"USB\VID_04E8&PID_6860\R5GL433Y6HT"))
        self.assertFalse(is_plug_device(r"PCI\VEN_10DE&DEV_2504\4&3602F3B8&0&0008"))
        self.assertFalse(is_plug_device(r"USB\VID_04E8&PID_6860&MI_00\7&8d790da&0&0000"))
        stick = parse_instance(
            r"SWD\WPDBUSENUM\_??_USBSTOR#DISK&VEN_KINGSTON&PROD_DATATRAVELER_2.0&REV_PMAP#60A44C413CA0BF6059760336&0"
        )
        self.assertEqual(stick["vendor"], "KINGSTON")
        self.assertIn("DATATRAVELER", stick["product"])
        self.assertTrue(is_plug_device(r"USBSTOR#DISK&VEN_KINGSTON&PROD_X"))
        self.assertEqual(stick["serial"], "60A44C413CA0BF6059760336")
        self.assertFalse(is_plug_device(r"USB\ROOT_HUB30\4&1dd9c07d&0&0"))
        self.assertFalse(is_plug_device(r"STORAGE\Volume\_??_USBSTOR#Disk&Ven_Kingston&Prod_X#ABC"))
        self.assertFalse(is_plug_device(r"USB\VID_0000&PID_0002\5&3de9ecd&0&3"))
        hub = parse_instance(r"USB\VID_1B3F&PID_2008\5&3de9ecd&0&6")
        self.assertEqual(hub["serial"], "")
        self.assertEqual(hub["vid"], "1B3F")

    def test_iso_and_payload(self) -> None:
        when = parse_iso("2026-10-28T19:25:33.3877700+05:00")
        self.assertIsNotNone(when)
        with self.assertRaises(Exception):
            parse_payload("ERR отказано в доступе")


class SessionTests(unittest.TestCase):
    def test_in_out_and_dedupe(self) -> None:
        phone = r"USB\VID_04E8&PID_6860\R5GL433Y6HT"
        events = [
            Event(at(28, 19, 25, 33), 400, "in", (phone,)),
            Event(at(28, 19, 25, 34), 400, "in", (phone,)),
            Event(at(25, 16, 29, 54), 420, "out", (r"SWD\WINTUN\{1}",)),
            Event(at(21, 18, 24, 17), 400, "in", (
                r"USBSTOR#DISK&VEN_KINGSTON&PROD_DATATRAVELER_2.0#ABC",
            )),
        ]
        rows = build_sessions(events)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].kind, "подключили")
        self.assertEqual(rows[0].vid, "04E8")
        self.assertEqual(rows[1].vendor, "KINGSTON")

    def test_flash_drive_one_card(self) -> None:
        serial = "60A44C413CA0BF6059760336"
        events = [
            Event(at(21, 18, 24, 17), 400, "in", (rf"USB\VID_0951&PID_1665\{serial}",)),
            Event(at(21, 18, 24, 18), 400, "in", (
                rf"USBSTOR\Disk&Ven_Kingston&Prod_DataTraveler_2.0&Rev_PMAP\{serial}&0",
            )),
            Event(at(21, 18, 24, 18), 400, "in", (
                rf"STORAGE\Volume\_??_USBSTOR#Disk&Ven_Kingston&Prod_DataTraveler_2.0#{serial}",
            )),
        ]
        rows = build_sessions(events)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].vendor, "KINGSTON")
        self.assertEqual(rows[0].serial, serial)

    def test_clip_and_newer_first(self) -> None:
        now = at(29, 21, 0)
        old = Event(at(1, 10, 0), 400, "in", (r"USB\VID_1111&PID_2222\OLD",))
        fresh = Event(at(28, 19, 25, 33), 400, "in", (r"USB\VID_04E8&PID_6860\NEW",))
        shown = clip_sessions(build_sessions([old, fresh]), 14, now)
        self.assertEqual(len(shown), 1)
        self.assertEqual(shown[0].serial, "NEW")


class SettingsTests(unittest.TestCase):
    def test_roundtrip_in_temp(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            save_days(30, root)
            self.assertEqual(load_days(root), 30)
            save_days(3, root)
            self.assertEqual(load_days(root), 14)


if __name__ == "__main__":
    unittest.main()
