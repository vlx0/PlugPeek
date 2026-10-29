# PlugPeek

**Что втыкали в компьютер.** Когда USB или другое устройство подключили и когда вытащили. Имя берётся из журнала: VID/PID или VEN/PROD, без выдуманных названий.

**Автор:** darkshade ([@vlx0](https://github.com/vlx0))

**365 дней open source** · **неделя 10 — «Следы»** · день 67.

Не CrashPeek: там падения программ. Здесь шнуры и флешки.

---

## Возможности

- список: свежие сверху
- подключили (событие 400) и отключили (событие 420)
- USB, USBSTOR, HID — PCI, монитор и виртуальные диски не показывает
- VID, PID, серийный номер, если Windows их записала
- период 7 / 14 / 30 / 90 дней
- журнал Kernel-PnP/Configuration, без журнала Security и без прав администратора

## Установка

```powershell
git clone https://github.com/vlx0/PlugPeek.git
cd PlugPeek
pythonw run_plugpeek.pyw
```

Или `start.bat`.

Нужен Windows 10+ и Python 3.10+. Внешних зависимостей нет.

## Лицензия

MIT. См. [LICENSE](LICENSE).
