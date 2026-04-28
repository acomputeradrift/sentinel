"""Playwright CLI proof: commissioning shell shows hard-key strip layout (CSS bypass).

Follows the playwright skill: npx @playwright/cli playwright-cli (open, run-code, eval, screenshot).

Builds output/playwright/{hk_device.html,shell.html,css}, serves them, drives Chromium via CLI.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
OUT = ROOT / "output" / "playwright"
SHELL_SRC = ROOT / "src" / "sentinel" / "ui" / "commissioning" / "project_device_static_layout.html"
CSS_SRC = ROOT / "src" / "sentinel" / "ui" / "commissioning" / "project_device_static_layout.css"
SESSION = "sentinel-hk-shell-proof"


def _ensure_src_path() -> None:
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))


def _minimal_t4x_project() -> dict:
    hk_buttons = [
        {
            "buttonIdentity": {"buttonTagName": "Power", "text": "Power", "buttonType": None},
            "apexScopeSource": {"button": {"buttonId": 1}},
            "testTargets": {"text": True, "macros": False, "macroSteps": False, "variables": {}},
        },
    ]
    hk_slots = [{"buttonId": 1, "slotKey": 128}]
    return {
        "devices": [
            {
                "userFacing": {
                    "displayName": "T4x CLI Proof",
                    "productModel": "t4x",
                    "deviceUI": {
                        "portrait": {"supported": True, "resolution": {"width": 480, "height": 854}},
                        "landscape": {"supported": False, "resolution": {"width": 854, "height": 480}},
                    },
                    "pages": [
                        {
                            "pageName": "Home",
                            "layers": [
                                {
                                    "layerName": "Screen",
                                    "layerOrder": 0,
                                    "isKeypadLayer": False,
                                    "buttonCategories": {
                                        "screenLabels": [],
                                        "hardButtons": [],
                                        "screenButtons": [],
                                    },
                                    "viewports": [],
                                },
                                {
                                    "layerName": "Hard Keys",
                                    "layerOrder": 1,
                                    "isKeypadLayer": True,
                                    "hardKeyLayer": {"slots": hk_slots},
                                    "buttonCategories": {
                                        "screenLabels": [],
                                        "hardButtons": hk_buttons,
                                        "screenButtons": [],
                                    },
                                    "viewports": [],
                                },
                            ],
                        }
                    ],
                },
                "diagnostics": {"deviceId": 1, "pages": [{"pageId": 1, "pageName": "Home"}]},
            }
        ]
    }


def _npx_exe() -> str:
    import shutil

    for name in ("npx.cmd", "npx"):
        p = shutil.which(name)
        if p:
            return p
    raise FileNotFoundError("npx not on PATH (install Node.js / npm)")


def _pw_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    cmd = [
        _npx_exe(),
        "--yes",
        "--package",
        "@playwright/cli",
        "playwright-cli",
        "--session",
        SESSION,
        *args,
    ]
    return subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def main() -> int:
    _ensure_src_path()
    from sentinel.generation.render_core import render_single_device_html

    OUT.mkdir(parents=True, exist_ok=True)
    app_ui = {
        "layout": {
            "appCanvas": {"mode": "browser-viewport"},
            "appUIControls": {"top": 52, "bottom": 32, "left": 0, "right": 0},
            "rtiCanvas": {"deriveFromAppCanvas": True},
            "rtiDeviceCanvas": {"fitMode": "contain", "allowScaleAboveOne": True, "maxScale": 10, "minScale": 0.1},
        },
        "header": {"enabled": False, "titleTemplate": "{deviceName}"},
        "appNavigation": {"enabled": False, "pageLinks": {"enabled": False}},
        "zoomControls": {"enabled": False},
        "viewportNavigation": {"enabled": False},
        "testingPopup": {"enabled": False},
        "buttonPresentation": {"fallbackFontSize": 12, "scaleRtiDerivedFontSizes": True},
        "state": {},
        "layerPanel": {"enabled": False},
    }
    html = render_single_device_html(
        _minimal_t4x_project(),
        app_ui,
        project_stem="playwright_hk_shell",
        device_index=0,
    )
    if "data-sentinel-hard-key-template" not in html:
        print("FAIL: generated device HTML missing data-sentinel-hard-key-template", file=sys.stderr)
        return 2
    (OUT / "hk_device.html").write_text(html, encoding="utf-8")

    shell_text = SHELL_SRC.read_text(encoding="utf-8")
    meta = '  <meta name="sentinel-shell-source" content="__SOURCE_URL__">\n'
    if '<meta name="sentinel-shell-source"' in shell_text:
        print("FAIL: shell template already had sentinel-shell-source meta", file=sys.stderr)
        return 2
    injected = shell_text.replace("<meta charset=\"utf-8\">", "<meta charset=\"utf-8\">\n" + meta, 1)
    shutil.copyfile(CSS_SRC, OUT / "project_device_static_layout.css")

    class _Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(OUT), **kw)

        def log_message(self, fmt: str, *args) -> None:
            return

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    source_url = f"{base}/hk_device.html"
    shell_final = injected.replace("__SOURCE_URL__", source_url)
    (OUT / "shell.html").write_text(shell_final, encoding="utf-8")

    shell_page = f"{base}/shell.html"
    try:
        r = _pw_cli(["close"])
        _ = r  # ignore if no session

        # playwright-cli defaults to system Chrome; use Firefox (Playwright-managed) when Chrome is absent.
        r0 = _pw_cli(["open", shell_page, "--browser", "firefox"])
        if r0.returncode != 0:
            print(r0.stdout, r0.stderr, file=sys.stderr)
            return r0.returncode or 1

        wait_js = (
            "await page.waitForSelector('.hk-split-right .frame', { timeout: 30000 }); "
            "await page.waitForFunction(() => typeof window.applyRtiLayout === 'function'); "
            "await page.evaluate(() => { if (typeof window.applyRtiLayout === 'function') window.applyRtiLayout(); }); "
            "await page.waitForTimeout(500);"
        )
        r1 = _pw_cli(["run-code", wait_js])
        if r1.returncode != 0:
            print("run-code failed:", r1.stdout, r1.stderr, file=sys.stderr)
            return r1.returncode or 1

        eval_js = (
            "() => JSON.stringify({"
            "hkStyleBlocks: document.querySelectorAll('style[data-shell-source-style-hard-keys]').length,"
            "hasFrame: !!document.querySelector('.hk-split-right .frame'),"
            "rightWidth: (() => { const r = document.querySelector('.hk-split-right'); "
            "return r ? r.getBoundingClientRect().width : 0; })(),"
            "frameVarPx: (() => { const r = document.querySelector('.hk-split-right'); "
            "if (!r) return ''; return String(getComputedStyle(r).getPropertyValue('--frame-w') || '').trim(); })()"
            "})"
        )
        r2 = _pw_cli(["eval", eval_js, "--raw"])
        if r2.returncode != 0:
            print("eval failed:", r2.stdout, r2.stderr, file=sys.stderr)
            return r2.returncode or 1

        raw_out = (r2.stdout or "").strip()
        try:
            out = json.loads(raw_out)
            if isinstance(out, str):
                out = json.loads(out)
        except (json.JSONDecodeError, TypeError):
            print("FAIL: eval stdout not JSON:", raw_out[:500], file=sys.stderr)
            return 1
        shot = OUT / "hk_shell_proof.png"
        r3 = _pw_cli(["screenshot", str(shot)])
        if r3.returncode != 0:
            print("screenshot failed:", r3.stdout, r3.stderr, file=sys.stderr)

        _pw_cli(["close"])

        print(json.dumps({"playwrightEval": out, "screenshot": str(shot)}, indent=2))
        frame_var = str(out.get("frameVarPx") or "")
        ok = (
            int(out.get("hkStyleBlocks") or 0) >= 1
            and bool(out.get("hasFrame"))
            and float(out.get("rightWidth") or 0) > 10
            and ("px" in frame_var or "vw" in frame_var)
        )
        if not ok:
            print("FAIL: layout assertions:", out, file=sys.stderr)
            return 1
        print("PASS: shell mounted hard-key strip (--frame-w set, .frame visible, bypass style present).")
        return 0
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


if __name__ == "__main__":
    raise SystemExit(main())
