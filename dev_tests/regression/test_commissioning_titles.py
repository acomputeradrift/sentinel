from __future__ import annotations

import json
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.generation.render_core import (
    build_device_render_bundle,
    format_page_header_title,
    format_row_status_line,
    load_json,
    render_project_home_html,
)


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
                    "pages": [{"pageId": 1, "pageName": "Home", "pageOrder": 0, "pageNumber": 1, "uiItems": [], "buttons": [], "viewports": []}],
                },
            }
        ],
        "events": {"system": [], "macro": [], "macroStep": []},
        "source": {"file": "uploads/demo/Holtby_ISR.apex"},
    }


class CommissioningTitlesTests(unittest.TestCase):
  def test_page_header_breadcrumb_template(self) -> None:
    app_ui = load_json(
        Path(__file__).resolve().parents[2] / "src" / "sentinel" / "contracts" / "app_ui_structure.json"
    )
    template = app_ui["header"]["titleTemplate"]
    self.assertIn("{clientName}", template)
    self.assertIn("{projectName}", template)
    title = format_page_header_title(
        template,
        client_name="Blue Ember",
        project_name="Holtby ISR",
        device_name="ISR-4",
        page_name="Home",
    )
    self.assertEqual(title, "Blue Ember -> Holtby ISR -> ISR-4 -> Home")

  def test_popup_title_template_in_contract(self) -> None:
    app_ui = load_json(
        Path(__file__).resolve().parents[2] / "src" / "sentinel" / "contracts" / "app_ui_structure.json"
    )
    self.assertEqual(app_ui["testingPopup"]["titleTemplate"], "{category} - {identity}")

  def test_row_status_line(self) -> None:
    line = format_row_status_line("Jamie", "2026-05-27 18:30:00Z")
    self.assertEqual(line, "Passed by Jamie: 2026-05-27 18:30:00Z")

  def test_project_home_embeds_client_project_and_basename(self) -> None:
    project_data = _minimal_project_data()
    app_ui = load_json(
        Path(__file__).resolve().parents[2] / "src" / "sentinel" / "contracts" / "app_ui_structure.json"
    )
    html = render_project_home_html(
        project_data,
        app_ui,
        project_stem="minimal",
        client_name="Blue Ember",
        project_name="Holtby ISR",
    )
    self.assertIn("home-client-name", html)
    self.assertIn("Blue Ember", html)
    self.assertIn("home-project-name", html)
    self.assertIn("Holtby ISR", html)
    self.assertIn("Current File:", html)
    self.assertIn("Holtby_ISR.apex", html)
    self.assertNotIn("uploads", html)

  def test_device_html_embeds_commissioning_meta(self) -> None:
    project_data = _minimal_project_data()
    app_ui = load_json(
        Path(__file__).resolve().parents[2] / "src" / "sentinel" / "contracts" / "app_ui_structure.json"
    )
    bundle = build_device_render_bundle(
        project_data,
        app_ui,
        project_stem="minimal",
        device_index=0,
        client_name="Blue Ember",
        project_name="Holtby ISR",
    )
    html = str(bundle.get("html") or "")
    self.assertIn('meta name="sentinel-client-name" content="Blue Ember"', html)
    self.assertIn('meta name="sentinel-project-name" content="Holtby ISR"', html)
    self.assertIn("readCommissioningTitles", html)
    self.assertIn("formatRowStatusLine", html)

  def test_syncHeader_uses_top_controls_get_element_by_id(self) -> None:
    render_core_path = Path(__file__).resolve().parents[2] / "src" / "sentinel" / "generation" / "render_core.py"
    text = render_core_path.read_text(encoding="utf-8")
    self.assertIn("function syncHeader()", text)
    self.assertIn("document.getElementById('topControls')", text)
    self.assertIn("headerRoot.querySelector('.header')", text)

  def test_shell_layout_copies_commissioning_meta(self) -> None:
    shell_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "sentinel"
        / "ui"
        / "commissioning"
        / "project_device_static_layout.html"
    )
    text = shell_path.read_text(encoding="utf-8")
    self.assertIn("function copyCommissioningMeta(sourceDoc)", text)
    self.assertIn("copyCommissioningMeta(sourceDoc);", text)


if __name__ == "__main__":
  unittest.main()
