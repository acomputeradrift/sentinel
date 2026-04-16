# RTI scope — concise rules (non-code)

How **scope** works in RTI Integration Designer, for later codification. **Nothing here is asserted beyond these statements.**

---

## Definitions

| Term | Meaning |
| ---- | ------- |
| **Tag** | A single named concept that can define **macros** and **variables** at several **scope levels** at once. The tag stores **all** of those definitions; **which** macro or variable runs is chosen by **scope resolution** (effective scope for the control in context). |
| **Scope levels** (macros / variables) | **Global**, **Source**, **Room**, **Controller**. In ID 11, **Macro** and **Variable** in the Tag Editor expose this ladder; **Page Link** is a separate branch (see rules). |
| **Global scope** (macro / variable) | Macro/variable definitions under **Global** in Macro/Variable. **Not** the same as the **Global** workspace *area* (see below). |
| **Effective scope** | The **room** and **source** (and, where relevant, controller) context used to pick **Source**, **Room**, and **Controller** macros/variables. **Global** macro/variable definitions **ignore** effective scope (see rules). |
| **Workspace scope** | Scope implied by **where** the page/control lives in the workspace tree (placement in the file). |
| **Workspace areas** | **Rooms** and **Global**. Under **Rooms**, structure is **room → source → pages**. Under **Global**, **shared sources** exist and may be used by **any/all rooms**. |

---

## Rules

1. **Global macros and variables** apply in **every room and every source**, **regardless** of effective scope.

2. **Source**, **Room**, and **Controller** macros and variables are selected using **effective scope**, which comes from **workspace placement**, **page layer** settings, and **viewport layer** settings (see 3–6).

3. **Precedence:** **viewport layer** overrides **page layer** overrides **workspace scope**. Viewport and page layers use the **same setting model** (viewport layer is not a different feature set).

4. **Default Room** and **Default Source** on layers **pass effective scope down** along: **viewport → page → workspace** (each step can supply or defer).

5. **Rooms area — workspace:** In a room you add **sources**; **all pages** sit **under a source**. Workspace scope for a page is **room → source** from **where that page lives** in the tree. Tags on that page **start** from that workspace scope before layer overrides.

6. **Rooms area — layers:** Effective scope is reasoned **from the viewport downward** (then page, then workspace; see rule 3). A **page layer** may contain **some or all** buttons; its **room** and **source** settings can **override workspace scope** for those buttons. **Viewport** content must sit on a **viewport layer**; changing that layer overrides **both** page layer **and** workspace for scope.

7. **Rooms area — viewport defaults:** With **Default Room** and **Default Source** on the **viewport layer**, **effective room** and **effective source** for that viewport are taken from the **page layer** below. If defaults **fall through** instead, **workspace scope** applies.

8. **Global workspace area — source:** For a **page in the Global area**, **source** effective scope is resolved **like Rooms**: **workspace**, then **page layer**, then **viewport layer** (same precedence and default flow as above).

9. **Global workspace area — room (exception):** For **room** on Global pages, **workspace** room is **not** taken from tree placement like Rooms; it comes from the runtime variable **`Selected Room`** (**exact** product name). If a **page layer** uses **default room**, it uses **`Selected Room`**. If **both** viewport and page layers are **default room**, **`Selected Room`** still applies the same way.

10. **Controller macros and variables** use effective scope like **Source** and **Room**, but **tags** are generally usable **across multiple devices**; **Controller** macros and variables are **locked to a single device**.

11. **Page links — dedicated row:** The Tag Editor **Page Link** branch (not under **Macro**) is **global automatically** (not scoped by Source/Room/Controller unless handled elsewhere).

12. **Page links — as a macro command:** **Page Link** is available as a **macro command** inside the **Macro** tree under **Global / Source / Room / Controller**. There it follows the **same rules as any other scoped macro** at that level (effective scope and layer precedence apply).

13. **Level priority (same tag):** If a tag has macro or variable definitions at more than one of **Global / Source / Room / Controller**, precedence is **Controller → Room → Source → Global** (highest wins).

14. **Controller level:** Bound to **one** controller. **Standalone** (controller-originated command path vs processor) is only available at **Controller** level, and only where the product supports it.

---

## Revision history

| Date | Notes |
| ---- | ----- |
| (initial) | Draft from author notes. |
| (revision) | Viewport defaults, layer parity, Selected Room, scoped Page Link command, Controller device lock. |
| (revision) | Consolidated: single definitions table + numbered rules; meaning preserved, duplication removed. |
| (revision) | Removed examples section; rule 5 generalized (no room/source sample names). |
| (revision) | Rules 13–14: level priority (same tag); controller binding and standalone. |
