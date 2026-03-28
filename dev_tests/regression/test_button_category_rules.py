import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.extraction import extractor_core


class ButtonCategoryRulesTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
