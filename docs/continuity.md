# Continuity

Short dated session notes so the next agent or human can pick up without rereading the whole transcript.

## 2026-10-25: Public RTI XP driver code survey

Research only. No Sentinel app code changed.

- Branch: `research/rti-xp-driver-github`
- Write-up: `research/rti-xp-driver-public-code.md`
- Question: what can an Integration Designer XP-series JavaScript `.rtidriver` do for testing, commissioning, diagnostics, and usage analytics, based only on public GitHub / GitLab / Bitbucket / gists (plus public Driver Store and firmware notes where they name an API).

Top public facts:

- Full driver source exists: `The1TrueJoe/rti-http-client`, `ceisenach/rachio_rti_driver`, `ceisenach/homeworks_qs_rti_driver`, `Pulse-Eight/drivers` `RTI/`.
- Proven JS objects: `System.*`, `Config.Get`, `SystemVars.Read/Write`, `HTTP`, `TCP`, `Timer`, `ScheduledEvent`, optional WebSocket upgrade on `HTTP`.
- Other drivers' variables can be watched via XP Diagnostics WebSocket (`/diagnosticswss`, Subscribe/Sysvar), or bound in IDesign (Print To Log). No public JS reflection API.
- No public automatic capture of every panel button. Workaround: map buttons to a logging/HTTP/Two-Way Strings command.
- `.rtidriver` is OLE/CFB. `.apex` is SQLite (already handled in this repo). No other public `.apex` decompiler found.
- Official SDK remains login-walled. Do not copy `XPDriverGuide` / `PackageDriver.exe` from third-party repos.

Open: HTTPServer/Curl/MQTT samples, inbound WebSocket listen, sysvar write over diagnostics WS, System Manager JS access.
