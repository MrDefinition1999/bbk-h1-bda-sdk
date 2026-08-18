from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = ROOT / "examples" / "v2" / "v1_game_compat_rules.py"


def load_rules():
    spec = importlib.util.spec_from_file_location("h1_v2_game_compat_rules", RULES_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_confirmed_non_linear_gui_mappings() -> None:
    rules = load_rules()
    assert rules.classify_service("GUI", 0x6E0).target == 0x9E4
    assert rules.classify_service("GUI", 0x72C).target == 0x688
    assert rules.classify_service("GUI", 0xA38).target == 0x924
    assert rules.classify_service("GUI", 0xA70).target == 0x938


def test_graphics_rebase_and_policy_shims() -> None:
    rules = load_rules()
    init_rule = rules.classify_service("GUI", 0x84C)
    assert init_rule.action == "shim_state_bridge"
    assert init_rule.target == 0x738
    assert rules.classify_service("GUI", 0x9F8).target == 0x8E4
    assert rules.classify_service("GUI", 0xAA4).action == "shim_allow_without_coins"
    assert rules.classify_service("GUI", 0xAA8).action == "shim_allow_without_coins"
    assert rules.classify_service("GUI", 0xAA4).target is None
    assert rules.classify_service("GUI", 0xAA8).target is None
    assert rules.classify_service("RES", 0x094).action == "shim_return_zero"


def test_unknown_service_is_rejected() -> None:
    rules = load_rules()
    assert rules.classify_service("GUI", 0xABC) is None
    assert rules.classify_service("SYS", 0x000) is None
