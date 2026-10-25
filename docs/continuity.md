# Continuity

Short dated session notes. Not a substitute for `research/` write-ups or `docs/directives/`.

---

## 25 October 2026 - RTI XP driver forum research (public sources only)

Branch: `research/rti-xp-driver-forums`

Wrote `research/rti-xp-driver-forums.md`. No app code changed.

Jamie is scoping an XP-series Integration Designer driver for testing, commissioning, diagnostics, and usage analytics (heat maps, most-used buttons, source/feature use, device health, feedback checks, outbound event logging).

Public-web result in one line: XP Diagnostics plus RTiQ plus helper/HTTP/email/Pushover drivers already cover health, bound variables, and outbound posts. There is no native button heat map. Press capture needs a hook on each macro. The dealer forum and SDK stay login-walled.

Strongest public facts to carry forward:

- Browser XP Diagnostics at the processor IP: uptime, memory, SystemVar load, per-driver CPU/RAM, Sysvars, Flags, logs, Get Report, Log User Message.
- Onboard diagnostics miss startup; Chowmain says disable it and use the older XP Diagnostics driver or TraceViewer.
- Drivers are JavaScript on one script thread. Firmware documents HTTP, MQTT, SSH, Ping, Curl, OAuth, port-80 sharing, and repeated memory/Ping freezes.
- RTiQ is cloud health (ping, IP, sysvar, email/SMS, remote macros), not usage analytics. "RTI Connect" is not an XP product; AVPro Connect is the dealer login.
- System Manager tracks room/source/device state for programming. Public pages do not expose it as an API or analytics feed.
- Integer Helper, Lambda, Logic Helper, and Button SysVar Events bind to other drivers' variables from ID dropdowns.
- Outbound: Email SMTP, Pushover, HTTP Toolkit, HA Fire Event. Inbound: HTTP Server (port > 1024), HTTP Commander JSON vars.
- Limits: finite SystemVar pool, ~10-50k typical driver RAM, 80% memory warning, XP 10/100 Ethernet, 512 MB flash.

Next useful step if Jamie wants it: a one-page driver-shape proposal (logger function + HTTP post + optional sysvar bindings) that stays inside those public limits, or a dealer-forum pass if login is later authorized. Do not implement until asked.
