"""Favicon on every tab document, wordmark only in console and management headers."""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.generation.render_core import (  # noqa: E402
    build_device_render_bundle,
    load_json,
    render_project_home_html,
)

ICON_LINK = re.compile(
    r'<link rel="icon" href="/commissioning/sentinel-logo-tab\.png" type="image/png"\s*/?>'
)
WORDMARK = "sentinel-logo-wordmark.png"
UI = ROOT / "src" / "sentinel" / "ui"
CONSOLE_HTML = UI / "commissioning" / "index.html"
MANAGEMENT_HTML = UI / "management" / "index.html"
DEVICE_SHELL_HTML = UI / "commissioning" / "project_device_static_layout.html"


def _minimal_project_data() -> dict:
    return {
        "devices": [
            {
                "userFacing": {
                    "displayName": "ISR-4",
                    "productModel": None,
                    "deviceUI": {
                        "portrait": {"supported": True, "resolution": {"width": 480, "height": 854}},
                        "landscape": {"supported": False, "resolution": {"width": 0, "height": 0}},
                    },
                    "pages": [
                        {
                            "pageName": "Home",
                            "layers": [
                                {
                                    "layerName": "Main",
                                    "sharedLayerId": 1,
                                    "layerOrder": 0,
                                    "isKeypadLayer": False,
                                    "buttonCategories": {
                                        "screenLabels": [],
                                        "screenButtons": [],
                                        "hardButtons": [],
                                        "emptyTag": [],
                                        "uiItems": [],
                                    },
                                    "viewports": [],
                                }
                            ],
                        }
                    ],
                },
                "diagnostics": {
                    "deviceId": 1,
                    "deviceName": "ISR-4",
                    "displayName": "ISR-4",
                    "rtiAddress": 1,
                    "isClonedController": False,
                    "rooms": [],
                    "sourceListRows": [],
                    "pages": [
                        {
                            "pageId": 1,
                            "pageName": "Home",
                            "pageOrder": 0,
                            "pageNumber": 1,
                            "uiItems": [],
                            "buttons": [],
                            "viewports": [],
                        }
                    ],
                },
            }
        ],
        "events": {"system": [], "macro": [], "macroStep": []},
        "source": {"file": "uploads/demo/Holtby_ISR.apex"},
    }


def _png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    self_check = data[:8] == b"\x89PNG\r\n\x1a\n"
    if not self_check or data[12:16] != b"IHDR":
        raise AssertionError(f"{path.name} is not a PNG")
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    return width, height


def _topbar(html: str) -> str:
    match = re.search(r'<header class="topbar">.*?</header>', html, flags=re.S)
    if match is None:
        raise AssertionError("topbar was not found")
    return match.group(0)


class SentinelLogoTests(unittest.TestCase):
    def test_tab_documents_link_shield_favicon(self) -> None:
        app_ui = load_json(ROOT / "src" / "sentinel" / "contracts" / "app_ui_structure.json")
        project_data = _minimal_project_data()
        home_html = render_project_home_html(
            project_data,
            app_ui,
            project_stem="minimal",
            client_name="Blue Ember",
            project_name="Holtby ISR",
        )
        device_html = str(
            build_device_render_bundle(
                project_data,
                app_ui,
                project_stem="minimal",
                device_index=0,
                client_name="Blue Ember",
                project_name="Holtby ISR",
            ).get("html")
            or ""
        )
        documents = {
            "console": CONSOLE_HTML.read_text(encoding="utf-8"),
            "management": MANAGEMENT_HTML.read_text(encoding="utf-8"),
            "device shell": DEVICE_SHELL_HTML.read_text(encoding="utf-8"),
            "project home": home_html,
            "device page": device_html,
        }
        for name, html in documents.items():
            self.assertRegex(html, ICON_LINK, msg=name)
        tab_icon = UI / "commissioning" / "sentinel-logo-tab.png"
        self.assertEqual(_png_size(tab_icon), (687, 687))

    def test_wordmark_is_only_in_console_and_management_topbars(self) -> None:
        console = CONSOLE_HTML.read_text(encoding="utf-8")
        management = MANAGEMENT_HTML.read_text(encoding="utf-8")
        device_shell = DEVICE_SHELL_HTML.read_text(encoding="utf-8")
        self.assertIn(WORDMARK, _topbar(console))
        self.assertIn('alt="Sentinel"', _topbar(console))
        self.assertIn("Sentinel Console", _topbar(console))
        self.assertIn(WORDMARK, _topbar(management))
        self.assertIn('alt="Sentinel"', _topbar(management))
        self.assertIn("Sentinel Management", _topbar(management))
        self.assertIn("Active technician links grouped by user.", management)
        self.assertNotIn(WORDMARK, device_shell)


if __name__ == "__main__":
    unittest.main()
