"""Auditable V1-to-V2 service rules used by the game compatibility stage."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ServiceRule:
    action: str
    target: int | None


DIRECT_OFFSETS = {
    "FS": {0x000, 0x004, 0x008, 0x00C, 0x010, 0x014, 0x024, 0x02C, 0x030, 0x048},
    "MEM": {0x008, 0x00C},
    "SYS": {0x040, 0x044, 0x050, 0x054, 0x058, 0x05C, 0x060, 0x064, 0x068},
}

GUI_RELOCATIONS = {
    0x2B8: 0x2B0,
    0x300: 0x2F8,
    0x3F8: 0x3F0,
    0x400: 0x3F8,
    0x6E0: 0x9E4,
    0x72C: 0x688,
    0xA38: 0x924,
    0xA70: 0x938,
    0xA7C: 0x6A4,
    0xA80: 0x6A8,
    0xA84: 0x940,
    0xA88: 0x944,
    0xA8C: 0x948,
    0xA90: 0x94C,
    0xAD8: 0x95C,
    0xADC: 0x960,
}

GUI_SHIMS = {
    0x6A8: "game_mode_allow",
    0x6E4: "license_scope_begin",
    0x6E8: "license_scope_end",
    0x6F4: "debug_return_zero",
    0x6FC: "rtc_ticks_shadow",
    0x700: "rtc_flag_shadow",
    0xAA4: "allow_without_coins",
    0xAA8: "allow_without_coins",
}


def classify_service(table: str, offset: int) -> ServiceRule | None:
    if offset in DIRECT_OFFSETS.get(table, set()):
        return ServiceRule("direct", offset)
    if table == "GUI":
        if offset == 0x84C:
            return ServiceRule("shim_state_bridge", 0x738)
        if offset in GUI_RELOCATIONS:
            return ServiceRule("relocate", GUI_RELOCATIONS[offset])
        if 0x850 <= offset <= 0x9F8 and offset % 4 == 0:
            return ServiceRule("relocate", offset - 0x114)
        if offset in GUI_SHIMS:
            return ServiceRule("shim_" + GUI_SHIMS[offset], None)
    if table == "RES" and offset == 0x094:
        return ServiceRule("shim_return_zero", None)
    if table == "SYS" and offset in {0x08C, 0x090}:
        return ServiceRule("shim_legacy_handle", None)
    return None
