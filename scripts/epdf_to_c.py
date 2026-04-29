#!/usr/bin/env python3
"""Convert .epdf binary files to C array headers for firmware embedding."""
import sys
import os


def epdf_to_c(input_path: str, output_path: str, array_name: str) -> None:
    with open(input_path, "rb") as f:
        data = f.read()

    lines = [
        "// Auto-generated — do not edit. Regenerate with scripts/epdf_to_c.py",
        f"// Source: {os.path.basename(input_path)}  ({len(data)} bytes)",
        "#pragma once",
        "#include <cstdint>",
        f"static const uint8_t {array_name}[] = {{",
    ]

    for i in range(0, len(data), 16):
        chunk = data[i:i + 16]
        hex_vals = ", ".join(f"0x{b:02x}" for b in chunk)
        lines.append(f"  {hex_vals},")

    lines.append("};")
    lines.append(f"static const size_t {array_name}_size = {len(data)};")
    lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"  {output_path}: {len(data)} bytes → {len(lines)} lines")


if __name__ == "__main__":
    base = os.path.join(os.path.dirname(__file__), "..")
    cjk_dir = os.path.join(base, "lib", "EpdFont", "builtinFonts", "cjk_data")

    conversions = [
        ("reader_cjk.epdf", "reader_cjk_flash.h", "READER_CJK_FLASH"),
        ("ui_cjk.epdf",     "ui_cjk_flash.h",     "UI_CJK_FLASH"),
    ]

    print("=== EPDF → C array conversion ===")
    for epdf_name, h_name, array_name in conversions:
        epdf_path = os.path.join(cjk_dir, epdf_name)
        h_path    = os.path.join(cjk_dir, h_name)
        if not os.path.exists(epdf_path):
            print(f"  ERROR: {epdf_path} not found — run make_sd_font.py first")
            sys.exit(1)
        epdf_to_c(epdf_path, h_path, array_name)

    print("Done.")
