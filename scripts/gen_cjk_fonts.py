#!/usr/bin/env python3
"""
Generate CJK-capable UI font files for the Chinese (ZH) locale.

This script:
1. Reads lib/I18n/translations/chinese.yaml to extract every unique non-ASCII
   character used in the UI strings.
2. Converts each character to an --additional-intervals argument for fontconvert.py.
3. Generates ubuntu_10/12 font variants (as font stacks: Ubuntu + NotoSansSC)
   that contain both Latin glyphs and the exact CJK subset needed for the UI.

Usage (run from project root):
    python scripts/gen_cjk_fonts.py [--noto-sc-path <path/to/NotoSansSC-Regular.ttf>]

Prerequisites:
    pip install freetype-py fonttools
    Download Noto Sans SC from https://fonts.google.com/noto/specimen/Noto+Sans+SC
    Place NotoSansSC-Regular.ttf / NotoSansSC-Bold.ttf in:
        lib/EpdFont/builtinFonts/source/NotoSansSC/

Output files (replacing the Latin-only versions):
    lib/EpdFont/builtinFonts/ubuntu_10_regular.h
    lib/EpdFont/builtinFonts/ubuntu_10_bold.h
    lib/EpdFont/builtinFonts/ubuntu_12_regular.h
    lib/EpdFont/builtinFonts/ubuntu_12_bold.h
    lib/EpdFont/builtinFonts/notosans_8_regular.h  (for SMALL_FONT_ID)
"""

import re
import subprocess
import sys
import os
from pathlib import Path


TRANSLATIONS_FILE = "lib/I18n/translations/chinese.yaml"
FONT_SCRIPTS_DIR = "lib/EpdFont/scripts"
UBUNTU_DIR = "lib/EpdFont/builtinFonts/source/Ubuntu"
NOTO_SC_DIR = "lib/EpdFont/builtinFonts/source/NotoSansSC"
NOTO_SANS_DIR = "lib/EpdFont/builtinFonts/source/NotoSans"
NOTO_SERIF_DIR = "lib/EpdFont/builtinFonts/source/NotoSerif"
OUTPUT_DIR = "lib/EpdFont/builtinFonts"


def parse_yaml(path: str) -> dict:
    result = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip()
            m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*"(.*)"$', line)
            if m:
                result[m.group(1)] = m.group(2)
    return result


def extract_non_ascii_chars(yaml_path: str) -> list:
    """Extract sorted unique non-ASCII codepoints from the translation file."""
    data = parse_yaml(yaml_path)
    codepoints = set()
    for key, value in data.items():
        if key.startswith("_"):
            continue
        for ch in value:
            cp = ord(ch)
            if cp > 0x007F:
                codepoints.add(cp)
    return sorted(codepoints)


def build_additional_intervals(codepoints: list) -> list:
    """Convert individual codepoints into contiguous ranges for --additional-intervals."""
    if not codepoints:
        return []
    ranges = []
    start = codepoints[0]
    end = codepoints[0]
    for cp in codepoints[1:]:
        if cp == end + 1:
            end = cp
        else:
            ranges.append((start, end))
            start = cp
            end = cp
    ranges.append((start, end))
    return [f"0x{s:04X},0x{e:04X}" for s, e in ranges]


def run_fontconvert(font_name: str, size: int, primary_font: str, fallback_font: str,
                    output_path: str, extra_intervals: list, compress: bool = False,
                    two_bit: bool = False) -> bool:
    """Run fontconvert.py with primary + fallback font stack and CJK intervals."""
    script = os.path.join(FONT_SCRIPTS_DIR, "fontconvert.py")
    cmd = [sys.executable, script, font_name, str(size), primary_font, fallback_font]
    if two_bit:
        cmd.append("--2bit")
    if compress:
        cmd.append("--compress")
    for interval in extra_intervals:
        cmd += ["--additional-intervals", interval]

    print(f"  Generating {os.path.basename(output_path)} ...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(result.stdout)
        if result.stderr:
            print(f"    (warnings: {result.stderr.strip()[:200]})")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ERROR generating {font_name}: {e.stderr[:400]}")
        return False
    except FileNotFoundError as e:
        print(f"  ERROR: {e}")
        return False


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Generate CJK-capable UI fonts for CrossPoint")
    parser.add_argument("--noto-sc-path", default=None,
                        help="Path to NotoSansSC directory (default: lib/EpdFont/builtinFonts/source/NotoSansSC)")
    args = parser.parse_args()

    noto_sc_dir = args.noto_sc_path or NOTO_SC_DIR

    print("=== CrossPoint CJK Font Generator ===")
    print()

    # Check source files exist
    ubuntu_regular = os.path.join(UBUNTU_DIR, "Ubuntu-Regular.ttf")
    ubuntu_bold = os.path.join(UBUNTU_DIR, "Ubuntu-Bold.ttf")
    notosans_regular = os.path.join(NOTO_SANS_DIR, "NotoSans-Regular.ttf")
    notosans_bold = os.path.join(NOTO_SANS_DIR, "NotoSans-Bold.ttf")
    notoserif_regular = os.path.join(NOTO_SERIF_DIR, "NotoSerif-Regular.ttf")
    notoserif_bold = os.path.join(NOTO_SERIF_DIR, "NotoSerif-Bold.ttf")
    # Accept both .ttf and .otf (release zip ships .otf)
    noto_sc_regular = os.path.join(noto_sc_dir, "NotoSansSC-Regular.ttf")
    if not os.path.exists(noto_sc_regular):
        noto_sc_regular = os.path.join(noto_sc_dir, "NotoSansSC-Regular.otf")
    noto_sc_bold = os.path.join(noto_sc_dir, "NotoSansSC-Bold.ttf")
    if not os.path.exists(noto_sc_bold):
        noto_sc_bold = os.path.join(noto_sc_dir, "NotoSansSC-Bold.otf")

    missing = []
    for path in [ubuntu_regular, ubuntu_bold, notosans_regular, notosans_bold,
                 notoserif_regular, notoserif_bold]:
        if not os.path.exists(path):
            missing.append(path)
    for path in [noto_sc_regular, noto_sc_bold]:
        if not os.path.exists(path):
            missing.append(path)

    if missing:
        print("Missing font files:")
        for p in missing:
            print(f"  {p}")
        print()
        if any("NotoSansSC" in p for p in missing):
            print("Download Noto Sans SC from:")
            print("  https://fonts.google.com/noto/specimen/Noto+Sans+SC")
            print(f"  Place Regular and Bold .ttf files in: {noto_sc_dir}/")
        return 1

    # Extract CJK character set
    print(f"Reading translations: {TRANSLATIONS_FILE}")
    codepoints = extract_non_ascii_chars(TRANSLATIONS_FILE)
    cjk_count = sum(1 for cp in codepoints if 0x4E00 <= cp <= 0x9FFF)
    print(f"Found {len(codepoints)} unique non-ASCII chars ({cjk_count} CJK ideographs)")
    extra_intervals = build_additional_intervals(codepoints)
    print(f"Merged into {len(extra_intervals)} Unicode intervals")
    print()

    # UI fonts (Ubuntu + NotoSansSC fallback) — file browser and menus
    ui_fonts = [
        ("ubuntu_10_regular", 10, ubuntu_regular, noto_sc_regular),
        ("ubuntu_10_bold",    10, ubuntu_bold,    noto_sc_bold),
        ("ubuntu_12_regular", 12, ubuntu_regular, noto_sc_regular),
        ("ubuntu_12_bold",    12, ubuntu_bold,    noto_sc_bold),
        # SMALL_FONT for status bar / path display
        ("notosans_8_regular", 8, notosans_regular, noto_sc_regular),
    ]

    # Reader body fonts (NotoSerif and NotoSans, regular + bold only, all sizes)
    # Italic/bolditalic variants are omitted; EpdFontFamily falls back to regular/bold.
    body_fonts = [
        ("notoserif_12_regular", 12, notoserif_regular, noto_sc_regular),
        ("notoserif_12_bold",    12, notoserif_bold,    noto_sc_bold),
        ("notoserif_14_regular", 14, notoserif_regular, noto_sc_regular),
        ("notoserif_14_bold",    14, notoserif_bold,    noto_sc_bold),
        ("notoserif_16_regular", 16, notoserif_regular, noto_sc_regular),
        ("notoserif_16_bold",    16, notoserif_bold,    noto_sc_bold),
        ("notoserif_18_regular", 18, notoserif_regular, noto_sc_regular),
        ("notoserif_18_bold",    18, notoserif_bold,    noto_sc_bold),
        ("notosans_12_regular",  12, notosans_regular,  noto_sc_regular),
        ("notosans_12_bold",     12, notosans_bold,     noto_sc_bold),
        ("notosans_14_regular",  14, notosans_regular,  noto_sc_regular),
        ("notosans_14_bold",     14, notosans_bold,     noto_sc_bold),
        ("notosans_16_regular",  16, notosans_regular,  noto_sc_regular),
        ("notosans_16_bold",     16, notosans_bold,     noto_sc_bold),
        ("notosans_18_regular",  18, notosans_regular,  noto_sc_regular),
        ("notosans_18_bold",     18, notosans_bold,     noto_sc_bold),
    ]

    all_fonts = ui_fonts + body_fonts
    success = 0

    print("--- UI fonts ---")
    for font_name, size, primary, fallback in ui_fonts:
        out = os.path.join(OUTPUT_DIR, f"{font_name}.h")
        ok = run_fontconvert(font_name, size, primary, fallback, out, extra_intervals)
        if ok:
            success += 1

    print()
    print("--- Reader body fonts (NotoSerif + NotoSans regular/bold with CJK) ---")
    for font_name, size, primary, fallback in body_fonts:
        out = os.path.join(OUTPUT_DIR, f"{font_name}.h")
        ok = run_fontconvert(font_name, size, primary, fallback, out, extra_intervals)
        if ok:
            success += 1

    print()
    if success == len(all_fonts):
        print(f"Done! {success}/{len(all_fonts)} font files regenerated with CJK support.")
        print()
        print("Next steps:")
        print("  1. Run: pio run -e gh_release   (to rebuild firmware)")
        print("  2. Flash to device, set language to 中文 in Settings > Language")
    else:
        print(f"WARNING: only {success}/{len(all_fonts)} fonts generated successfully.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
