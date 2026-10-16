from __future__ import annotations

import json
import re
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
    self.assertIn("Blue Ember", html)
    self.assertIn("home-project-name", html)
    self.assertIn("Holtby ISR", html)
    self.assertIn("Current File:", html)
    self.assertIn("Holtby_ISR.apex", html)
    self.assertNotIn("uploads", html)
    self.assertIn("<title>Blue Ember: Holtby ISR</title>", html)
    self.assertNotIn("home-client-name", html)
    self.assertIn("<h1 class='home-title home-project-name'>Holtby ISR</h1>", html)
    self.assertIn("Current File: Holtby_ISR.apex", html)

  def test_project_home_title_omits_empty_client_without_dangling_colon(self) -> None:
    project_data = _minimal_project_data()
    app_ui = load_json(
        Path(__file__).resolve().parents[2] / "src" / "sentinel" / "contracts" / "app_ui_structure.json"
    )
    html = render_project_home_html(
        project_data,
        app_ui,
        project_stem="minimal",
        client_name="",
        project_name="Holtby ISR",
    )
    self.assertIn("<title>Holtby ISR</title>", html)
    self.assertNotIn("<title>:", html)
    self.assertIn("<h1 class='home-title home-project-name'>Holtby ISR</h1>", html)
    self.assertIn("Current File: Holtby_ISR.apex", html)

  def test_project_home_title_does_not_replace_heading_with_filename_stem(self) -> None:
    project_data = _minimal_project_data()
    app_ui = load_json(
        Path(__file__).resolve().parents[2] / "src" / "sentinel" / "contracts" / "app_ui_structure.json"
    )
    html = render_project_home_html(
        project_data,
        app_ui,
        project_stem="minimal",
        client_name="Blue Ember",
        project_name="",
    )
    self.assertIn("<title>Blue Ember</title>", html)
    self.assertNotIn("<title>Blue Ember:", html)
    self.assertNotIn("home-client-name", html)
    self.assertIn("<h1 class='home-title home-project-name'>Holtby_ISR</h1>", html)
    self.assertIn("Current File: Holtby_ISR.apex", html)

  def test_project_home_heading_and_current_file_hide_upload_id(self) -> None:
    upload_id = "19c4a933-da0c-4a25-aac8-18c61c8f08f2"
    original_name = "1790 High Rd (Simple v32.2).apex"
    project_data = _minimal_project_data()
    project_data["source"] = {
        "file": f"uploads/proj/{upload_id}__{original_name}",
    }
    app_ui = load_json(
        Path(__file__).resolve().parents[2] / "src" / "sentinel" / "contracts" / "app_ui_structure.json"
    )
    html = render_project_home_html(
        project_data,
        app_ui,
        project_stem="minimal",
        project_name="1790 High Rd",
    )
    project_h1 = _class_element_text(html, "h1", "home-project-name")
    current_file = _current_file_text(html)
    self.assertEqual(project_h1, "1790 High Rd")
    self.assertEqual(current_file, original_name)
    self.assertNotIn(upload_id, project_h1)
    self.assertNotIn(upload_id, current_file)
    self.assertNotIn("home-client-name", html)
    self.assertNotIn(upload_id, html)
    self.assertIn("<title>1790 High Rd</title>", html)
    self.assertNotIn(f"{upload_id}__", html)

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
    self.assertIn("<title>Holtby ISR: ISR-4</title>", html)
    self.assertIn("class='header'>ISR-4: Home</div>", html)
    self.assertIn("class='project-home-link' href=", html)
    self.assertIn(">Holtby ISR Home</a>", html)
    self.assertNotIn("Blue Ember -> Holtby ISR -> ISR-4 -> Home", html.split("const APP_UI=", 1)[0])
    sync = _sync_header_source(html)
    self.assertIn("${deviceName}: ${pageName}", sync)
    self.assertNotIn(" - ", sync)
    self.assertNotIn("titleTemplate", sync)
    self.assertNotIn("clientName", sync)

  def test_device_titles_omit_empty_project_without_dangling_colon(self) -> None:
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
        project_name="",
    )
    html = str(bundle.get("html") or "")
    self.assertIn("<title>ISR-4</title>", html)
    self.assertNotIn("<title>:", html)
    self.assertNotIn("<title>ISR-4:", html)
    self.assertIn("class='header'>ISR-4: Home</div>", html)
    self.assertIn(">Project Home</a>", html)
    self.assertNotIn("> Home</a>", html)

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
    self.assertIn("function applyDocumentTitle(sourceDoc)", text)
    self.assertIn("applyDocumentTitle(sourceDoc);", text)
    self.assertIn("document.title", text)
    self.assertIn('querySelector("title")', text)


def _class_element_text(html: str, tag: str, class_name: str) -> str:
    match = re.search(
        rf"<{tag} class='[^']*\b{re.escape(class_name)}\b[^']*'>(.*?)</{tag}>",
        html,
        flags=re.S,
    )
    if match is None:
        raise AssertionError(f"{class_name} element was not rendered")
    return match.group(1)


def _current_file_text(html: str) -> str:
    match = re.search(r"class='home-source'>Current File: ([^<]*)</div>", html)
    if match is None:
        raise AssertionError("Current File line was not rendered")
    return match.group(1)


def _sync_header_source(html: str) -> str:
    match = re.search(r"function syncHeader\(\) \{.*?\n\}", html, flags=re.S)
    if match is None:
        raise AssertionError("syncHeader was not rendered")
    return match.group(0)


if __name__ == "__main__":
  unittest.main()
