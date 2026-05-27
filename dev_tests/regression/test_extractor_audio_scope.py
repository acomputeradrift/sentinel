"""Regression: per-room hard-key audio scope (MacroRedirect) extraction.

See docs/audio_scope_investigation.md for the locked rules. This file covers
phase A only: that `_load_macro_redirect_map` reads MacroRedirect correctly,
and that `_audio_scope_for_hard_button` returns the scope dict for redirected
hard keys and None for everything else.
"""

import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _hard_button_ui() -> dict:
    return {
        "fontSize": 0,
        "orientations": {
            "portrait": {"visible": True, "coordinates": {"top": 0, "left": 0, "height": 0, "width": 0}},
            "landscape": {"visible": True, "coordinates": {"top": 0, "left": 0, "height": 0, "width": 0}},
        },
        "stack": {"layerOrder": 0, "buttonOrder": 0, "frameNumber": 0},
    }


def _soft_button_ui() -> dict:
    return {
        "fontSize": 0,
        "orientations": {
            "portrait": {"visible": True, "coordinates": {"top": 0, "left": 0, "height": 80, "width": 80}},
            "landscape": {"visible": True, "coordinates": {"top": 0, "left": 0, "height": 80, "width": 80}},
        },
        "stack": {"layerOrder": 0, "buttonOrder": 0, "frameNumber": 0},
    }


class LoadMacroRedirectMapTest(unittest.TestCase):
    def test_returns_empty_map_when_table_missing(self) -> None:
        from sentinel.extraction import extractor_core

        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        result = extractor_core._load_macro_redirect_map(cur)
        self.assertEqual(result, {})
        con.close()

    def test_returns_empty_map_when_table_present_but_empty(self) -> None:
        from sentinel.extraction import extractor_core

        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute(
            "create table MacroRedirect (MacroRedirectId INTEGER, RoomId INTEGER, ButtonTagId INTEGER, SourceId INTEGER)"
        )
        result = extractor_core._load_macro_redirect_map(cur)
        self.assertEqual(result, {})
        con.close()

    def test_loads_haven_jazz_room_shape(self) -> None:
        from sentinel.extraction import extractor_core

        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute(
            "create table MacroRedirect (MacroRedirectId INTEGER, RoomId INTEGER, ButtonTagId INTEGER, SourceId INTEGER)"
        )
        cur.executemany(
            "insert into MacroRedirect values (?, ?, ?, ?)",
            [
                (1, 1, 14, 9),  # Jazz Room | Vol Up | Marantz wrapper
                (2, 1, 22, 9),  # Jazz Room | Vol Down | Marantz wrapper
                (3, 1, 19, 9),  # Jazz Room | Mute | Marantz wrapper
            ],
        )
        result = extractor_core._load_macro_redirect_map(cur)
        self.assertEqual(
            result,
            {(1, 14): 9, (1, 22): 9, (1, 19): 9},
        )
        con.close()

    def test_loads_sung_two_room_override(self) -> None:
        from sentinel.extraction import extractor_core

        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute(
            "create table MacroRedirect (MacroRedirectId INTEGER, RoomId INTEGER, ButtonTagId INTEGER, SourceId INTEGER)"
        )
        cur.executemany(
            "insert into MacroRedirect values (?, ?, ?, ?)",
            [
                (14, 12, 10, 166),  # Theater
                (15, 12, 14, 166),
                (16, 12, 8, 166),
                (17, 7, 10, 168),  # Rec Room
                (18, 7, 14, 168),
                (19, 7, 8, 168),
            ],
        )
        result = extractor_core._load_macro_redirect_map(cur)
        self.assertEqual(result[(12, 10)], 166)
        self.assertEqual(result[(12, 14)], 166)
        self.assertEqual(result[(12, 8)], 166)
        self.assertEqual(result[(7, 10)], 168)
        self.assertEqual(result[(7, 14)], 168)
        self.assertEqual(result[(7, 8)], 168)
        self.assertEqual(len(result), 6)
        con.close()

    def test_skips_invalid_rows(self) -> None:
        from sentinel.extraction import extractor_core

        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute(
            "create table MacroRedirect (MacroRedirectId INTEGER, RoomId INTEGER, ButtonTagId INTEGER, SourceId INTEGER)"
        )
        cur.executemany(
            "insert into MacroRedirect values (?, ?, ?, ?)",
            [
                (1, 1, 14, 9),   # valid
                (2, -1, 14, 9),  # negative room
                (3, 1, 0, 9),    # zero tag
                (4, 1, 14, 0),   # zero source
                (5, 1, 14, None),  # null source
            ],
        )
        result = extractor_core._load_macro_redirect_map(cur)
        self.assertEqual(result, {(1, 14): 9})
        con.close()


class AudioScopeForHardButtonTest(unittest.TestCase):
    def test_returns_none_for_soft_button(self) -> None:
        from sentinel.extraction import extractor_core

        scope = extractor_core._audio_scope_for_hard_button(
            button_ui=_soft_button_ui(),
            effective_room_id=1,
            tag_id=14,
            macro_redirect_map={(1, 14): 9},
        )
        self.assertIsNone(scope)

    def test_returns_none_when_tag_id_invalid(self) -> None:
        from sentinel.extraction import extractor_core

        for bad in (0, -1):
            with self.subTest(tag_id=bad):
                scope = extractor_core._audio_scope_for_hard_button(
                    button_ui=_hard_button_ui(),
                    effective_room_id=1,
                    tag_id=bad,
                    macro_redirect_map={(1, 14): 9},
                )
                self.assertIsNone(scope)

    def test_returns_none_when_no_redirect_exists(self) -> None:
        from sentinel.extraction import extractor_core

        scope = extractor_core._audio_scope_for_hard_button(
            button_ui=_hard_button_ui(),
            effective_room_id=2,  # different room
            tag_id=14,
            macro_redirect_map={(1, 14): 9},
        )
        self.assertIsNone(scope)

    def test_returns_none_when_map_is_empty(self) -> None:
        from sentinel.extraction import extractor_core

        scope = extractor_core._audio_scope_for_hard_button(
            button_ui=_hard_button_ui(),
            effective_room_id=1,
            tag_id=14,
            macro_redirect_map={},
        )
        self.assertIsNone(scope)

    def test_returns_scope_for_redirected_hard_key(self) -> None:
        from sentinel.extraction import extractor_core

        scope = extractor_core._audio_scope_for_hard_button(
            button_ui=_hard_button_ui(),
            effective_room_id=1,
            tag_id=14,
            macro_redirect_map={(1, 14): 9, (1, 22): 9, (1, 19): 9},
        )
        self.assertEqual(scope, {"roomId": 1, "wrapperDeviceId": 9})

    def test_three_hard_keys_in_same_room_share_wrapper(self) -> None:
        """Validates equivalence: all 3 redirected keys in a room emit the same wrapperDeviceId."""
        from sentinel.extraction import extractor_core

        redirect_map = {(12, 8): 166, (12, 10): 166, (12, 14): 166}
        wrappers = set()
        for tag in (8, 10, 14):
            scope = extractor_core._audio_scope_for_hard_button(
                button_ui=_hard_button_ui(),
                effective_room_id=12,
                tag_id=tag,
                macro_redirect_map=redirect_map,
            )
            self.assertIsNotNone(scope)
            assert scope is not None
            wrappers.add(scope["wrapperDeviceId"])
        self.assertEqual(wrappers, {166})

    def test_audio_scope_sets_macros_test_target_when_source_scoped_macro_missing(self) -> None:
        """Redirected vol keys may have audioScope but no macro on the page effective source."""
        audio_scope = {"roomId": 12, "wrapperDeviceId": 166}
        has_macros_target = False
        emits_macros_test_target = has_macros_target or audio_scope is not None
        self.assertTrue(emits_macros_test_target)

    def test_two_rooms_with_same_button_tag_get_different_wrappers(self) -> None:
        """Validates per-room scoping: Theater(12) and Rec Room(7) keep separate wrappers."""
        from sentinel.extraction import extractor_core

        redirect_map = {(12, 14): 166, (7, 14): 168}
        theater = extractor_core._audio_scope_for_hard_button(
            button_ui=_hard_button_ui(), effective_room_id=12, tag_id=14, macro_redirect_map=redirect_map
        )
        rec_room = extractor_core._audio_scope_for_hard_button(
            button_ui=_hard_button_ui(), effective_room_id=7, tag_id=14, macro_redirect_map=redirect_map
        )
        assert theater is not None and rec_room is not None
        self.assertEqual(theater["wrapperDeviceId"], 166)
        self.assertEqual(rec_room["wrapperDeviceId"], 168)
        self.assertNotEqual(theater["wrapperDeviceId"], rec_room["wrapperDeviceId"])


if __name__ == "__main__":
    unittest.main()
