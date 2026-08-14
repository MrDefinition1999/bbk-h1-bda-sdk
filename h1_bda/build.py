from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Sequence

from .header import HeaderFields, encode_header
from .resources import (
    PAYLOAD_OFFSET,
    RESOURCE_OFFSET,
    RESOURCE_SIZES,
    build_diagnostic_resources,
    build_icon_resources,
)
from .validate import validate_bda


ENTRY_VA = 0x83C00020
PROJECT_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_INCLUDE = PROJECT_ROOT / "sdk" / "include"
RESEARCH_INCLUDE = PROJECT_ROOT / "reverse" / "include"


def _path_privacy_flags(work: Path) -> list[str]:
    mappings: list[tuple[Path, str]] = [
        (Path.home(), "user-home"),
        (PROJECT_ROOT, "h1-sdk"),
        (work, "build"),
    ]
    flags = ["-g0"]
    seen: set[str] = set()
    for source, target in mappings:
        resolved = str(source.resolve())
        for prefix in (resolved, resolved.replace("\\", "/")):
            if prefix in seen:
                continue
            seen.add(prefix)
            flags.extend(
                [
                    f"-ffile-prefix-map={prefix}={target}",
                    f"-fmacro-prefix-map={prefix}={target}",
                    f"-fdebug-prefix-map={prefix}={target}",
                ]
            )
    return flags


def _build_timestamp() -> str:
    source_date_epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if source_date_epoch is None:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        epoch = int(source_date_epoch)
        timestamp = datetime.fromtimestamp(epoch, timezone.utc)
    except (OverflowError, OSError, ValueError) as error:
        raise ValueError("SOURCE_DATE_EPOCH must be a valid Unix timestamp") from error
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")


def _find_llvm_tool(name: str) -> Path:
    configured = os.environ.get("H1_LLVM_BIN")
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured) / f"{name}.exe")
        candidates.append(Path(configured) / name)
    candidates.extend(
        [
            PROJECT_ROOT.parent
            / "work"
            / "rebuild"
            / "tools"
            / "msys2-20260611"
            / "msys64"
            / "ucrt64"
            / "bin"
            / f"{name}.exe",
            PROJECT_ROOT.parent
            / "work"
            / "tools"
            / "msys64"
            / "clangarm64"
            / "bin"
            / f"{name}.exe",
            Path("R:/clangarm64/bin") / f"{name}.exe",
            Path("R:/ucrt64/bin") / f"{name}.exe",
        ]
    )
    located = shutil.which(name) or shutil.which(f"{name}.exe")
    if located:
        candidates.append(Path(located))
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise SystemExit(
        f"cannot find {name}; set H1_LLVM_BIN to an LLVM bin directory with "
        "MIPS support"
    )


def _find_gnu_tool(name: str) -> Path:
    configured = os.environ.get("H1_GNU_BIN")
    if not configured:
        raise SystemExit("set H1_GNU_BIN to a MIPS little-endian GNU bin directory")
    root = Path(configured)
    candidates = [
        root / f"mipsel-none-elf-{name}.exe",
        root / f"mipsel-none-elf-{name}",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise SystemExit(f"cannot find mipsel-none-elf-{name} below H1_GNU_BIN")


def _find_binary_tool(llvm_name: str, gnu_name: str) -> Path:
    if os.environ.get("H1_GNU_BIN"):
        return _find_gnu_tool(gnu_name)
    return _find_llvm_tool(llvm_name)


def _run(command: list[str], label: str) -> None:
    completed = subprocess.run(command, check=False)
    if completed.returncode:
        raise SystemExit(f"{label} failed with exit code {completed.returncode}")


def compile_sources(
    sources: Sequence[Path],
    extra_includes: Sequence[Path],
    defines: Sequence[str] = (),
    compiler_flags: Sequence[str] = (),
    debug_elf: Path | None = None,
    noinit_address: int | None = None,
    entry_va: int = ENTRY_VA,
) -> bytes:
    if not sources:
        raise ValueError("at least one source file is required")
    use_gnu = bool(os.environ.get("H1_GNU_BIN"))
    if use_gnu:
        compiler = _find_gnu_tool("gcc")
        linker_tool = _find_gnu_tool("ld")
        objcopy = _find_gnu_tool("objcopy")
    else:
        compiler = _find_llvm_tool("clang")
        linker_tool = _find_llvm_tool("ld.lld")
        objcopy = _find_llvm_tool("llvm-objcopy")
    include_dirs = [*extra_includes, PUBLIC_INCLUDE, RESEARCH_INCLUDE]
    include_args = [item for path in include_dirs for item in ("-I", str(path))]
    define_args = [item for value in defines for item in ("-D", value)]

    with tempfile.TemporaryDirectory(prefix="h1-bda-") as temporary:
        work = Path(temporary)
        privacy_flags = _path_privacy_flags(work)
        linker = work / "h1-bda.ld"
        output_elf = work / "app.elf"
        output_bin = work / "app.bin"
        output_objects: list[Path] = []
        noinit_placement = ""
        if entry_va & 3:
            raise ValueError("entry address must be 4-byte aligned")
        if not 0x80000000 <= entry_va < 0x84000000:
            raise ValueError("entry address must be inside H1 cached SDRAM")
        if noinit_address is not None:
            if noinit_address < entry_va:
                raise ValueError("noinit address must not precede the BDA entry")
            noinit_placement = (
                f'  ASSERT(. <= 0x{noinit_address:08x}, '
                '"initialized H1 application overlaps fixed noinit address")\n'
                f'  . = 0x{noinit_address:08x};\n'
            )
        linker.write_text(
            f"""ENTRY(h1_bda_main)
SECTIONS
{{
  . = 0x{entry_va:08x};
  .text : {{ *(.text.h1_bda_entry) *(.text*) }}
  .rodata : {{ *(.rodata*) }}
  .data : {{ *(.data*) *(.sdata*) *(.bss*) *(COMMON) }}
  .got : {{ *(.got*) }}
{noinit_placement}
  . = ALIGN(16);
  .h1_noinit (NOLOAD) :
  {{
    __h1_noinit_start = .;
    *(.h1_noinit.a320_stack)
    *(.h1_noinit.a320_arena)
    *(.h1_noinit*)
    __h1_noinit_end = .;
  }}
  ASSERT(__h1_noinit_end <= 0x84000000, "H1 application exceeds 64 MiB SDRAM")
  /DISCARD/ : {{ *(.comment*) *(.note*) *(.MIPS.abiflags*) *(.reginfo*) }}
}}
""",
            encoding="ascii",
        )
        for index, source in enumerate(sources):
            output_object = work / f"{index:03d}-{source.stem}.o"
            target_args = (
                ["-EL", "-msoft-float"] if use_gnu else
                ["--target=mipsel-none-elf"]
            )
            selected_compiler_flags = list(compiler_flags)
            if use_gnu:
                selected_compiler_flags = [
                    flag for flag in selected_compiler_flags
                    if flag != "-Wno-incompatible-library-redeclaration"
                ]
            _run(
                [
                    str(compiler),
                    *target_args,
                    "-march=mips32",
                    "-mabi=32",
                    "-mno-abicalls",
                    "-fno-pic",
                    "-G0",
                    "-Os",
                    "-ffreestanding",
                    "-fno-builtin",
                    "-fno-stack-protector",
                    "-ffunction-sections",
                    "-fdata-sections",
                    *privacy_flags,
                    *include_args,
                    *define_args,
                    *selected_compiler_flags,
                    "-c",
                    str(source),
                    "-o",
                    str(output_object),
                ],
                f"MIPS compilation of {source}",
            )
            output_objects.append(output_object)
        _run(
            [
                str(linker_tool),
                "-m",
                "elf32elmip" if use_gnu else "elf32ltsmip",
                "-T",
                str(linker),
                "--build-id=none",
                "--gc-sections",
                *map(str, output_objects),
                "-o",
                str(output_elf),
            ],
            "MIPS linking",
        )
        _run(
            [str(objcopy), "-O", "binary", str(output_elf), str(output_bin)],
            "flat binary export",
        )
        if debug_elf is not None:
            debug_elf.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(output_elf, debug_elf)
        return output_bin.read_bytes()


def compile_source(source: Path, extra_includes: list[Path]) -> bytes:
    """Backward-compatible single-source build helper."""
    return compile_sources([source], extra_includes)


def build_bda(
    sources: Path | Sequence[Path],
    title: str,
    category: int,
    includes: Sequence[Path],
    defines: Sequence[str] = (),
    compiler_flags: Sequence[str] = (),
    debug_elf: Path | None = None,
    icon_png: Path | None = None,
    noinit_address: int | None = None,
    entry_va: int = ENTRY_VA,
) -> bytes:
    source_list = [sources] if isinstance(sources, Path) else list(sources)
    payload = compile_sources(
        source_list,
        includes,
        defines,
        compiler_flags,
        debug_elf,
        noinit_address,
        entry_va,
    )
    resources = (
        build_icon_resources(icon_png)
        if icon_png is not None
        else build_diagnostic_resources()
    )
    total_size = PAYLOAD_OFFSET + len(payload)
    padding = (-total_size) & 3
    fields = HeaderFields(
        category=category,
        file_size_minus_4=total_size + padding - 4,
        payload_offset=PAYLOAD_OFFSET,
        resource_offset=RESOURCE_OFFSET,
        resource_sizes=RESOURCE_SIZES,
    )
    header = encode_header(
        fields,
        title=title,
        build_time=_build_timestamp(),
    )
    return header + resources + payload + bytes(padding)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a standalone BBK H1 BDA")
    parser.add_argument("sources", nargs="+", type=Path)
    parser.add_argument("--title", required=True)
    parser.add_argument("--category", type=lambda value: int(value, 0), default=0x1E)
    parser.add_argument("-I", "--include", action="append", type=Path, default=[])
    parser.add_argument("-D", "--define", action="append", default=[])
    parser.add_argument(
        "--cflag",
        action="append",
        default=[],
        help="additional compiler flag; repeat for multiple flags",
    )
    parser.add_argument("-o", "--output", required=True, type=Path)
    parser.add_argument(
        "--icon-png",
        type=Path,
        help="RGBA PNG converted into all four H1 menu icon resources",
    )
    parser.add_argument(
        "--entry-va",
        type=lambda value: int(value, 0),
        default=ENTRY_VA,
        help="runtime link/entry address (default: 0x83c00020 for H1 V1)",
    )
    args = parser.parse_args()

    data = build_bda(
        args.sources,
        args.title,
        args.category,
        args.include,
        args.define,
        args.cflag,
        icon_png=args.icon_png,
        entry_va=args.entry_va,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    report = validate_bda(args.output)
    if not report["ok"]:
        args.output.unlink(missing_ok=True)
        raise SystemExit("built BDA failed validation: " + "; ".join(report["errors"]))
    print(f"output={args.output}")
    print(f"size=0x{len(data):x}")
    print(f"payload_offset=0x{PAYLOAD_OFFSET:x}")
    print(f"entry_va=0x{args.entry_va:08x}")


if __name__ == "__main__":
    main()
