"""Smoke tests that run on every OS against the real backend.

CI runners are headless, so they only check that the platform backend imports and answers
with a sane value, not that it matches a real desktop setting.
"""

import subprocess
import sys

import darkdetect


def _theme() -> str | None:
    """Widen the platform-specific return type, which pyright narrows per OS."""
    return darkdetect.theme()


def test_theme_is_a_known_value() -> None:
    assert darkdetect.theme() in {"Dark", "Light", None}


def test_is_dark_and_is_light_agree_with_theme() -> None:
    match _theme():
        case None:
            assert darkdetect.isDark() is None
            assert darkdetect.isLight() is None
        case "Dark":
            assert darkdetect.isDark() is True
            assert darkdetect.isLight() is False
        case _:
            assert darkdetect.isDark() is False
            assert darkdetect.isLight() is True


def test_module_entry_point_prints_theme() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "darkdetect"], capture_output=True, text=True, check=True
    )
    assert result.stdout.startswith("Current theme: ")
