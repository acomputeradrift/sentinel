import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.extraction import extractor_core


class ButtonCategoryRulesTest(unittest.TestCase):
    def test_macro_ids_resolve_when_any_macro_targets_effective_source(self):
        resolved = extractor_core._macro_ids_resolve_for_effective_source(
            macro_ids=[50, 75],
            macro_non_empty_by_id={50: True, 75: True},
            macro_device_ids_by_macro={50: {9}, 75: {12}},
            effective_source_id=12,
        )
        self.assertTrue(resolved)

    def test_macro_ids_do_not_resolve_when_only_other_sources_exist(self):
        resolved = extractor_core._macro_ids_resolve_for_effective_source(
            macro_ids=[49, 74],
            macro_non_empty_by_id={49: True, 74: True},
            macro_device_ids_by_macro={49: {9}, 74: {10}},
            effective_source_id=12,
        )
        self.assertFalse(resolved)

    def test_macro_ids_resolve_when_non_empty_macro_is_source_agnostic(self):
        resolved = extractor_core._macro_ids_resolve_for_effective_source(
            macro_ids=[201],
            macro_non_empty_by_id={201: True},
            macro_device_ids_by_macro={},
            effective_source_id=12,
        )
        self.assertTrue(resolved)

    def test_hard_button_wins_over_ui_item(self):
        button = {
            "buttonIdentity": {"buttonType": None, "buttonTagName": None},
            "buttonUI": {
                "orientations": {
                    "portrait": {"coordinates": {"height": 0, "width": 0}},
                    "landscape": {"coordinates": {"height": 0, "width": 0}},
                }
            },
            "testTargets": {
                "text": False,
                "macros": False,
                "macroSteps": False,
                "variables": {"Text": False},
                "pageLink": False,
            },
        }
        category = extractor_core._classify_user_button_category(
            button=button,
            has_tag_field=False,
            raw_text="",
            has_macros_target=False,
            has_any_variable_target=False,
        )
        self.assertEqual("hardButtons", category)

    def test_ui_item_when_empty_and_not_hard(self):
        button = {
            "buttonIdentity": {"buttonType": None, "buttonTagName": None},
            "buttonUI": {
                "orientations": {
                    "portrait": {"coordinates": {"height": 12, "width": 20}},
                    "landscape": {"coordinates": {"height": 12, "width": 20}},
                }
            },
            "testTargets": {
                "text": False,
                "macros": False,
                "macroSteps": False,
                "variables": {"Text": False},
                "pageLink": False,
            },
        }
        category = extractor_core._classify_user_button_category(
            button=button,
            has_tag_field=False,
            raw_text="",
            has_macros_target=False,
            has_any_variable_target=False,
        )
        self.assertEqual("uiItems", category)

    def test_empty_tag_category_requires_tag_field_present(self):
        button = {
            "buttonIdentity": {"buttonType": None, "buttonTagName": ""},
            "buttonUI": {
                "orientations": {
                    "portrait": {"coordinates": {"height": 10, "width": 10}},
                    "landscape": {"coordinates": {"height": 10, "width": 10}},
                }
            },
            "testTargets": {
                "text": False,
                "macros": False,
                "macroSteps": False,
                "variables": {"Text": False},
                "pageLink": False,
            },
        }
        with_tag = extractor_core._classify_user_button_category(
            button=button,
            has_tag_field=True,
            raw_text="label",
            has_macros_target=False,
            has_any_variable_target=False,
        )
        without_tag = extractor_core._classify_user_button_category(
            button=button,
            has_tag_field=False,
            raw_text="label",
            has_macros_target=False,
            has_any_variable_target=False,
        )
        self.assertEqual("emptyTag", with_tag)
        self.assertEqual("screenButtons", without_tag)

    def test_effective_empty_tag_overrides_hard_button_when_content_missing(self):
        button = {
            "buttonIdentity": {"buttonType": None, "buttonTagName": "Channel Up"},
            "buttonUI": {
                "orientations": {
                    "portrait": {"coordinates": {"height": 0, "width": 0}},
                    "landscape": {"coordinates": {"height": 0, "width": 0}},
                }
            },
            "testTargets": {
                "text": False,
                "macros": False,
                "macroSteps": False,
                "variables": {"Text": False},
                "pageLink": False,
            },
        }
        category = extractor_core._classify_user_button_category(
            button=button,
            has_tag_field=True,
            raw_text="",
            has_macros_target=False,
            has_any_variable_target=False,
            has_meaningful_tag_content=False,
        )
        self.assertEqual("emptyTag", category)

    def test_hard_button_remains_hard_button_when_meaningful_content_exists(self):
        button = {
            "buttonIdentity": {"buttonType": None, "buttonTagName": "Volume Up"},
            "buttonUI": {
                "orientations": {
                    "portrait": {"coordinates": {"height": 0, "width": 0}},
                    "landscape": {"coordinates": {"height": 0, "width": 0}},
                }
            },
            "testTargets": {
                "text": False,
                "macros": False,
                "macroSteps": True,
                "variables": {"Text": False},
                "pageLink": False,
            },
        }
        category = extractor_core._classify_user_button_category(
            button=button,
            has_tag_field=True,
            raw_text="",
            has_macros_target=False,
            has_any_variable_target=False,
            has_meaningful_tag_content=True,
        )
        self.assertEqual("hardButtons", category)


if __name__ == "__main__":
    unittest.main()
