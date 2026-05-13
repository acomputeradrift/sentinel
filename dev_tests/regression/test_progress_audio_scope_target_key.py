"""Regression: redirected hard-key buttons collapse to a single shared targetKey.

See docs/audio_scope_investigation.md for the locked rules. Phase B reuses the
existing identity-by-targetKey equivalence mechanism — a redirected hard-key
button with non-null apexScopeSource.audioScope emits a wrapper-anchored key
instead of the per-button tt2: key. All vol+/vol-/mute buttons in the same
room (and on every page in that room) collapse to the same string, so a single
test result automatically applies to all of them via the existing append-only
history -> latest-record-per-targetKey model.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sentinel.server.services import progress


def _apex_scope_source(
    *,
    rti_address: int = 2,
    page_room_id: int = 12,
    page_source_id: int = 74,
    page_id: int = 513,
    layer_id: int = 300,
    shared_layer_id: int = 700,
    layer_room_id: int | None = 12,
    layer_source_id: int | None = 74,
    button_id: int = 48551,
    button_tag_id: int | None = 14,
    macro_ids: list[int] | None = None,
    audio_scope: dict | None = None,
) -> dict:
    """Build a user-side apexScopeSource dict mirroring extractor_core output."""
    return {
        "page": {
            "pageId": page_id,
            "roomId": page_room_id,
            "sourceDeviceId": page_source_id,
            "rtiAddress": rti_address,
        },
        "viewportLayer": {
            "layerId": layer_id,
            "sharedLayerId": shared_layer_id,
            "roomId": layer_room_id,
            "sourceId": layer_source_id,
        },
        "pageLayer": {"roomId": None, "sourceId": None},
        "button": {"buttonId": button_id, "buttonTagId": button_tag_id},
        "bindings": {
            "macroIds": list(macro_ids) if macro_ids else [],
            "variableIds": [],
            "macroStepIds": [],
            "pageLinkId": None,
        },
        "audioScope": audio_scope,
    }


class RedirectedHardKeyCollapsedKeyTest(unittest.TestCase):
    """Phase B: when audioScope is non-null, the targetKey collapses to a
    wrapper-anchored form so the three hard keys (vol+/vol-/mute) share it."""

    def test_redirected_hard_key_emits_collapsed_key(self) -> None:
        button = {
            "apexScopeSource": _apex_scope_source(
                button_tag_id=14,
                macro_ids=[3122],
                audio_scope={"roomId": 12, "wrapperDeviceId": 166},
            )
        }
        scoped = progress._scoped_target_key_from_button(button=button, label="System Macro")
        self.assertEqual(scoped, "tt2_audio:2:ROOM:12:166:System Macro")

    def test_three_hard_keys_in_same_room_collapse_to_identical_key(self) -> None:
        """vol+/vol-/mute share buttonTagId+macroId variation but same wrapper -> one key."""
        keys: set[str] = set()
        for tag_id, macro_id in ((14, 3122), (22, 3123), (19, 3124)):
            button = {
                "apexScopeSource": _apex_scope_source(
                    button_tag_id=tag_id,
                    macro_ids=[macro_id],
                    audio_scope={"roomId": 12, "wrapperDeviceId": 166},
                )
            }
            scoped = progress._scoped_target_key_from_button(button=button, label="System Macro")
            self.assertIsNotNone(scoped)
            assert scoped is not None
            keys.add(scoped)
        self.assertEqual(len(keys), 1, f"Expected one shared key, got {keys}")

    def test_same_hard_key_on_different_pages_in_same_room_collapse(self) -> None:
        """vol+ on Theater Home and vol+ on Theater AppleTV must share the same key."""
        home = {
            "apexScopeSource": _apex_scope_source(
                page_id=513, button_id=48551, button_tag_id=14,
                audio_scope={"roomId": 12, "wrapperDeviceId": 166},
            )
        }
        appletv = {
            "apexScopeSource": _apex_scope_source(
                page_id=999, button_id=99999, button_tag_id=14,
                audio_scope={"roomId": 12, "wrapperDeviceId": 166},
            )
        }
        home_key = progress._scoped_target_key_from_button(button=home, label="System Macro")
        appletv_key = progress._scoped_target_key_from_button(button=appletv, label="System Macro")
        self.assertIsNotNone(home_key)
        self.assertEqual(home_key, appletv_key)

    def test_two_rooms_with_different_wrappers_emit_different_keys(self) -> None:
        theater = {
            "apexScopeSource": _apex_scope_source(
                page_room_id=12, layer_room_id=12,
                audio_scope={"roomId": 12, "wrapperDeviceId": 166},
            )
        }
        rec_room = {
            "apexScopeSource": _apex_scope_source(
                page_room_id=7, layer_room_id=7,
                audio_scope={"roomId": 7, "wrapperDeviceId": 168},
            )
        }
        theater_key = progress._scoped_target_key_from_button(button=theater, label="System Macro")
        rec_key = progress._scoped_target_key_from_button(button=rec_room, label="System Macro")
        self.assertNotEqual(theater_key, rec_key)
        self.assertEqual(theater_key, "tt2_audio:2:ROOM:12:166:System Macro")
        self.assertEqual(rec_key, "tt2_audio:2:ROOM:7:168:System Macro")

    def test_collapsed_key_distinct_prefix_from_normal_key(self) -> None:
        """The collapsed key must not collide with any normal tt2: key."""
        normal_button = {
            "apexScopeSource": _apex_scope_source(
                button_tag_id=14, macro_ids=[3122], audio_scope=None,
            )
        }
        redirected_button = {
            "apexScopeSource": _apex_scope_source(
                button_tag_id=14, macro_ids=[3122],
                audio_scope={"roomId": 12, "wrapperDeviceId": 166},
            )
        }
        normal_key = progress._scoped_target_key_from_button(button=normal_button, label="System Macro")
        redirected_key = progress._scoped_target_key_from_button(button=redirected_button, label="System Macro")
        self.assertIsNotNone(normal_key)
        self.assertIsNotNone(redirected_key)
        assert normal_key is not None and redirected_key is not None
        self.assertTrue(normal_key.startswith("tt2:"))
        self.assertTrue(redirected_key.startswith("tt2_audio:"))
        self.assertNotEqual(normal_key, redirected_key)


class NonRedirectedHardKeyUnchangedTest(unittest.TestCase):
    """Phase B must not change behavior for any button without audioScope."""

    def test_non_redirected_hard_key_uses_normal_key(self) -> None:
        button = {
            "apexScopeSource": _apex_scope_source(
                button_tag_id=14, macro_ids=[3122], audio_scope=None,
            )
        }
        scoped = progress._scoped_target_key_from_button(button=button, label="System Macro")
        self.assertEqual(scoped, "tt2:2:ROOM:12:74:14:macro:3122:System Macro")

    def test_button_missing_audio_scope_field_uses_normal_key(self) -> None:
        """Defensive: older fixtures without the audioScope key should fall back."""
        scope_source = _apex_scope_source(button_tag_id=14, macro_ids=[3122])
        scope_source.pop("audioScope", None)
        button = {"apexScopeSource": scope_source}
        scoped = progress._scoped_target_key_from_button(button=button, label="System Macro")
        self.assertEqual(scoped, "tt2:2:ROOM:12:74:14:macro:3122:System Macro")

    def test_global_controller_button_unaffected(self) -> None:
        """A non-hard, global-scope button still emits the GLOBAL tt2 key."""
        button = {
            "apexScopeSource": _apex_scope_source(
                page_room_id=0, layer_room_id=0, button_tag_id=14, macro_ids=[3122],
                audio_scope=None,
            )
        }
        scoped = progress._scoped_target_key_from_button(button=button, label="System Macro")
        self.assertEqual(scoped, "tt2:2:GLOBAL:0:74:14:macro:3122:System Macro")


class CollapsedKeyValidationTest(unittest.TestCase):
    """Defensive guards on the audioScope dict shape."""

    def test_audio_scope_missing_wrapper_device_id_falls_back_to_normal_key(self) -> None:
        button = {
            "apexScopeSource": _apex_scope_source(
                button_tag_id=14, macro_ids=[3122],
                audio_scope={"roomId": 12},  # malformed
            )
        }
        scoped = progress._scoped_target_key_from_button(button=button, label="System Macro")
        self.assertEqual(scoped, "tt2:2:ROOM:12:74:14:macro:3122:System Macro")

    def test_audio_scope_non_dict_falls_back_to_normal_key(self) -> None:
        scope_source = _apex_scope_source(button_tag_id=14, macro_ids=[3122])
        scope_source["audioScope"] = "not-a-dict"
        button = {"apexScopeSource": scope_source}
        scoped = progress._scoped_target_key_from_button(button=button, label="System Macro")
        self.assertEqual(scoped, "tt2:2:ROOM:12:74:14:macro:3122:System Macro")


if __name__ == "__main__":
    unittest.main()
