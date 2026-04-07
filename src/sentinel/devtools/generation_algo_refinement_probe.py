from __future__ import annotations

import argparse
import json
import statistics
import time
import uuid
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]


def _pct(values: list[float], p: float) -> float | None:
    if not values:
        return None
    xs = sorted(float(v) for v in values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * max(0.0, min(100.0, float(p))) / 100.0
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    frac = pos - lo
    return xs[lo] * (1.0 - frac) + xs[hi] * frac


def _slug(name: str) -> str:
    out = []
    prev_dash = False
    for ch in str(name or "").lower():
        if ("a" <= ch <= "z") or ("0" <= ch <= "9"):
            out.append(ch)
            prev_dash = False
            continue
        if not prev_dash:
            out.append("-")
            prev_dash = True
    s = "".join(out).strip("-")
    return s or "item"


def _discover_apex_files(assets_dir: Path, include: list[str], exclude: list[str]) -> list[Path]:
    all_files = sorted([p for p in assets_dir.glob("*.apex") if p.is_file()], key=lambda p: p.name.lower())
    if include:
        wanted = {_slug(x) for x in include}
        all_files = [p for p in all_files if _slug(p.stem) in wanted or p.name in include]
    if exclude:
        ex = [str(x).strip().lower() for x in exclude if str(x).strip()]
        all_files = [p for p in all_files if not any(token in p.name.lower() for token in ex)]
    return all_files


def _new_name(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _wait_for_text(page: Any, selector: str, needle: str, timeout_ms: int) -> bool:
    deadline = time.perf_counter() + (float(timeout_ms) / 1000.0)
    need = str(needle or "")
    while time.perf_counter() < deadline:
        try:
            txt = str(page.locator(selector).inner_text() or "")
        except Exception:
            txt = ""
        if need in txt:
            return True
        time.sleep(0.05)
    return False


def _wait_for_usable_render(page: Any, timeout_ms: int) -> bool:
    deadline = time.perf_counter() + (float(timeout_ms) / 1000.0)
    while time.perf_counter() < deadline:
        ok = page.evaluate(
            """() => {
              const canvas = document.getElementById('rtiCanvas');
              if (!canvas) return false;
              const rows = document.querySelectorAll('.device-page.active .btn-wrap');
              if (!rows || !rows.length) return false;
              const r = canvas.getBoundingClientRect();
              if (!r || r.width <= 0 || r.height <= 0) return false;
              return true;
            }"""
        )
        if bool(ok):
            return True
        time.sleep(0.05)
    return False


def _measure_one_run(
    *,
    browser: Any,
    commissioning_url: str,
    apex_path: Path,
    run_index: int,
    timeout_ms: int,
    device_index: int,
) -> dict[str, Any]:
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    try:
        page.goto(commissioning_url, wait_until="domcontentloaded")
        if not _wait_for_text(page, "h1", "Sentinel Console", timeout_ms):
            raise RuntimeError("Commissioning UI did not load.")

        page.locator("#tab-manage").click()
        client_name = _new_name(f"probe-client-r{run_index}")
        project_name = _new_name(f"probe-project-{_slug(apex_path.stem)}-r{run_index}")

        page.fill("#newClientName", client_name)
        page.locator("#createClientBtn").click()
        if not _wait_for_text(page, "#clientSelect", client_name, timeout_ms):
            raise RuntimeError("Client was not created/selected.")

        page.fill("#newProjectName", project_name)
        page.locator("#createProjectBtn").click()
        if not _wait_for_text(page, "#projectSelect", project_name, timeout_ms):
            raise RuntimeError("Project was not created/selected.")

        api_responses: list[Any] = []

        def _capture_response(resp: Any) -> None:
            try:
                url = str(resp.url or "")
                method = str(resp.request.method or "").upper()
                if method != "POST":
                    return
                if "/upload-and-regenerate" not in url and not url.endswith("/regenerate"):
                    return
                api_responses.append(resp)
            except Exception:
                return

        page.on("response", _capture_response)
        page.set_input_files("#apexFile", str(apex_path.resolve()))
        page.locator("#uploadBtn").click()
        ready_ok = _wait_for_text(page, "#uploadStatus", "Uploaded:", timeout_ms)
        if not ready_ok:
            raise RuntimeError("Upload/regenerate did not reach Uploaded status in time.")

        preload_sec: float | None = None
        for resp in reversed(api_responses):
            if not bool(resp.ok):
                continue
            ct = str(resp.headers.get("content-type") or "")
            if "application/json" not in ct.lower():
                continue
            try:
                payload = resp.json()
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            generation = payload.get("generation")
            if not isinstance(generation, dict):
                continue
            timings = generation.get("timings")
            if not isinstance(timings, dict):
                continue
            g = timings.get("generateSec")
            if g is None:
                continue
            preload_sec = float(g)
            break
        if preload_sec is None:
            raise RuntimeError("Missing generation.timings.generateSec from upload/regenerate response.")

        project_id = str(page.locator("#projectSelect").input_value() or "").strip()
        if not project_id:
            raise RuntimeError("Missing selected project id before tech link creation.")
        tech_label = f"probe-tech-r{run_index}"
        tech_out = page.evaluate(
            """async ({projectId, label}) => {
              const res = await fetch(`/api/v1/commissioning/projects/${encodeURIComponent(projectId)}/tech-links`, {
                method: "POST",
                headers: { "content-type": "application/json" },
                body: JSON.stringify({ label }),
              });
              const ct = String(res.headers.get("content-type") || "");
              const body = ct.includes("application/json") ? await res.json() : await res.text();
              return { ok: res.ok, status: res.status, body };
            }""",
            {"projectId": project_id, "label": tech_label},
        )
        if not bool((tech_out or {}).get("ok")):
            raise RuntimeError(f"Tech link API failed: {tech_out}")
        body = (tech_out or {}).get("body") or {}
        tech_url = str((body or {}).get("techUrl") or "").strip()
        if not tech_url:
            raise RuntimeError("Empty tech URL.")

        testing_url = tech_url if tech_url.startswith("http") else f"{page.url.split('/commissioning', 1)[0]}{tech_url}"
        page.goto(testing_url, wait_until="domcontentloaded")
        links = page.locator("a.home-row.device-row")
        count = int(links.count())
        if count <= 0:
            raise RuntimeError("No device rows found in project home.")
        target_idx = max(0, min(int(device_index), count - 1))
        target = links.nth(target_idx)
        device_label = str(target.inner_text() or "").strip()

        c0 = time.perf_counter()
        target.click()
        page.wait_for_load_state("domcontentloaded")
        usable_ok = _wait_for_usable_render(page, timeout_ms)
        c1 = time.perf_counter()
        if not usable_ok:
            raise RuntimeError("Device page did not reach usable render in time.")
        ready_sec_value = page.evaluate("() => (typeof window.__sentinelReadySec === 'number' ? window.__sentinelReadySec : null)")
        if ready_sec_value is None:
            ready_sec = c1 - c0
        else:
            ready_sec = float(ready_sec_value)

        paints = page.evaluate(
            """() => {
              const entries = performance.getEntriesByType('paint') || [];
              const fp = entries.find((e) => e.name === 'first-paint');
              const fcp = entries.find((e) => e.name === 'first-contentful-paint');
              return {
                firstPaintMs: fp ? Number(fp.startTime || 0) : null,
                firstContentfulPaintMs: fcp ? Number(fcp.startTime || 0) : null,
                nodeCount: document.querySelectorAll('*').length
              };
            }"""
        )

        return {
            "run": int(run_index),
            "apexFile": apex_path.name,
            "projectName": project_name,
            "preload_sec": round(preload_sec, 3),
            "device_label": device_label,
            "ready_sec": round(ready_sec, 3),
            "first_paint_sec_from_nav": (
                round(float(paints.get("firstPaintMs")) / 1000.0, 3)
                if paints.get("firstPaintMs") is not None
                else None
            ),
            "first_contentful_paint_sec_from_nav": (
                round(float(paints.get("firstContentfulPaintMs")) / 1000.0, 3)
                if paints.get("firstContentfulPaintMs") is not None
                else None
            ),
            "node_count": int(paints.get("nodeCount") or 0),
        }
    finally:
        page.close()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Real UI benchmark for Sentinel preload and ready timing."
    )
    p.add_argument("--commissioning-url", default="http://127.0.0.1:8000/commissioning/index.html")
    p.add_argument("--assets-dir", default=str(ROOT / "Assets"))
    p.add_argument("--include-apex", action="append", default=[])
    p.add_argument("--exclude-token", action="append", default=[])
    p.add_argument("--runs", type=int, default=5)
    p.add_argument("--device-index", type=int, default=0)
    p.add_argument("--timeout-ms", type=int, default=180000)
    p.add_argument("--headless", action="store_true")
    p.add_argument("--output-json", default="")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    assets_dir = Path(args.assets_dir).resolve()
    apex_files = _discover_apex_files(
        assets_dir=assets_dir,
        include=[str(x) for x in (args.include_apex or [])],
        exclude=[str(x) for x in (args.exclude_token or [])],
    )
    if not apex_files:
        raise SystemExit("No apex files selected.")

    from playwright.sync_api import sync_playwright  # type: ignore

    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    out: dict[str, Any] = {
        "startedAtUtc": started,
        "mode": "real-ui-flow",
        "commissioningUrl": str(args.commissioning_url),
        "runsPerApex": int(args.runs),
        "deviceIndex": int(args.device_index),
        "files": [],
    }

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=bool(args.headless))
        try:
            for apex in apex_files:
                file_row: dict[str, Any] = {"apexFile": apex.name, "apexPath": str(apex), "runs": [], "summary": {}}
                for i in range(1, int(args.runs) + 1):
                    try:
                        run_row = _measure_one_run(
                            browser=browser,
                            commissioning_url=str(args.commissioning_url),
                            apex_path=apex,
                            run_index=i,
                            timeout_ms=int(args.timeout_ms),
                            device_index=int(args.device_index),
                        )
                        file_row["runs"].append(run_row)
                    except Exception as exc:
                        file_row["runs"].append({"run": int(i), "error": str(exc)})

                gen_vals = [
                    float(r["preload_sec"])
                    for r in file_row["runs"]
                    if isinstance(r, dict) and "preload_sec" in r
                ]
                ready_vals = [
                    float(r["ready_sec"])
                    for r in file_row["runs"]
                    if isinstance(r, dict) and "ready_sec" in r
                ]

                file_row["summary"] = {
                    "successfulRuns": len(gen_vals),
                    "preload_sec": {
                        "p50": (round(float(_pct(gen_vals, 50) or 0.0), 3) if gen_vals else None),
                        "p95": (round(float(_pct(gen_vals, 95) or 0.0), 3) if gen_vals else None),
                        "mean": (round(float(statistics.mean(gen_vals)), 3) if gen_vals else None),
                    },
                    "ready_sec": {
                        "p50": (round(float(_pct(ready_vals, 50) or 0.0), 3) if ready_vals else None),
                        "p95": (round(float(_pct(ready_vals, 95) or 0.0), 3) if ready_vals else None),
                        "mean": (round(float(statistics.mean(ready_vals)), 3) if ready_vals else None),
                    },
                }
                out["files"].append(file_row)
        finally:
            browser.close()

    out["endedAtUtc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    text = json.dumps(out, ensure_ascii=True, indent=2)
    print(text)
    if str(args.output_json or "").strip():
        out_path = Path(str(args.output_json)).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        print(f"WROTE_JSON {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
