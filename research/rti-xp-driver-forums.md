# RTI XP-series driver research (public forums and pages)

Research date: 25 October 2026  
Scope: public web only. No RTI or AVPro login. No paid or NDA material.  
Question: what could an RTI XP-series processor driver (Integration Designer, JavaScript plus XML manifest) do for testing, commissioning, diagnostics, and usage analytics?

This note is for Jamie Feeny's scoping of button-press heat maps, most-used buttons, feature and source usage, device online/offline health, feedback checks, logging events to an outside server, and what processor and System Manager data a driver can reach.

## How to read this

Each finding records URL, date, speaker, a short quote, and what it proves. **Confirmed** means a vendor page, public driver-store listing, firmware changelog, or a first-hand description that matches those. **Forum speculation** is labelled as such. **Not found** is a negative result, not a quote.

Driver Store pages often 302 on a direct fetch. Quotes for those listings come from the public search extract of the same URL. The RTI dealer forum at `forums.rticorp.com` is login-walled and was not opened.

There is no public RTI product named "RTI Connect" for XP processors. The live names are **RTiQ** (cloud monitoring), firmware **"cloud remote access"**, and **AVPro Connect** (dealer account used to download Integration Designer). ZincFive's "RTi Connect" is unrelated UPS software.

---

## Strongest findings

### 1. XP Diagnostics already exposes processor vitals, driver load, sysvars, flags, and logs in a browser

- **URL:** https://driverstore.rticontrol.com/driver/xp-diagnostics
- **Date:** Updated 15 December 2023 (v1.2)
- **Who:** RTI, Driver Store
- **Quote:** "This driver is used to assist dealers in accessing more detailed information about their system. To access the information provided by the driver type in the IP address of your processor into any web browser." Status includes name, IP, MAC, uptime, firmware, memory used, and SystemVar load. "A memory usage greater than 80% indicates that a slave processor may be needed to off load the master. An increase of this number over time indicates a memory leak. When the system approaches 100% memory used, the behaviour is unpredictable and will likely result in a 'frozen' XP processor." "SystemVar Load - The percentage of system variables in use. Each driver added to the system subtracts from a fixed number of system variables. When this value reaches 80% or greater, you may want to reduce the installed drivers or split the system." A driver "using more than 50% of the CPU may indicate a setup problem." Sysvars: "Choose the desired driver and variable to monitor then click 'Add'." User logging: "The driver functions 'Log User Message' and 'Log User Error' will place custom log message into the system logger window."
- **Proves:** A dealer (or any LAN browser) can read processor health, per-driver CPU and memory, RTiPanel connections, Zigbee, UPnP, any selected driver variable, system flags, and a log. Macros can write custom lines via Log User Message / Log User Error. Get Report exports a file for RTI support. This is the official on-processor diagnostic surface.
- **Confidence:** Confirmed (vendor driver docs).
- **Tabs named in that listing:** Status, Drivers, RTiPanel, Zigbee, UPnP, Sysvars, Flags, Log, Get Report.

Residential Systems, 24 May 2013 (updated 15 April 2019), Pete Baker (RTI VP Sales & Marketing): "Integration Designer 9.0 includes a new diagnostic driver that can be loaded onto an XP series processor running the latest firmware. Using any web browser, integrators can connect to the IP address of the processor to access its diagnostics Web interface to view processor vitals, controller connection status, driver usage, detailed logging information, and more." https://www.residentialsystems.com/technology/rti-releases-integration-designer-90-programming-software  
That dates the web diagnostics path to 2013.

### 2. Current onboard diagnostics miss startup; Chowmain tells dealers to disable it and use the older XP Diagnostics or TraceViewer

- **URL:** https://help.chowmain.software/portal/en/kb/articles/guide-troubleshooting-and-diagnostics-with-chowmain-rti-drivers
- **Date:** Current Chowmain KB (log sample uses epoch `1758266611000`, about September 2025)
- **Who:** Chowmain Software
- **Quote:** "The current onboard diagnostics is not suitable for this logging because it can't capture anything at startup, so instead we need to use the older version of XP Diagnostics." "To use it, you must first disable the Onboard Diagnostics, by making sure the Enable Onboard Processor Diagnostics System is unchecked." "Connecting after the project has loaded means we miss all the licencing, version and start up info which is critical." "the drivers can take up to 10 mintues to send licence information." Drivers have "Enable Trace" and Debug level; "Cloud logging is option, but if there is a chance that there may be internet issues that can be enabled as well."
- **Proves:** There are now two diagnostic paths: built-in onboard diagnostics, and the add-on XP Diagnostics driver. They conflict. Onboard cannot capture boot. TraceViewer is a PC tool that attaches to the processor IP. Chowmain drivers can also send logs to Chowmain's cloud. A driver that needs startup traces cannot rely on onboard diagnostics alone.
- **Confidence:** Confirmed for Chowmain's stack. Matches Joe Liggero's Home Assistant Bridge note that "XP Diagnostics starts a little after the drivers do."

### 3. Drivers are JavaScript on a single script thread; firmware documents HTTP, MQTT, SSH, Ping, Curl, OAuth, and memory leaks

- **URL:** https://firmware.avproglobal.com/downloads/rti/
- **Date:** Changelog through VXP-82 / XP-3 version 26.8.10 (24 August 2026)
- **Who:** RTI / AVPro firmware portal
- **Quote (selected):** 23.3.28 / 23.5.11: "Added JavaScript warning to HTTP.Open() if object is already open." "Fixed a memory ownership problem affecting garbage collection in callback functions for HTTPServer, TCPServer, Serial, SSH, MulticastUDP and MQTT objects." "Added OAuth driver support." "multiple drivers need to share port 80. To support this, a new version of the XP Diagnostic driver is required." 23.11.16 (12 January 2024): "Add support for cloud remote access." 24.3.29: "Fixed crash caused by Ping object." "Fixed HTTPServer object that could truncate data from slow clients." 24.12.10: "Add Curl object to driver API" and "Fixed multiple memory leaks." 26.8.10: freezes from "Drivers querying devices that were slow to respond," "Drivers using specific network features (curl, mDNS, ping)," and "Incoming RTiPanel app connections." 22.3.31: "Fixed bug that could cause HTTP communications from the processor to fail." 20.11.20: "Fixed a bug that prevented reboots during network firmware upgrades or from RTiQ."
- **Proves:** A custom driver can open HTTP/HTTPS, serve HTTP, talk MQTT, SSH, UDP, WebSocket, Ping, and later Curl. Outbound HTTP is first-class but historically buggy. Port 80 is shared (OAuth dashboard plus XP Diagnostics). RTiQ can reboot a processor. Slow device queries and Ping have crashed or frozen processors as recently as August 2026.
- **Confidence:** Confirmed.

David Bowdler's Apple TV driver (Driver Store, public listing) states the processor has a **single script thread**, and that local crypto on an XP-8v took "around 12 seconds" for a Curve25519 keypair and "20 to 40 seconds" for Ed25519 pairing, holding up every other driver. https://driverstore.rticontrol.com/driver/david-bowdler-apple-tv-control  
That is a confirmed practitioner measurement published on the Driver Store.

### 4. RTiQ is the cloud health product: ping, IP check, sysvar watch, email/text, remote macros. It is not a usage-analytics product.

- **URLs:**
  - https://www.avproglobal.com/pages/rti-rtiq-information
  - https://cediaexpo.com/exhibitor-press-release/rti-1-2/ (22 August 2018)
  - https://www.residentialsystems.com/resources/integration-guides/integration-guide-to-remote-monitoring-help-from-afar (8 October 2020)
- **Who:** AVPro / RTI marketing; Mike Everett, VP Global Sales, RTI; dealers Wayne Flittner (Thousand Oaks Home Theater) and Joe Mattera (Mattera Design); Karen Mitchell (Residential Systems)
- **Quotes:** AVPro: "RTiQ monitors all Ethernet-connected RTI devices (touchpanels, processors, etc.) and triggers custom actions remotely. RTiQ monitors third-party external devices as well—by pinging them, checking connection to a specific IP address, or by monitoring a system variable for information such as rack temperature and lamp hours." "Get notified about system issues by text message or email." "RTiQ keeps a detailed history on the connected devices in each system to measure system performance and health." Everett (CEDIA, 21 August 2018): "After being live for only a few weeks, we have more than 1,500 systems currently reporting into RTiQ." Flittner: "I use RTI’s RTiQ … to monitor devices on the network that need to communicate with the control processor. Sometimes, when there is a power outage, devices come back online in random order." Mattera: "We make sure every RTI processor is on RTiQ. And we set up certain macros to reboot specific equipment in case of equipment lockups and power outages."
- **Proves:** Device online/offline health via ping, IP, or a chosen system variable is a supported dealer product. Email and SMS alerts are supported. Remote reboot and any control-system action are supported. History is device-health history, not button-press heat maps. Setup is inside Integration Designer 11 / APEX. Public pages do not expose an API or webhook export from RTiQ itself.
- **Confidence:** Product behavior confirmed. Dealer workflow first-hand. "1,500 systems" is vendor PR.

### 5. System Manager tracks room/source/device state for programming. It is not a diagnostic or analytics console.

- **URLs:**
  - https://www.avproglobal.com/pages/rti-integration-designer
  - https://www.cepro.com/news/rti-integration-designer-11-software-update/98414/ (13 April 2022)
  - https://rticorp.com/integration-designer (search extract; live fetch returned HTTP 500)
- **Who:** AVPro product page; Arlen Schweiger (CE Pro); Kevin Marty (RTI CTO); Joe Roberts (then RTI CEO)
- **Quotes:** AVPro: "The System Manager tracks the status of every device in the system, simplifying your programming, improving system performance, and saving valuable time." Marty: "It’s kind of the back-end component of Integration Designer 11 that allows our control processors to keep track of the state of the entire system. So it knows which rooms are on, which rooms are off, what sources they’re using in each of them." Roberts: "Prior to system manager, these would all have to be macros written in there to track states – what is on, if this is on do this, etc. System manager does all that for you."
- **Proves:** System Manager is a runtime state engine plus an ID11 auto-programming helper. It knows room on/off and current source. Public pages do not say a driver or outside tool can dump that state as an API. They also do not mention heat maps, press counts, or usage reports. Clock-driver listing says the official clock was folded into System Manager in ID11 (https://driverstore.rticontrol.com/driver/clock-driver).
- **Confidence:** Confirmed as a programming/state feature. Absence of analytics is a negative finding, not a quote.

AVPro training lists "Programming with System Manager" (35:55) and "Mastering System Manager" (1:24:18) plus "XP Diagnostics & RTIQ Intelligent Monitoring" (1:00:13, Vincent Bova). Course pages are public; the videos themselves were not watched (account/player). https://training.avproglobal.com/rti/xp-diagnostics-rtiq-intelligent-monitoring

### 6. Drivers can read other drivers' variables if a helper driver is bound in Integration Designer

Confirmed public drivers that bind to another driver's variables:

| Driver | Author | What it does | Cap |
| --- | --- | --- | --- |
| Integer Helper | RTI, updated 7 Aug 2020, v1.3 | "The Integer Variable pulldown menu will allow you to choose any of the integer based variables in the drivers currently in your system file." Scale/translate ranges (volume, "US to metric conversion of temperature or distance"), range alerts, boolean-per-value. | One watched integer per instance |
| Lambda | Ryan Melena, v2.4 | "assign input variables from other drivers (currently up to 20) and then define a logical expression based on those variables using the full power of javascript." | 20 inputs; stackable instances |
| Logic Helper | RTI | "The inputs can come from any driver in the file." Up to 16 boolean groups, AND/OR/NAND/NOR. | 16 groups |
| Button SysVar Events | John Frost / Hilium | "events based on button press actions and changes to external (other drivers’) system variables. Up to 50 external variables can be monitored." | 50 vars |
| Processor to Processor | Coupe Automation, v2.00 | Copies String/Integer/Flag between two XP processors. "Current limitations in ID do not allow you to change driver variable names at design time." | Numbered Integer 1, String 1, Flag 1… |

- **URLs:** https://driverstore.rticontrol.com/driver/integer-helper ; https://driverstore.rticontrol.com/driver/ryan-melena-lambda ; https://driverstore.rticontrol.com/driver/logic-helper ; https://driverstore.rticontrol.com/driver/john-frost-button-sysvar-events ; https://driverstore.rticontrol.com/driver/coupe-automation-proc-to-proc-communication
- **Proves:** Cross-driver reads are a first-class, dealer-configured pattern. The dealer picks the source variable from a dropdown. A custom analytics driver could watch the same way. There is no silent scrape of every variable without bindings. Shared SystemVar space is finite (see limits).
- **Confidence:** Confirmed.

### 7. Outbound email, push, HTTP/HTTPS, and inbound HTTP webhooks already exist as drivers

| Path | Driver | What it proves |
| --- | --- | --- |
| Email out | RTI Email / SMTP Client, updated 27 Mar 2017, v2.52 | "email notifications can be sent from any macro running on the XPx." AUTH LOGIN PLAIN only. No NTLM/Exchange. Also can mail WAN IP changes so RTiPanel remote access can be updated. https://driverstore.rticontrol.com/driver/email-smtp-client |
| Push out / in | Chowmain Pushover (v3.3, $90, updated 23 Oct 2025) and David Bowdler Pushover Notifications | Send from any macro. Receive can fire RTI events. Chowmain: "The real power comes when using a system like If This Then That (IFTTT) or Zapier." Bowdler: "An RTI processor with internet access (Pushover is a cloud service)." Telnet debug console. https://chowmain.software/drivers/rti-pushover ; https://driverstore.rticontrol.com/driver/david-bowdler-pushover-notifications |
| HTTP out | David Bowdler HTTP Toolkit, updated 14 June 2026, v1.14 | Up to 50 named GET/POST/PUT/PATCH/DELETE requests from macros; 80 feedbacks from response bodies; HTTPS/TLS; browser test page on port 9033. Needs runtime 24+ and ID 11.4+. "One request at a time." 15-second timeout. https://driverstore.rticontrol.com/driver/david-bowdler-http-toolkit |
| HTTP in (macros) | RTI HTTP Server Driver, updated 29 May 2020, v1.4 | Listen on a port **greater than 1024** (ports under 1025 reserved). Example: `http://192.168.0.100:8080/opendoor` fires event 1. Used in Siri and 2N tech bulletins. https://driverstore.rticontrol.com/driver/rti-http-server-driver |
| HTTP in + JSON vars out | Coupe Automation HTTP Commander | GET/POST run macros; serve up to 50 flags/ints/strings as JSON (`/?vars`). Optional basic auth. Also can Send GET / Send POST outbound. https://driverstore.rticontrol.com/driver/coupe-automation-http-commander |
| Device health | Buttonwood Advanced Network and Service Health Monitor, updated 7 Oct 2026, v2.0 | Up to 32 ICMP/TCP/HTTP/HTTPS/DNS/SNMPv1/v2c monitors, composites, maintenance silence, TraceViewer diagnostics. No SNMPv3, no SET. https://driverstore.rticontrol.com/driver/buttonwood-technologies-llc-advanced-network-and-service-health-monitor |
| HA event out | Joe Liggero Home Assistant Bridge, updated 12 Oct 2026, v3.6 | "Fire HA Event - fires any HA event_type with optional JSON payload." Also Call HA Service. Writes to processor System Log. https://driverstore.rticontrol.com/driver/joe-liggero-home-assistant-bridge |

- **Proves:** Logging a tagged event to an outside server is possible today: put a driver function (Send Mail, Notify, SendSlotN, Fire HA Event) on the same macro as the button, or on a helper event. There is no official "syslog to SIEM" product. Ports below 1025 are reserved for system use on the official HTTP Server driver. HTTP Toolkit needs firmware 24+.
- **Confidence:** Confirmed.

### 8. Button-press capture is possible by programming, not by a built-in heat map

No public RTI, Driver Store, Remote Central, Home Assistant, CEDIA, or Residential Systems page describes a native button-usage dashboard or heat map.

What does exist:

- **XP Diagnostics Log User Message / Log User Error:** dealer adds those functions to macros. Confirmed on the XP Diagnostics listing.
- **Button SysVar Events (Frost):** press, double press, long press, release, ramp events; watches another driver's integer. Confirmed.
- **Flic Hub Trigger (Bowdler):** "Feedback variables: Last Button, Last Action and per-button press counts." "Print Button Reference - logs each button's URL to TraceView." Search extract of https://driverstore.rticontrol.com/driver/david-bowdler-flic-hub-trigger
- **One Touch Button (My Device, 2013):** "track (without using flags) up to 50 individual buttons" short/long press. Search extract of https://driverstore.rticontrol.com/driver/mydevice-one-touch-button
- **Tag-based programming:** AVPro ID page: "Start from a built-in template, add the equipment, and let tag-based programming wire the buttons." Tags are how ID11 shares macros across pages. They are not an automatic analytics tap.

- **Proves:** A heat map is a build, not a product. The practical path is: every interesting button's macro also calls a logger (HTTP Toolkit, Email, Pushover, HA Fire Event, or Log User Message). Untagged or template-only buttons will be invisible unless the dealer adds that step. Native "most-used buttons" reporting was not found.
- **Confidence:** Events and counts confirmed. Native heat maps: not found.

### 9. There is no generic inbound API. Dealer SDK is gated. XP web server is for debug, not a public REST API.

- **URL:** https://community.home-assistant.io/t/remote-technologies-rti-xp3-with-several-pcm-4/179741
- **Date:** 19 March 2020 onward
- **Who:** simplextech (self-identified dealer); Holdestmade; 80mileseast; mefranklin6; dskudrin
- **Quotes:** simplextech: "there is no API for these types of systems. There’s no ports that are sitting just listening for random queries or for accepting random input." "RTI isn’t going to open things up." Holdestmade: MQTT add-on is "in the RTI forum, only accessable to dealers" (https://forums.rticorp.com/index.php?topic=25609.0). mefranklin6 (16 March 2025, HA thread 742330): "there’s no way to make the two systems automatically talk to eachother out of the box, at least without access to the RTI SDK, which is only avaialbe to approaved developers." Also: "The RTI processors’ webserver is pretty helpful for debugging as it will show you the raw data that the driver last received."

AVPro Independent Driver Developers page: SDK is for "dealers with the technical aptitude to create drivers using script" (JavaScript, C++, etc.), after training and a formal agreement. Community Drivers (ID11.13+) default to 10 uploads. https://www.avproglobal.com/pages/rti-driver-developers

- **Proves:** An outside tool cannot walk up to an XP and list all variables or button presses unless a driver was programmed to expose them (HTTP Commander `/?vars`, HTTP Server paths, Two-Way Strings TCP, HA Bridge). The processor web UI is a diagnostics/debug page, not an open API. Writing a first-party-quality driver needs the dealer SDK.
- **Confidence:** Confirmed by dealer + vendor SDK page. XP-3 "cannot take drivers" (Holdestmade, "IIRC") is **forum speculation**; HA Bridge later lists XP-3 as supported.

### 10. Processor limits are real: memory, SystemVar pool, driver count, one script thread, 10/100 Ethernet

Confirmed hardware (Comm-Tec / RTI product catalog, March 2025, https://www.comm-tec.de/content/files/avgy_content/images/brand%20pages/rti/rti_product_catalog_03-2025.pdf):

- **XP-8v:** 32-bit 1 GHz CPU, 512 MB non-volatile flash, HDMI OSD, 8 IR/I-O, 8 RS-232, 8 relays, 8 sense, one 10/100 Ethernet, SD/MM slot.
- **XP-6s:** 32-bit 1 GHz CPU, 512 MB flash, 6 IR, 3 RS-232, 3 relays, 3 sense, 10/100 Ethernet.
- AVPro KB extract for XP-8v also states **1 GB RAM** (https://support.avproglobal.com/portal/en/kb/articles/xp-8v-operation-guide). Catalog text does not list RAM on those two pages.

ICP replacements (ID12, not XP): "quad-core, 3GB RAM, 16GB flash, 1.8GHz." https://www.avproglobal.com/pages/rti-integration-designer

Confirmed software ceilings:

- Shared SystemVar pool; XP Diagnostics warns at 80%. Vantage InFusion driver notes that an earlier mapping "swallowed up almost 8% of the shared driver variable space" and "in larger systems this can cause a system to literally run out of space to store variables." https://driverstore.rticontrol.com/driver/vantage-infusion
- Typical driver memory "10-50k" (XP Diagnostics). Driver over 50% CPU is a problem.
- HA Bridge: 100 entities max; "40-60 configured entities is the recommended target." Validated "on a real XP-8 running ~15 drivers and 100+ HA entities." Overload symptoms: "slow state-change propagation, memory pressure … dropped WebSocket frames."
- Two-Way Strings: 100 strings per instance (FrontierFred, 12 Feb 2026, HA 742330). Multiple instances need different ports.
- HTTP Toolkit: 50 commands, one request at a time.
- HTTP Commander: 50 macros, 50 events, 50 of each variable type.
- Official HTTP Server: listen port must be > 1024.
- Chowmain: internet required to register a license; Project Agent must stay installed. https://help.chowmain.software/portal/en/kb/articles/how-to-licence-chowmain-rti-drivers

---

## Capability by capability

### Testing

**Possible (confirmed):**

- Load XP Diagnostics (or keep onboard diagnostics), open `http://<processor-ip>/`, watch Sysvars and Flags while pressing buttons.
- Raise a driver's log category to High, Save Levels, keep the browser open across reload if startup matters (Chowmain).
- Use TraceViewer from a PC (Chowmain KB; HA Bridge also mentions Integration Designer System Log).
- HTTP Toolkit browser page on port 9033: fire a request and capture response patterns.
- Bowdler Pushover: telnet debug console; "Send Test Notification."
- HA Bridge: LastError, LicenseStatusText, System Log every 5 minutes; Force Reconnect.
- Buttonwood health monitor: TraceViewer diagnostics, per-monitor last-result fields.
- Virtual Panel / RTiPanel Desktop (ID12 language; ID11 still has Virtual Panel). Connected Media, 11 Oct 2022: "Virtual Panel will more quickly detect and connect to the system controller." https://connectedmedia.co.nz/News/x_post/Rti-id11-update-00003.html

**Hard (confirmed):**

- Onboard diagnostics miss boot (Chowmain, Liggero).
- ID System Log "does not remember" the per-driver message filter after a project send (HA Bridge).
- Slow or chatty drivers freeze processors (firmware 26.8.10).

**Not found:** a built-in test runner, pass/fail checklist, or scripted button exerciser on the XP.

### Commissioning

**Possible (confirmed):**

- System Manager auto-programs room/source activities and tracks which room is on which source (Marty / Roberts, CE Pro 13 Apr 2022).
- Tag-based templates and Button Clusters (AVPro ID page).
- Master/slave processors since ID 9.0 (Residential Systems, 24 May 2013): two-way drivers can run on a slave.
- RTiQ plus reboot macros after power-fail (Mattera, Flittner, 2020).
- Import/export driver configuration since ID 9.0.
- ID11.2.0: unexpected shutdown recovery, faster large RTiPanel downloads, up to 20% smaller panel images (Connected Media, 11 Oct 2022).

**Pain (confirmed and first-hand):**

- Programming file cannot be pulled back off a processor. Reddit dealer Deep-Ad-5983, 29 Dec 2023: "One cannot download the programming from a file that is loaded onto a processor." https://www.reddit.com/r/homeautomation/comments/18tbemz/rti_dealer_quoted_me_10k_to_fix_our_system/
- Integration Designer and the dealer forum need an AVPro Connect / dealer account (AVPro ID download page; Holdestmade; flippedcracker lost forum access after leaving a dealership).
- Firmware upgrades still brick or orphan processors. Remote Central, RTI Installer, 12 Oct 2026: "Tried to upgrade to 28.6.10 and it failed. Are there any new tricks to get this processor to be recognized via USB or ethernet, or is it trash?" https://www.remotecentral.com/cgi-bin/mboard/rc-touch/thread.cgi?5627,1
- Ethernet commissioning on older XP-8 can fail because of VM NAT vs bridged networking (AVS, thebland / Itai, Aug 2010). https://www.avsforum.com/threads/rti-xp8-issues-connecting-to-home-network-via-ethernet.1269640/
- ID9 dual-master jobs do not convert cleanly to ID11 (AVS snippets for "RTI legacy system want to upgrade"; not fully fetched).

### Diagnostics

**What the XP web / System Log / XP Diagnostics surface shows (confirmed):**

- Processor: name, IP, MAC, uptime, firmware, memory %, SystemVar %.
- Per driver: name, CPU, CPU average, memory used, memory peak, ports.
- RTiPanel: device class, WAN/LAN, state, timeout.
- Zigbee and UPnP/ESC-2 device lists.
- Any selected driver variable and any system flag (watch list, not a full dump unless added).
- Logs by category at None/Low/Medium/High. Defaults to errors. Levels reset on reboot unless Save Levels.
- Get Report file for support.
- User-written log lines from macros.
- Two-Way Strings last-RX raw data (mefranklin6).
- HA Bridge last error and 5-minute health summary.

**What an outside tool can read without extra programming:**

- The diagnostics HTML if it can reach port 80 on the LAN. That is a browser UI, not a documented JSON API. Whether a scraper could parse it was not proven in public sources.
- Nothing from RTiQ without a dealer RTiQ login (not opened here).

**What a driver can read:**

- Variables the dealer binds into that driver (Integer Helper / Lambda / Frost pattern).
- Its own HTTP/TCP/MQTT/Ping results.
- Not the full System Manager token set unless those tokens are exposed as ordinary system variables and bound. Public pages never say "enumerate System Manager variables from script."

### Analytics and heat maps

**Not found** as a native RTI or RTiQ feature.

**Possible build (confirmed pieces):**

1. Add a Log User Message or HTTP Toolkit SendSlot / Pushover / Email / Fire HA Event step to each tagged macro.
2. Optionally increment integers with a helper and expose them via HTTP Commander `/?vars`.
3. Flic / One-Touch style press counts for a bounded set of buttons (50).
4. Ship the stream to HA, Zapier, or a custom HTTPS endpoint.

**Impossible from public evidence:**

- Automatic capture of every page tap without dealer programming.
- A factory heat-map UI on XP or RTiQ.

The closest non-RTI hit in search was Bitfocus Companion issue #4132 (unrelated product). That is not RTI.

### Data export

**Outbound (confirmed):** Email SMTP, Pushover, HTTP Toolkit (HTTPS REST), HTTP Commander Send GET/POST, HA Fire Event / Call HA Service, Chowmain cloud logging, RTiQ email/SMS (health only).

**Inbound (confirmed):** HTTP Server driver (path to event), HTTP Commander GET/POST to macros, Two-Way Strings TCP, HA Bridge WebSocket to HA.

**Reserved:** official HTTP Server cannot bind ports 1-1024. Firmware 23.3.28+ shares port 80 among OAuth dashboard and XP Diagnostics.

**Not found:** official syslog, MQTT (except a $70 dealer-forum add-on), Splunk/webhook product, or RTiQ data-export API.

### System Manager and processor info

| Data | Where it lives | Reachable by a driver / tool? |
| --- | --- | --- |
| Room on/off, current source | System Manager runtime (Marty) | Indirectly, if those states appear as system variables a helper can bind. Not documented as an API. |
| Device "status" in ID | Programming intelligence, not a health ping | Do not confuse with RTiQ or Buttonwood ping |
| Clock / date | Folded into System Manager in ID11 | Variables exist for UI; clock driver listing |
| Processor IP, MAC, uptime, firmware, memory, SystemVar load | XP Diagnostics Status tab | Browser on LAN. Driver-side access not documented beyond writing your own log lines. |
| Per-driver CPU / RAM | XP Diagnostics Drivers tab | Browser |
| RTiPanel sessions | XP Diagnostics RTiPanel tab | Browser |
| Selected driver variables | Sysvars tab, or HTTP Commander if configured | Browser or HTTP GET |
| RTiQ history | Cloud dashboard | Dealer RTiQ login only |

### Internal and other drivers' variables

Dealer setup (confirmed by Integer Helper, Lambda, Logic Helper, Frost):

1. Add the helper driver to the processor in Integration Designer.
2. In driver properties, pick the source variable from a dropdown of integers/booleans/strings already in the project.
3. Enable only the tasks you need (Integer Helper: each extra task costs CPU on every change).
4. Use the helper's output variables on pages, or its events to fire macros.
5. Stack instances (Lambda into Lambda, Logic Helper into itself) if you need more inputs.

Cross-processor: pair of Coupe XP2XP drivers; map Integer 1 on A to Integer 1 on B; name them in String/Integer/Flag Names because ID cannot rename driver variables at design time.

### Button press capture

Practical dealer methods, strongest first:

1. **Macro tagging:** every activity or button macro starts with "Log User Message" or "HTTP Toolkit SendSlotN" or "Pushover Notify" with a stable name (room, page, tag). Confirmed functions exist.
2. **Button SysVar Events:** bind 1-50 buttons to another driver's integers; get press/hold/double/ramp events.
3. **HTTP Server / HTTP Commander:** an outside test harness presses a virtual button by URL; that is reverse of analytics (inject, not observe).
4. **Two-Way Strings / HA:** mefranklin6 pattern sends a string per remote action into HA. That captures only the strings the dealer defined (100 per driver).
5. **Flic / One-Touch counts:** only for those devices/buttons.

No public dealer comment was found that said "we already have a heat map." Comments that exist are about feedback failures, not usage ranking.

### Limits (summary)

- **Memory:** watch XP Diagnostics Memory Used; 80% means add a slave; 100% freezes the box. Firmware has repeated leak and GC fixes.
- **SystemVar pool:** finite, shared, 80% warning. Fat drivers (Vantage example) can starve a large job.
- **CPU / thread:** one JavaScript thread; a heavy driver stalls others (Apple TV crypto).
- **Driver count:** HA Bridge validated ~15 drivers on an XP-8. Older firmware notes (quoted by dskudrin on HA, not re-fetched as a separate official line in the current changelog page) mentioned instability above 50 drivers and Diagnostics Driver max raised from 40 to 80. Treat the "50 drivers" figure as **reported via community reprint**, not as a line we independently copied from the current firmware page.
- **Network:** one 10/100 port on XP-6s/XP-8v. Outbound HTTP has a history of bugs. Ping/curl/mDNS have crashed firmware. TLS via mbedTLS; HTTP Toolkit uses `StartSSLHandshake()`; self-signed often needs TLS off.
- **Storage:** 512 MB flash. SD/MM slot on XP-8v. No public "write a CSV of presses to SD" driver was found.
- **Firmware:** current public latest on the portal viewed here is 26.8.10 (24 Aug 2026). A Remote Central poster named 28.6.10 (unverified).
- **SDK / ID:** JavaScript two-way drivers; SDK agreement required. ID11 for XP; ID12/ICP is the next platform, conversion one way.
- **Licensing:** Chowmain needs internet + Project Agent. Many community drivers are MAC-bound or site-licensed.

---

## Dealer pain points

These are the recurring public complaints that matter to Sentinel-style commissioning.

1. **Closed toolchain.** End users and many leftover-homeowners cannot get Integration Designer or the dealer forum. Simplextech, Holdestmade, Dornquast (HA 2020); Reddit Deep-Ad-5983 (2023); AVPro "AVPro Connect account required."
2. **No project extract from the processor.** If the `.apex` is lost, the job is a rewrite (Deep-Ad-5983).
3. **Two-way feedback is the hard part.** AVS HAI/OmniPro thread: first open after download shows correct thermostat and zone state; later updates die; driver "reboots every few minutes"; installer added a one-minute keep-alive. iRule still had better HAI feedback. eatenbacktolife: use diagnostics page, Sysvars, High logging; "your installer should be on the RTI forums"; "something like this can eat up hours and days and turn your install unprofitable rather quick." https://www.avsforum.com/threads/rti-with-hai-omnipro-ii.3179460/ (live AVS returned HTTP 402; quotes from public search/Wayback-visible text)
4. **Network and VLAN fragility.** Reddit bofadoze (Dec 2018): after router/VLAN work and an XP-8 slave death, RTiPanel and drivers (AD8, clock, Sonos) dropped. Reboot used to help, then did not. https://www.reddit.com/r/homeautomation/comments/a6v5o5/rtipanel_keypads_not_communicating_with_drivers/
5. **Power-fail boot order.** Flittner (2020): devices come back in random order and break IP links; RTiQ plus reboot macros are the workaround.
6. **Startup and license timing.** Chowmain: 10-15 minutes of logs needed; onboard diagnostics miss that window.
7. **Firmware and download hangs.** Changelog: hang while receiving program updates (25.1.27), shutdown hang (24.12.10), Ping crashes, slow-device freezes (26.8.10). Remote Central Oct 2026: failed upgrade, processor no longer seen on USB or Ethernet.
8. **Large panel downloads.** Official ID11.2.0 notes admit many/large RTiPanels were slow; image optimisation added.
9. **Third-party license and internet.** Chowmain Agent must stay installed; license invalid if removed. Apple TV crypto-offload needs outbound internet.
10. **Support split.** eatenbacktolife: RTI direct "won't be much help" on a third-party driver; dealer forum is the real channel, and it is login-walled.
11. **Platform transition.** XP stays on ID11. ICP + ID12 is the new line; "RTiQ monitoring runs on the processor" is an ICP/ID12 claim, not an XP built-in. Conversion is one way.

iRule-era note: the HAI AVS thread is the clearest public "we left iRule for RTI and lost feedback" story. No public iRule-to-RTI analytics tool was found.

Highfive / Dynamic Drivers: public search did not find RTI driver vendors under those names. High Five (highfiveonline.com) is an RTI dealer in Hopkins, MN. Dynamic Camera Feed is an official RTI camera-stream driver, not a vendor. Community HTTP/Pushover/health work is Chowmain, Coupe Automation, David Bowdler, Joe Liggero / Custom Control Drivers, Buttonwood, John Frost, Ryan Melena.

---

## Open questions

These cannot be answered from public pages without dealer-forum or SDK access.

1. **Can a JavaScript driver enumerate all system variables, or only ones bound in its XML/config?** Public helpers all use dealer-picked dropdowns. The SDK may allow more. Unknown.
2. **Are System Manager room/source tokens ordinary system variables a driver can subscribe to?** This repo already treats System Manager as a variable family inside `.apex` files. Public RTI pages never say a runtime driver can list them.
3. **Is the XP Diagnostics web UI scrapeable as structured data?** No public schema. Get Report is a file for humans/support.
4. **Onboard diagnostics vs XP Diagnostics driver: exact feature delta besides startup capture?** Chowmain says onboard cannot capture boot. Full tab list for onboard was not on a public page we could fetch.
5. **Does RTiQ expose a dealer API or only the dashboard?** Not documented publicly.
6. **What does firmware "cloud remote access" (23.11.16) actually expose?** Name only. Could be RTiPanel cloud, RTiQ, or something else.
7. **TraceViewer protocol.** Chowmain documents the UI. Wire protocol is not public.
8. **MQTT add-on** on `forums.rticorp.com/index.php?topic=25609.0`: $70, 60-minute trial, dealer-only. Capabilities unknown beyond the HA mention.
9. **XP-3 driver support** is contradicted in public sources (Holdestmade vs HA Bridge). Needs a current official compatibility matrix.
10. **Can Log User Message lines be pulled off-box without a person clicking Get Report?** Not documented. A custom driver posting to HTTPS is the only proven export.
11. **SD card on XP-8v:** can a driver write logs there? Not found.
12. **Heat-map prior art on the dealer forum.** Highest-value unread source is `forums.rticorp.com` (login). Remote Central index is public (thousands of threads) but individual recent threads are hard to address without guessing IDs; "RTI Software for non dealers?" is the largest old thread (84 replies, ~69k views since 2007) and was not fully read.
13. **ID12 / ICP RTiQ-on-processor:** if Jamie later moves off XP, on-box monitoring may get richer. That does not help current XP-6s / XP-8v / XP-3 jobs.

---

## Source quality map

**Strongest (vendor, reproducible):** XP Diagnostics listing; firmware changelog; Email/SMTP; HTTP Server; HTTP Toolkit; HTTP Commander; Integer Helper; Lambda; Logic Helper; Button SysVar Events; RTiQ product page; ID 9.0 announcement; ID11 CE Pro interview; Chowmain TraceViewer/onboard KB; HA Bridge scale notes; AVPro SDK page; March 2025 product catalog.

**Strong dealer or practitioner voice:** Mattera, Flittner, Everett (PR), eatenbacktolife, simplextech, mefranklin6, FrontierFred, dskudrin, RTI Installer (Remote Central).

**Forum speculation:** XP-3 cannot run drivers; heat maps "must exist" on the dealer forum; 28.6.10 as a real firmware train (only one post); Highfive/Dynamic Drivers as driver vendors.

**Login-walled or blocked (not used as evidence beyond the fact of the wall):**

- https://forums.rticorp.com/ (dealer forum, including MQTT topic 25609)
- https://training.avproglobal.com/ videos (catalog public)
- RTIXCEL (Connected Media: login required)
- Integration Designer User Manual download (AVPro Connect)
- Many AVS threads (live 402)
- Many Reddit threads (live 403; snippets used only where quoted in search extracts and labelled)
- driverstore.rticontrol.com direct fetch 302 (search extracts used)
- rticorp.com/integration-designer and rticorp.com/rtiq-information HTTP 500 at fetch time; AVPro mirrors used instead

---

## Implication for an XP analytics / commissioning driver

From public evidence only, a custom XP driver can:

- Watch dealer-selected variables from other drivers (including, if they are exposed, System Manager-style room/source integers).
- Post events to HTTPS, email, Pushover, or Home Assistant when a macro calls it.
- Offer its own small web page (HTTP Server / Toolkit pattern) for commissioning.
- Participate in XP Diagnostics logging (Log User Message, or write to System Log the way HA Bridge does).

It cannot, on public evidence:

- Turn on a factory heat map.
- Read RTiQ's cloud history.
- Scrape every button press without the dealer putting a hook on those macros.
- Assume unlimited memory, parallel HTTP, or a stable Ping object.
- Ship as an official Driver Store package without a signed developer account.

The highest-leverage public design is: a thin logger driver plus HTTP Toolkit or a built-in HTTPS post, bound through tags so every activity and a sample of hard keys call one function, with XP Diagnostics used for health and RTiQ used for online/offline. Heat maps then live on the outside server, not on the XP.
