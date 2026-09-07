"""Full operator path inside Docker: Load File → device → Pass → commissioning.

Requires SENTINEL_OPS_BASE_URL (set by dev_tests/ops/compose.yml).
"""
from __future__ import annotations

import os
import socket
import sys
import time
import unittest
from urllib.parse import urlparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class OpsFullRunTest(unittest.TestCase):
    def test_load_file_device_pass_appears_in_commissioning(self):
        raw_url = str(os.environ.get("SENTINEL_OPS_BASE_URL") or "").rstrip("/")
        self.assertTrue(
            raw_url,
            "SENTINEL_OPS_BASE_URL is required. Run: python devtools/run_ops_load_file.py",
        )
        parsed = urlparse(raw_url)
        self.assertTrue(parsed.hostname, f"Invalid SENTINEL_OPS_BASE_URL: {raw_url}")
        ip = socket.getaddrinfo(parsed.hostname, parsed.port or 80, type=socket.SOCK_STREAM)[0][4][0]
        base_url = f"http://{ip}:{parsed.port or 80}"

        from dev_tests.integration.test_scripts import apex_fixture_path

        apex_path = apex_fixture_path()
        self.assertIsNotNone(apex_path, "No .apex fixture. Put one in Assets/ or set SENTINEL_TEST_APEX.")
        assert apex_path is not None

        try:
            from playwright.sync_api import expect, sync_playwright
        except Exception as e:
            self.fail(f"Playwright is required: {e}")

        pw = sync_playwright().start()
        browser = pw.chromium.launch(
            headless=True,
            args=["--disable-features=HttpsUpgrades,HttpsFirstBalancedModeAutoEnable"],
        )
        try:
            context = browser.new_context(ignore_https_errors=True)
            tech_logs: list[str] = []
            context.on("console", lambda msg: tech_logs.append(str(msg.text or "")))
            page = context.new_page()
            page_errors: list[str] = []
            page.on("pageerror", lambda err: page_errors.append(str(err)))

            page.goto(f"{base_url}/commissioning/")
            page.get_by_role("button", name="File").click()
            page.locator("#clientSelect").select_option(value="__new_client__")
            page.locator("#modalNewClientName").fill("Ops Full Client")
            page.locator("#modalNewClientSubmit").click()
            page.locator("#projectSelect").select_option(value="__new_project__")
            page.locator("#modalNewProjectName").fill("Ops Full Job")
            page.locator("#modalNewProjectSubmit").click()
            expect(page.get_by_label("Project", exact=True)).not_to_have_value("")

            page.set_input_files("input[type=file][name=apex]", str(apex_path))
            with page.expect_response(
                lambda r: "upload-and-regenerate" in r.url and r.ok,
                timeout=120000,
            ) as upload_info:
                page.get_by_role("button", name="Load File").click()
            self.assertEqual(upload_info.value.status, 200, upload_info.value.text())
            self.assertNotIn("Internal Server Error", page.locator("#panel-file").inner_text())
            problems: list[str] = []
            file_label = page.locator("#lastGeneratedLabel").inner_text().strip()
            if file_label != f"Currently Testing {apex_path.name}":
                problems.append(f"File card stayed {file_label!r} after Load File 200")

            page.goto(f"{base_url}/management/")
            expect(page.get_by_role("heading", name="Sentinel Management")).to_be_visible()
            page.locator("#clientSelect").select_option(label="Ops Full Client")
            page.locator("#projectSelect").select_option(label="Ops Full Job")
            page.locator("#techLinkName").fill("Ops Tech")
            page.get_by_role("button", name="Issue or reuse link").click()
            expect(page.get_by_test_id("tech-url")).to_contain_text("/testing/", timeout=15000)

            with page.expect_popup() as popup_info:
                page.get_by_role("button", name="Open").click()
            tech = popup_info.value
            tech.wait_for_load_state("domcontentloaded")
            self.assertIn("/testing/", tech.url)
            ws_deadline = time.time() + 20
            while time.time() < ws_deadline:
                if any("[tech-ws] connect" in line for line in tech_logs):
                    break
                time.sleep(0.15)
            else:
                self.fail(f"Tech WebSocket did not connect. logs={tech_logs[-30:]}")
            time.sleep(1.0)

            button_label = ""
            tech.locator("button.section-toggle[data-target='system-events']").click()
            home_btns = tech.locator(".btn-wrap--home-event .test-btn")
            if home_btns.count() == 0:
                tech.locator("button.section-toggle[data-target='driver-events']").click()
                home_btns = tech.locator("#driver-events .btn-wrap--home-event .test-btn")
            self.assertGreater(home_btns.count(), 0, "Generated project has no home event targets to Pass.")
            button_label = home_btns.first.inner_text().strip()
            home_btns.first.click()
            expect(tech.locator("#ov")).to_be_visible()
            tech.locator("#rows").get_by_role("button", name="Pass").first.click()
            deadline = time.time() + 20
            while time.time() < deadline:
                if any("test_result" in line for line in tech_logs):
                    break
                time.sleep(0.2)
            else:
                self.fail(
                    "Pass did not submit a test_result. "
                    f"postStatus={tech.locator('#postStatus').inner_text()!r} logs={tech_logs[-40:]}"
                )
            close_btn = tech.locator("#close")
            if close_btn.is_visible():
                close_btn.click()

            tech.locator("button.section-toggle[data-target='devices']").click()
            device_link = tech.locator("a.home-row.device-row").first
            expect(device_link).to_be_visible()
            device_link.click()
            expect(tech.locator(".device-page, .rti-device-canvas").first).to_be_visible(timeout=30000)

            page.goto(f"{base_url}/commissioning/")
            page.locator("#clientSelect").select_option(label="Ops Full Client")
            page.locator("#projectSelect").select_option(label="Ops Full Job")
            page.get_by_role("button", name="Commissioning").click()
            expect(page.locator("#commissionActivityBody")).to_contain_text("PASS", timeout=40000)
            activity = page.locator("#commissionActivityBody").inner_text()
            self.assertIn(button_label, activity, f"Commissioning missing {button_label!r}: {activity!r}")
            page.get_by_role("button", name="Diagnostics").click()
            expect(page.locator("#diagnosticsTaskTable")).to_contain_text("PASS", timeout=20000)
            self.assertFalse(page_errors, f"Page errors: {page_errors}")
            if problems:
                self.fail("; ".join(problems))
        finally:
            browser.close()
            pw.stop()


if __name__ == "__main__":
    unittest.main()
