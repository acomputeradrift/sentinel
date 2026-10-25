# Public RTI XP driver code survey

Date: 25 October 2026  
Scope: public GitHub (and GitLab / Bitbucket / gist) sources that show what an RTI Integration Designer XP-series JavaScript driver can do. No app code was changed. Official RTI / AVPro dealer portals were not logged into. Nothing from paid or NDA SDK packages was copied into this repo.

Search coverage: GitHub repo search, GitHub code search (until rate-limited), `gh` user/repo listing, web search, and shallow clones of every useful match. GitLab and Bitbucket returned no Integration Designer / `.rtidriver` driver source. Public gists matching these terms were RTI Connext DDS samples, not XP processor drivers. Official org `@rticorp` has zero public repos. Org `@rtidriver` only hosts generic JS polyfills (`js-base64`, `JSON-js`), not XP driver source.

A second class of public pages (RTI Driver Store listings and the public XP firmware changelog) is included only where it names a capability that public source does not yet show. Those pages are product descriptions, not driver source.

---

## Strongest findings

1. **A complete, modern XP driver can be written from public source.** [The1TrueJoe/rti-http-client](https://github.com/The1TrueJoe/rti-http-client) is a full Integration Designer 9.6+ package: JavaScript, XML manifest, config, events, variables, a pure-Python `.rtidriver` packager, and CI. It proves outbound TCP, HTTP request construction, `SystemVars` read/write, `System.SignalEvent`, `System.Print`, `System.FirmwareVersion`, `System.Version`, and `System.ConvertFromUTF8`. It also states a hard limit: **plain HTTP only; the RTI TCP stack in that driver does not do HTTPS**.

2. **Older public drivers already do HTTPS, timers, scheduled jobs, and TCP reconnect.** [ceisenach/rachio_rti_driver](https://github.com/ceisenach/rachio_rti_driver) opens `HTTP` to `api.rach.io:443`, calls `StartSSLHandshake()`, and polls with `new Timer()`. [ceisenach/homeworks_qs_rti_driver](https://github.com/ceisenach/homeworks_qs_rti_driver) opens `new TCP(...)`, logs in, enables Lutron monitoring, turns keypad press/hold/release into `System.SignalEvent(...)`, and uses `new ScheduledEvent(...)` for periodic LED sync.

3. **Outbound HTTP GET is a first-class SDK helper.** Pulse-Eight's public neo / CEC / ProAmp drivers call `System.GetURL(url)` on a 1-second `Timer` and write the JSON result into `SystemVars`. Same pattern across [Pulse-Eight/drivers `RTI/`](https://github.com/Pulse-Eight/drivers/tree/master/RTI).

4. **The processor can expose a diagnostics WebSocket that streams every system variable.** [Aaron-Gardien/rti-matter-bridge](https://github.com/Aaron-Gardien/rti-matter-bridge) documents `ws://<xp-ip>:<port>/diagnosticswss` and this subscribe/push protocol:

   ```json
   {"type":"Subscribe","resource":"Sysvar","value":{"id":966,"status":true}}
   ```

   Response:

   ```json
   {"messageType":"Sysvar","sysvarid":966,"sysvarval":"19:21"}
   ```

   The same repo's XP driver source uses `new HTTP(...)`, `UpgradeWebsocket()`, `WebsocketVersion = 13`, and writes subscribe JSON with `g_http.Write(...)`. That is the strongest public proof that **another driver's variables can be observed**, but it is via the diagnostics WebSocket (numeric sysvar IDs), not via `SystemVars.Read("some other driver")` inside JS.

5. **There is no public hook that silently captures every panel button press.** Public workarounds all require programming: map the button to a driver command (Two-Way Strings TCP, HTTP client string, Print To Log, RelayServer slot). Lutron keypad presses are captured only because that device's protocol reports them. Companion module request [#1052](https://github.com/bitfocus/companion-module-requests/issues/1052) asked for two-way RTI variable subscribe from outside and was closed without an implementation.

6. **Logging events off the processor to a server is already a normal driver job.** Pulse-Eight and rti-http-client send HTTP. Rachio sends HTTPS. Home Assistant bridges send TCP strings. Driver Store HTTP / TCP Toolkits host a browser page on the processor and export config. Official XP Diagnostics already serves processor health in a browser on port 80.

7. **System Manager / processor info is visible from outside if XP Diagnostics is installed.** Public Driver Store text for [XP Diagnostics](https://driverstore.rticontrol.com/driver/xp-diagnostics) lists Name, IP, MAC, Up Time, Firmware, Memory Used, SystemVar Load, per-driver CPU/memory, Sysvars, Flags, and a log tab. Firmware notes at [firmware.avproglobal.com/downloads/rti/](https://firmware.avproglobal.com/downloads/rti/) name later SDK objects (`Curl`, `HTTPServer`, `TCPServer`, `MQTT`, `SSH`, `MulticastUDP`, `Ping`, OAuth, `HTTP.Open()`). No public GitHub driver source was found that constructs `new MQTT` or `new HTTPServer`.

8. **`.rtidriver` is an OLE/CFB container of zlib-compressed streams.** Unpack: [ceisenach/RTI_tools](https://github.com/ceisenach/RTI_tools). Pack: [The1TrueJoe/rti-http-client `scripts/package-driver.py`](https://github.com/The1TrueJoe/rti-http-client/blob/main/scripts/package-driver.py). Typical streams: `DriverManifest.xml`, `ConfigSettings.xml`, `SystemFunctions.xml`, `SystemEvents.xml`, `SystemVariables.xml`, `instructions.rtf`, one or more `.js` processor scripts, optional `DynamicConfigInfo`.

9. **`.apex` is a SQLite database.** That is already documented in this Sentinel repo (`research/initial-testing/`). Public third-party GitHub does not contain a competing `.apex` decompiler. Sample `.apex` / `.rti` project files appear in [Aaron-Gardien/SDK_Climate](https://github.com/Aaron-Gardien/SDK_Climate) and [Matioliflavio/RTI-Drivers](https://github.com/Matioliflavio/RTI-Drivers).

10. **Outside-the-processor control of XP itself is thin.** Home Assistant and Node-RED talks to XP by loading RTI's built-in Two-Way Strings driver and exchanging TCP strings. AD-series amps have their own Telnet protocol and are not XP processors. ZRP-6 open firmware is a replacement OS for an older box, not an XP driver.

---

## Repo table

| URL | Author | Last update (GitHub) | License | What it is | RTI APIs / objects (exact names in code) | What it proves |
|---|---|---|---|---|---|---|
| [The1TrueJoe/rti-http-client](https://github.com/The1TrueJoe/rti-http-client) | Joey Telaak (`The1TrueJoe`) | 24 Oct 2026 | None declared | Full XP HTTP client `.rtidriver` + Python packager | `System.Print`, `System.FirmwareVersion`, `System.Version`, `System.ConvertFromUTF8`, `System.SignalEvent`, `Config.Get`, `SystemVars.Write`, `SystemVars.Read`, `new TCP(rx, host, port)`, `TCP.Write`, `TCP.OnConnectFunc`, `TCP.OnDisconnectFunc`, `TCP.AddRxHTTPFraming` | Outbound HTTP over TCP; events; counters; **HTTPS not supported** on this TCP path |
| [ceisenach/rachio_rti_driver](https://github.com/ceisenach/rachio_rti_driver) | Carson Eisenach | 30 Jul 2018 | GPL-3.0 | XP-8 Rachio cloud driver | `new HTTP('OnCommRX')`, `HTTP.Open(host, 443)`, `HTTP.StartSSLHandshake`, `OnSSLHandshakeOKFunc`, `OnSSLHandshakeFailedFunc`, `OnConnectFunc`, `OnDisconnectFunc`, `OnConnectFailedFunc`, `HTTP.ConnectState`, `HTTP.Close`, `HTTP.Write`, `new Timer()`, `Timer.Start`, `System.LogInfo`, `SystemVars.Write`, `Config.Get` | Outbound HTTPS; queued requests; periodic poll; SSL callbacks |
| [ceisenach/homeworks_qs_rti_driver](https://github.com/ceisenach/homeworks_qs_rti_driver) | Carson Eisenach | 28 Sep 2018 | GPL-3.0 | XP-8 Lutron Homeworks QS driver | `new TCP(OnCommRX)`, `TCP.Open`, `TCP.Write`, `TCP.Close`, `TCP.SetTxInterMsgDelay`, `new Timer()`, `new ScheduledEvent(fn,"Periodic","Minutes",n)`, `ScheduledEvent.Enable`, `System.SignalEvent`, `SystemVars.Write`, `System.LogInfo` | Persistent TCP; keypad press/hold/release events; periodic jobs |
| [ceisenach/RTI_tools](https://github.com/ceisenach/RTI_tools) | Carson Eisenach | 9 Aug 2026 (repo metadata; last push 2018) | None declared | `.rtidriver` unpacker | n/a (Python `olefile` + `zlib`) | `.rtidriver` = OLE streams, often zlib-compressed JS/XML/RTF |
| [Pulse-Eight/drivers](https://github.com/Pulse-Eight/drivers) (`RTI/` tree) | Pulse-Eight | 19 Jun 2026 | Apache-2.0 | neo:8 / neo:4 / neo Modular / OneIP / ProAmp8 / CEC source+sink | `System.GetURL`, `new Timer()`, `Timer.Start`, `new HTTP(fn)`, `HTTP.Open`, `HTTP.Write`, `HTTP.Read`, `HTTP.Close`, `HTTP.OnConnectFunc`, `HTTP.OpenState`, `HTTP.ConnectState`, `SystemVars.Write`, `Config.Get`, `System.Print` | Polling HTTP GET; JSON parse; feedback into sysvars; multi-script manifest |
| [Aaron-Gardien/SDK_Climate](https://github.com/Aaron-Gardien/SDK_Climate) | posted by Aaron-Gardien; JS header says Copyright 2017 Remote Technologies Inc. | 30 Dec 2024 | None declared | Official-looking SDK virtual climate sample + `.apex` / `.rti` | `System.GetLocalTimeInSeconds`, `System.GetUTCTimeInSeconds`, `new Timer()`, `Timer.Start`, `Timer.Stop`, `Timer.UseHandleInCallbacks`, `Timer.Handle`, `SystemVars.Read`, `SystemVars.Write`, `System.SignalEvent`, `System.LogInfo`, `Config.Get` | Processor clock; timer handles; many named sysvars/events; **no network** |
| [Aaron-Gardien/rti-matter-bridge](https://github.com/Aaron-Gardien/rti-matter-bridge) | Aaron-Gardien | pushed 11 Jun 2026 | None declared | XP driver + Python clients for diagnostics WebSocket / HomeKit / Matter | Driver JS: `new HTTP(OnCommHttpRx)`, `OnConnectFunc`, `OnDisconnectFunc`, `OnConnectFailedFunc`, `OnWebsocketUpgradeOKFunc`, `OnWebsocketUpgradeFailedFunc`, `HTTP.WebsocketVersion`, `HTTP.UseHandleInCallbacks`, `HTTP.Open`, `HTTP.UpgradeWebsocket`, `HTTP.Write`, `HTTP.Close`, `Config.Get`, `System.Print`. Wire protocol: `Subscribe` / `Sysvar` | Outbound WebSocket from a driver; subscribe to numeric sysvars; boot dump of variables |
| [Aaron-Gardien/homebridge-rti-proxy](https://github.com/Aaron-Gardien/homebridge-rti-proxy) | Aaron-Gardien | 17 Jul 2025 | None declared | Homebridge plugin; JSON WebSocket server for RTI clients | n/a (Node, not XP JS) | An XP driver can be a WebSocket **client** of Homebridge |
| [CreativeLightingAdmin/eDIDIO-Integrations](https://github.com/CreativeLightingAdmin/eDIDIO-Integrations) (`RTI Driver/`) | Michael Howes / Control Freak | 29 Sep 2026 | MIT (package.json) | ID 11 driver logic, tested off-device | Binding file uses placeholders (`System.Device.send`, `System.setVariable`, `System.print`) and says names vary | Constrained JS engine (no npm); two-way TCP/IP template; keep-alive timer; **exact DDK names not wired** |
| [mefranklin6/HomeAssistant_RTI_Remote](https://github.com/mefranklin6/HomeAssistant_RTI_Remote) | mefranklin6 | 24 Oct 2026 | MIT | Node-RED + Pyscript + RTI Two-Way Strings | No XP JS. Uses store driver [Two-Way Strings](https://driverstore.rticontrol.com/driver/rti-two-way-strings) over TCP | Button-to-string export; HA state back into RTI RX prefixes; **SDK not required** |
| [srhunt-cyber/RTI-AD8x-Home-Assistant-bridge](https://github.com/srhunt-cyber/RTI-AD8x-Home-Assistant-bridge) | Steve Hunt | 19 Sep 2026 | MIT (LICENSE file) | Telnet poll of AD-4x / AD-8x amps to MQTT / HA | n/a (talks to the amp, not XP) | Device online/offline health for AD-series; usage of sources/volume; not an XP API |
| [Matioliflavio/RTI-Drivers](https://github.com/Matioliflavio/RTI-Drivers) | Matioliflavio | 10 Oct 2026 | MIT | Binary `.rtidriver` collection + sample `.apex` | Source not published (binaries only) | Third-party drivers and example projects exist in the open; unpack with RTI_tools if needed |
| [The1TrueJoe/rti-zrp6](https://github.com/The1TrueJoe/rti-zrp6) | Joseph Telaak | 30 Sep 2026 | MIT | Replacement firmware for ZRP-6 + Control4 driver | MQTT / HTTP on the replacement OS; **no XP JS** | Older RTI hardware can be bridged to Control4/MQTT after a full firmware replace. Not an XP-6/8 path |
| [The1TrueJoe/rti-bml-scripts](https://github.com/The1TrueJoe/rti-bml-scripts) | The1TrueJoe | 27 May 2026 | None declared | Pack/extract `.bml` icon libraries | n/a | File-format reader for old RTI bitmap libraries, not processors |
| [The1TrueJoe/t2i-zephyr](https://github.com/The1TrueJoe/t2i-zephyr) | The1TrueJoe | 29 Sep 2026 | None declared | Zephyr firmware for T2i remote | n/a | Handheld remote research, not XP driver API |
| [acomputeradrift/sentinel](https://github.com/acomputeradrift/sentinel) (this repo) | Jamie Feeny / Sentinel | current | (repo license as declared) | `.apex` extract / commissioning | SQLite tables `Events`, `DriverConfig`, `DriverData`, macros, tags | `.apex` structure and driver events are readable offline |

Not useful after inspection (listed so the search is complete):

| URL | Why skipped |
|---|---|
| [github.com/rticorp](https://github.com/rticorp) | Official org, 0 public repos |
| [github.com/rtidriver](https://github.com/rtidriver) | Generic Base64/JSON polyfills only |
| [rticommunity/rticonnextdds-connector-js](https://github.com/rticommunity/rticonnextdds-connector-js) | Wrong RTI (Connext DDS) |
| GitLab / Bitbucket searches for `rtidriver`, Integration Designer, XP-8 driver | No matching driver source |
| Public gists for `SystemVars` / `rtidriver` | Connext DDS or unrelated |

### Public product pages (no source in this survey)

These are Driver Store or firmware pages, not GitHub source. They still name capabilities:

| Page | Claim that matters |
|---|---|
| [XP Diagnostics](https://driverstore.rticontrol.com/driver/xp-diagnostics) | Browser UI on processor IP (port 80). Status, driver CPU/mem, Sysvars, Flags, logs, UPnP |
| [Print To Log](https://driverstore.rticontrol.com/driver/coupe-automation-print-to-log) | Print messages (and other drivers' bound vars via `<F#>`, `<I#>`, `<S#>` or names) into XP Diagnostics |
| [HTTP Server Driver](https://driverstore.rticontrol.com/driver/rti-http-server-driver) | Processor listens on a port >1024 and fires events from HTTP GET |
| [HTTP Toolkit](https://driverstore.rticontrol.com/driver/david-bowdler-http-toolkit) | 50 HTTP/HTTPS slots, 80 feedbacks, browser page on port 9033, TLS, Bearer/Basic auth |
| [TCP Toolkit](https://driverstore.rticontrol.com/driver/david-bowdler-tcp-toolkit) | Same idea over raw TCP, browser page on 9031, Connected/Disconnected events |
| [RS-232 Toolkit](https://driverstore.rticontrol.com/driver/david-bowdler-rs-232-toolkit) | Same engine on serial; optional telnet debug with "raw JavaScript eval" |
| [RelayServer](https://driverstore.rticontrol.com/driver/qinghua-wang-relayserver) | Driver is a WebSocket **client** to a self-hosted relay. Author states the scripting SDK has **no listen/accept** so a browser cannot connect to the driver directly. 100 button slots, 24 sliders |
| [Home Assistant Bridge](https://driverstore.rticontrol.com/driver/joe-liggero-home-assistant-bridge) | XP is a WebSocket client of HA `subscribe_entities` |
| [Hubitat Bridge](https://driverstore.rticontrol.com/driver/joe-liggero-hubitat-bridge) | HTTP to Maker API + WebSocket eventsocket |
| [Two-Way Strings](https://driverstore.rticontrol.com/driver/rti-two-way-strings) | Built-in TCP string TX/RX used by the HA/Node-RED project |
| [XP firmware notes](https://firmware.avproglobal.com/downloads/rti/) | Runtime 24.12.10 adds `Curl`. Older notes mention `HTTP.Open()`, `HTTPServer`, `TCPServer`, `Serial`, `SSH`, `MulticastUDP`, `MQTT`, `Ping`, OAuth, SysVar subscription speed-up. Ports < 1025 reserved for system use |

SDK caution: `Aaron-Gardien/rti-matter-bridge` hosts files named `PackageDriver.exe` and `RTI SDK/XPDriverGuide_v25.pdf`. Those look like official SDK artifacts that someone uploaded. They were **not** copied here and are **not** quoted. Official docs remain login-walled at [developer.rticontrol.com](https://developer.rticontrol.com/).

---

## Capability by capability

### Testing

What public code can help a test / commissioning driver do:

- **Fire a named command from a button or macro.** `SystemFunctions.xml` maps a UI name to a JS export. Example from rti-http-client:

  ```xml
  <function name="Send HTTP String" export="SendHTTP" repeatrate="0">
    <parameter name="HTTP string, path, or URL" type="string" default="/"/>
  </function>
  ```

- **Raise a driver event that Integration Designer macros can catch.** rti-http-client:

  ```javascript
  System.SignalEvent("CONNECT");
  System.SignalEvent("RESPONSE");
  System.SignalEvent("ERROR");
  ```

  Homeworks QS builds event tags from live keypad traffic (`Device1_press`, `Device1_hold`, …) and signals them. That is device-button capture, not RTI panel-button capture.

- **Write live values a test UI can bind.** Every source driver uses `SystemVars.Write(name, value)` and `SystemVars.Read(name)`. Types in XML: boolean, integer, string.

- **Poll a device and fail visibly.** Pulse-Eight `Timer` + `System.GetURL` + `try/catch` + `System.Print(err)`. Rachio checks `ConnectState` and SSL handshake success.

- **Virtual Panel / off-device tests.** eDIDIO documents building a test interface, launching RTI Virtual Panel, and unit-testing driver logic in Node with an injected `{send, setVariable, log}` host. SDK Climate is a no-network virtual thermostat used to exercise climate templates.

- **Local HTTP test sink.** rti-http-client ships `test_server.py` so a driver can be pointed at a LAN logger.

Not shown in public XP JS:

- A built-in "test all buttons on this page" API.
- A way to query Integration Designer project structure from the running processor.
- A PASS/FAIL result store that survives reboot (sysvars reset unless the driver rewrites them; no public file API).

Workaround for structured test results: send HTTP/TCP to Sentinel (or any server) from a command bound on each test button, or from a dedicated "log this target" driver.

### Commissioning

Public patterns that match field commissioning:

- **Browser page on the processor.** Official HTTP Server Driver and the Bowdler toolkits serve a control/authoring page (ports 8080 / 9030 / 9031 / 9033). XP Diagnostics is the same idea for health. Public GitHub JS does **not** show `new HTTPServer(...)`; the store drivers and firmware notes are the evidence that inbound HTTP exists.
- **Live command and feedback authoring.** TCP / HTTP / RS-232 Toolkits: Send & Capture, traffic log, `.driverconfig` XML export. Useful model for a commissioning helper driver even without their source.
- **Import/export driver config.** Toolkits export `.driverconfig` for IDesign import. rti-http-client uses `DynamicConfigInfo` so the number of HTTP strings can show/hide categories.
- **Virtual Panel.** eDIDIO README: test commands on the emulator before touching the house.
- **Two-way connection status.** eDIDIO `ConnectionStatus` = Connected / Disconnected. rti-http-client `Connected` boolean + CONNECT/DISCONNECT events. Homeworks auto-reconnects.

RelayServer's author says the SDK **cannot listen** for a browser WebSocket, so they bounce through an external Node relay. That conflicts with HTTP Server Driver / HTTPServer firmware notes for **HTTP**. Treat "no inbound WebSocket accept" as likely, and "no inbound anything" as overstated.

### Diagnostics

Proven from public source or public Driver Store text:

| Need | Evidence |
|---|---|
| Print to XP Diagnostics log | `System.Print(...)` in every public driver; `System.LogInfo(level, msg)` in Rachio, Homeworks, SDK Climate (levels 1, 2, 3 seen). Print To Log store driver writes at Connections / User Actions / Messages |
| Processor firmware / runtime | `System.FirmwareVersion`, `System.Version` (rti-http-client) |
| Processor clock | `System.GetLocalTimeInSeconds()`, `System.GetUTCTimeInSeconds()` (SDK Climate) |
| Per-driver CPU, memory, ports | XP Diagnostics Drivers tab (store page, no source) |
| Memory leak / sysvar exhaustion | XP Diagnostics Status: Memory Used, SystemVar Load (80% warning) |
| Watch any sysvar / flag | XP Diagnostics Sysvars/Flags tabs; diagnostics WebSocket `Subscribe`/`Sysvar` |
| Device online/offline | TCP/HTTP connect callbacks; toolkit Connected/Disconnected events; AD-8x bridge publishes `status` online/offline after missed polls |
| UPnP / RTiPanel / Zigbee | XP Diagnostics tabs (store page) |
| Raw JS eval on processor | RS-232 Toolkit store text claims an optional telnet console with JavaScript eval. No public source. Treat as a dealer-tool claim, not a documented API |

`System.Print` is the supported log path. There is no public `console.log`. Debug flags are almost always `Config.Get("DebugTrace") == "true"`.

### Analytics (heat maps, most-used buttons/sources)

No public driver implements a heat map or usage rollup.

What public code **does** prove you could build one:

- A button can call a driver function with a string (rti-http-client `SendHTTP`, Two-Way Strings `cmd:device:action`).
- That function can timestamp (`new Date()` in matter-bridge; processor clock in SDK Climate) and increment a counter (`SystemVars.Read` + `Write`).
- It can POST the event off-box (HTTP/TCP/HTTPS).
- Diagnostics WebSocket can stream **sysvar changes** (source power, volume, true/false flags). That is feature/source usage if those vars already exist.
- Print To Log can interpolate other drivers' bound variables into a log line.

What public code **does not** prove:

- Automatic capture of every panel button without programming each one.
- Reading the current page name, room, or source from JS (no `System.CurrentPage` or similar in public source). `Selected Room` is an Integration Designer runtime variable in this repo's scope docs, not a driver API shown on GitHub.
- Durable on-processor storage beyond sysvars. matter-bridge `ExportVariableMapping` only `dbgPrint`s JSON ("in a real implementation, this would save to a file").
- A public RTIPanel usage API.

Practical analytics design from public evidence: add one analytics driver; bind important buttons/macros to it (or to Two-Way Strings); POST `{button, room, source, ts}` to a server; optionally also subscribe to diagnostics sysvars for device-state time series. Heat maps then live on the server, not on the XP.

### Data export

Proven outbound:

- `System.GetURL(url)` blocking HTTP GET (Pulse-Eight).
- `new TCP` / `new HTTP` with `Write` of raw HTTP or JSON (rti-http-client, Rachio, CEC, matter-bridge).
- HTTPS via `HTTP.StartSSLHandshake()` on port 443 (Rachio). rti-http-client explicitly cannot.
- WebSocket client upgrade on `HTTP` (matter-bridge; HA/Hubitat/RelayServer store drivers).
- TCP strings to Node-RED / HA (HomeAssistant_RTI_Remote).
- MQTT from **outside** (AD-8x bridge, ZRP-6 replacement firmware). Firmware notes say an `MQTT` object exists on newer XP runtimes; no public XP JS uses it.

Not proven in public XP JS:

- Writing a file on the processor.
- Pushing to a cloud analytics API with modern TLS stacks on old firmware (use Curl on runtime 24.12.10+, or a LAN proxy).
- Inbound WebSocket server inside a custom driver (RelayServer says no).

Charset: rti-http-client stores responses with `System.ConvertFromUTF8(str)`.

### System Manager / processor info access

Two different things get called "System Manager":

1. **Integration Designer System Manager** (activities, shared sources). AVPro training pages exist. **No public GitHub tool talks to it.** No public driver API name for System Manager objects was found.
2. **Live processor / diagnostics information.**

Public path to (2):

- Install XP Diagnostics, open `http://<processor-ip>/` (port 80 on v1.2).
- Or connect to `ws://<processor-ip>/diagnosticswss` (port 80 in "RTI driver documentation" comments; matter-bridge also tried 1234).
- From **inside** a driver: `System.FirmwareVersion`, `System.Version`, clock helpers, `System.Print` / `System.LogInfo`. No public `System.GetMAC`, `System.GetIP`, or memory API. Those fields appear only in the Diagnostics HTML.

matter-bridge `rti_port_scanner.py` probes 80, 1234, 1883 (MQTT), 5000 and paths `/diagnostics`, `/diagnosticswss`. That is reconnaissance of one lab processor, not an official port map.

### Reading internal or other drivers' variables

Three layers, do not mix them up:

| Layer | Possible? | Evidence |
|---|---|---|
| This driver's own sysvars | Yes | `SystemVars.Read` / `Write` of names declared in this driver's `SystemVariables.xml` (or written at runtime; rti-http-client notes ID 9.6 uses runtime writes) |
| Other drivers' variables, bound in Integration Designer | Yes, as a product feature | Print To Log: configure up to 50 flag/int/string refs; expand `<F1>` / `<I1>` / `<S1>` or names in a message. XP Diagnostics Sysvars tab: pick any driver and variable. This is **programmer binding**, not JS reflection |
| Other drivers' variables, from JS with no binding | Not shown | No `SystemVars.Read("OtherDriver.Power")` in any public script |
| Other drivers' variables, by numeric ID over diagnostics WebSocket | Yes | matter-bridge Subscribe/Sysvar. IDs are opaque; names are not in the push (`sysvarid` + `sysvarval` only). Boot may dump many vars |
| Subscribe to changes of this driver's vars from **outside** | Partial | Diagnostics WebSocket. Companion request for a documented TCP subscribe API was never built |

Print To Log also special-cases Clock 3.4 `Date` and `Time`.

### Button press capture

| Source of the press | Can a driver see it? | How |
|---|---|---|
| RTI panel / RTiPanel / hard key, if the programmer maps the button to this driver's command | Yes | `SystemFunctions.xml` export. Two-Way Strings TX string. HTTP client string. RelayServer slot 1-100 |
| RTI panel, automatically, all buttons | **No public API** | Would need System Manager hooks or a firmware event that no public driver uses |
| Lutron (or similar) keypad that reports presses on TCP | Yes | Homeworks QS `~DEVICE,` frames → `System.SignalEvent` |
| HA / Homebridge / Hubitat device events | Yes, inbound to RTI | Two-Way Strings RX prefixes; HA/Hubitat store bridges; homebridge-rti-proxy |
| RTI handheld on a stock XP | Not in public XP JS | ZRP-6 open firmware publishes `remote/code` only on that replacement OS |

HomeAssistant_RTI_Remote is the cleanest "press goes off-box" pattern:

```
cmd:kitchen_main_lights:on
```

Node-RED fires HA event `RTI_Rx`; Pyscript splits `mode:device:command`. Reverse path uses `device:state:suffix` into a second Two-Way Strings driver. On TCP connect, RTI asks `cmd:states:get` so panels are not left null after reboot.

That is also the honest limit: **without the SDK, you cannot sync the two systems automatically.** You program each string. A custom analytics/testing driver with the SDK removes that mapping pain for *its own* commands, but still cannot see unmapped buttons.

---

## File formats and outside-the-processor tools

**.rtidriver**

- OLE/CFB. Streams zlib-compressed. Unpack: `ceisenach/RTI_tools/extract_rti.py` (`olefile`). Pack: `rti-http-client/scripts/package-driver.py` (no npm). Pulse-Eight and matter-bridge still ship `PackageDriver.exe`.
- Manifest `processorType="XP-8"` is used even when the README says XP-6/XP-8 (rti-http-client) or "most modern processors" (HA remote, developed on XP-3).
- Multiple `<processorScript stream="..."/>` entries run in order (Pulse-Eight `json2.js`, `p8core.js`, `p8routing.js`).

**.apex / .rti**

- `.apex` = SQLite. This repo's `research/initial-testing/` and `src/sentinel/extraction/` are the public extractor. No other GitHub decompiler found.
- `.rti` sample projects sit next to SDK Climate and Pulse-Eight `template/Pulse Eight test for XP-3.rti`.
- Matioliflavio `Exemplos/*.apex` are example Integration Designer projects, not parsers.

**AD-series**

- Separate Ethernet Telnet protocol. HA MQTT bridge polls power/mute/source/volume/bass/treble and publishes health. Useful for amp analytics, not XP button analytics.

**Control4**

- No Control4-to-XP bridge source found. `rti-zrp6` is Control4 → replacement ZRP-6 firmware over MQTT. The1TrueJoe's other public work is Control4-centric (`openHC`, `control4-appletv-remote`) and does not talk to XP.

**Hubitat / Home Assistant / Node-RED**

- HA/Hubitat **native** XP bridges live on the Driver Store (closed source). Public GitHub is the Two-Way Strings + Node-RED pattern, plus homebridge-rti-proxy.

**RTiPanel**

- No public protocol spec. Firmware notes mention RTiPanel connection freezes. RelayServer exists specifically because the official app protocol is unpublished.

---

## API name checklist (seen in public XP JavaScript)

Globals and system:

- `System.Print`
- `System.LogInfo(level, message)` with levels 1, 2, 3
- `System.SignalEvent(tag)`
- `System.GetURL(url)`
- `System.FirmwareVersion`
- `System.Version`
- `System.ConvertFromUTF8(str)`
- `System.GetLocalTimeInSeconds()`
- `System.GetUTCTimeInSeconds()`
- `Config.Get(name)` (string compare to `"true"` is the usual boolean)
- `SystemVars.Write(name, value)`
- `SystemVars.Read(name)`

HTTP:

- `new HTTP(callbackNameOrFunction)`
- `.Open(host, port)`, `.Close()`, `.Write(data)`, `.Read(timeoutMs)`
- `.OnConnectFunc`, `.OnDisconnectFunc`, `.OnConnectFailedFunc`
- `.OnSSLHandshakeOKFunc`, `.OnSSLHandshakeFailedFunc`, `.StartSSLHandshake()`
- `.OnWebsocketUpgradeOKFunc`, `.OnWebsocketUpgradeFailedFunc`, `.UpgradeWebsocket()`, `.WebsocketVersion`, `.UseHandleInCallbacks`
- `.OpenState`, `.ConnectState`

TCP:

- `new TCP(rxCallback)` or `new TCP(rxCallback, host, port)`
- `.Open(host, port)`, `.Close()`, `.Write(data)`
- `.OnConnectFunc`, `.OnDisconnectFunc`, `.OnConnectFailedFunc`
- `.SetTxInterMsgDelay(ms)`
- `.AddRxHTTPFraming()` (optional; rti-http-client guards with try/catch)

Time:

- `new Timer()`, `.Start(fn, ms)`, `.Stop()`, `.UseHandleInCallbacks`, `.Handle`
- `new ScheduledEvent(fn, "Periodic", "Minutes", n)`, `.Enable()`
- Standard `Date` in matter-bridge; `setTimeout` appears there too (may or may not be supported on all runtimes; Pulse-Eight/Rachio use `Timer`)

XML package:

- `DriverManifest.xml`: `id`, `name`, `author`, `processorType`, `minimumSoftwareVersion`, `minimumRuntimeVersion`, stream names, `driverStore` / `developer` GUID (newer)
- `ConfigSettings.xml`, `SystemFunctions.xml`, `SystemEvents.xml` (`tag=` matches `SignalEvent`), `SystemVariables.xml` (`sysvar=` matches `SystemVars` names), `instructions.rtf`, `DynamicConfigInfo`

Named in firmware notes but **not** found in public JS:

- `Curl`
- `HTTPServer`
- `TCPServer`
- `MQTT`
- `SSH`
- `MulticastUDP`
- `Ping`
- OAuth dashboard (port 80 shared)

Placeholder names in eDIDIO only (do not treat as real API): `System.Device.send`, `System.setVariable`, `System.print`.

---

## Gaps and open questions

1. **Does a driver JS API exist to enumerate or subscribe to other drivers' variables without the diagnostics WebSocket and without IDesign bindings?** Public source says no. Print To Log and XP Diagnostics do it through the product UI.

2. **Can a custom driver host HTTP or HTTPServer the way HTTP Toolkit does?** Firmware and store pages say yes. No public source shows the constructor. RelayServer's "outbound only" claim needs a firmware-version footnote.

3. **Is `/diagnosticswss` always on port 80, and does it require the XP Diagnostics driver?** matter-bridge treats it as the diagnostics interface. Official XP Diagnostics v1.2 "set port to 80". Whether stock firmware without that driver still speaks the WebSocket is unknown from public code.

4. **Sysvar IDs vs names.** Subscribe messages use numeric `id`. Pushes return `sysvarid` + `sysvarval` only. How to map ID 966 to "Current Time" from a driver without scraping the Diagnostics HTML is not shown.

5. **Can you write a sysvar (change another driver) over that WebSocket, or only subscribe?** matter-bridge README says command sending is future work. No public `Set` message example.

6. **Button, page, room, source identity inside a driver.** No public `System.GetCurrentRoom` / page / button ID. Sentinel already extracts those from `.apex`. Runtime capture still needs explicit programming or an unpublished System Manager API.

7. **On-processor durable storage.** No public file, SQLite, or key-value API. Analytics must leave the box.

8. **MQTT / Curl / SSH / Ping from JS.** Named in firmware. No public sample. Worth a dealer-SDK check before designing around them.

9. **RTiPanel and official mobile-app protocol.** Still unpublished. RelayServer is the public workaround.

10. **XP-3 vs XP-6s vs XP-8v vs XP-3 vs older.** Manifests say `processorType="XP-8"` while READMEs claim XP-3/6 compatibility. What actually fails on XP-3 (HTTPS, HTTPServer, Curl, WebSocket upgrade) is not tabulated in public source. rti-http-client is explicitly for "older" controllers and avoids TLS.

11. **System Manager as a programmable object.** Training exists; GitHub does not. If a testing driver needs "which source is active in this room", that may already be a System Manager variable that can be **bound** (Print To Log style) even if JS cannot discover it.

12. **GitLab / Bitbucket / gists.** Re-check later; this pass found none. Driver Store authors (Joe Liggero, David Bowdler, QingHua Wang / Gold Knight, Coupe Automation) do not publish matching public driver source under those names.

13. **Legal / SDK.** Official driver SDK is application-only. Public repos include at least one RTI-copyright sample (SDK Climate) and an uploaded PDF/exe in matter-bridge. Do not copy those artifacts. Prefer rti-http-client, Pulse-Eight, Rachio, and Homeworks as clean public templates.

---

## Suggested takeaway for a Sentinel-oriented XP driver

A custom `.rtidriver` can cover a large part of Jamie's list **if the project is programmed to talk to it**:

- Testing: commands + events + sysvars + HTTP POST of each result.
- Commissioning: connection health, optional on-processor HTTP page (confirm HTTPServer/Curl on target firmware), Virtual Panel.
- Diagnostics: `System.Print` / `System.LogInfo`, firmware/runtime strings, TCP/HTTP/WS health, and (if Diagnostics is installed) the sysvar WebSocket.
- Analytics: explicit "log this button" commands plus optional sysvar subscribe; rollups on a server.
- Data export: HTTP/HTTPS/TCP/WebSocket client. Not a file on the XP.

It cannot, from public evidence alone, silently heat-map every existing button or read System Manager internals. The high-leverage unknown to settle with the official SDK (not from GitHub) is: inbound HTTPServer, Curl, MQTT, and whether sysvars can be listed/subscribed **inside** JS without bouncing through `/diagnosticswss`.
