#!/usr/bin/env python3
"""
Generate .epdf (EPDF v1) CJK font files for CrossPoint SD-card streaming.

Two files are produced:
  /.crosspoint/reader_cjk.epdf  — 14 pt, for EPUB reader body text
  /.crosspoint/ui_cjk.epdf     — 12 pt, for file-browser filenames

Copy both files to the /.crosspoint/ folder on your SD card.
CrossPoint will auto-detect them at startup.

Prerequisites:
    pip install freetype-py
    NotoSansSC-Regular.otf in lib/EpdFont/builtinFonts/source/NotoSansSC/

Usage (run from project root):
    python scripts/make_sd_font.py [--max-chars N] [--out-dir DIR]
"""

import struct
import sys
import os
import argparse

NOTO_SC_DIR = "lib/EpdFont/builtinFonts/source/NotoSansSC"
DEFAULT_MAX_CHARS = 3500   # GB2312 level-1 sized coverage

# Unicode ranges included in the EPDF font files
# (characters outside these ranges are never queried via SdFont)
CJK_RANGES = [
    (0x3001, 0x3002),   # 、。 — CJK ideographic comma/period
    (0x3008, 0x3011),   # 〈〉《》「」『』【】
    (0x3014, 0x3015),   # 〔〕
    (0xFF01, 0xFF5E),   # ！…～ fullwidth punctuation
    (0x4E00, 0x9FFF),   # CJK Unified Ideographs (main block)
    (0xF900, 0xFAFF),   # CJK Compatibility Ideographs
]

# Fixed-point helpers matching EpdFont conventions
# advanceX is stored as 12.4 fixed-point (uint16_t)
# freetype advance is 26.6 fixed-point → shift right 2 to get 12.4
def ft_adv_to_fp4(ft_adv_x: int) -> int:
    """Convert freetype 26.6 advance to EpdFont 12.4 fixed-point, clamped to uint16."""
    fp4 = (ft_adv_x + 2) >> 2   # round
    return min(fp4, 0xFFFF)


def collect_codepoints(font_path: str, max_chars: int) -> list:
    """Return sorted list of CJK codepoints present in the font, up to max_chars.
    Uses freetype to probe each codepoint — no fonttools required."""
    import freetype

    face = freetype.Face(font_path)
    face.set_char_size(14 << 6, 14 << 6, 150, 150)  # any size; we only probe the cmap

    all_cp = []
    for lo, hi in CJK_RANGES:
        for cp in range(lo, hi + 1):
            # get_char_index returns 0 if the glyph is not in the font's cmap
            if face.get_char_index(cp) != 0:
                all_cp.append(cp)

    all_cp.sort()
    if len(all_cp) > max_chars:
        all_cp = all_cp[:max_chars]

    return all_cp


def rasterize_glyph(face, cp: int):
    """
    Rasterize a single codepoint with freetype and return
    (packed_1bit_bytes, width, height, advanceX_fp4, left, top)
    or None if the glyph is empty / not renderable.
    """
    import freetype
    try:
        face.load_char(cp, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_TARGET_MONO)
    except Exception:
        return None

    bm = face.glyph.bitmap
    w, h = bm.width, bm.rows
    if w == 0 or h == 0:
        return None

    pitch = bm.pitch  # bytes per row in freetype mono bitmap
    ft_buf = bytes(bm.buffer)

    # Repack: strip row-alignment padding, produce tightly-packed 1-bit stream
    packed = bytearray()
    cur_byte = 0
    bit_count = 0
    for row in range(h):
        for col in range(w):
            byte_idx = row * pitch + col // 8
            bit_idx = 7 - (col % 8)
            bit = (ft_buf[byte_idx] >> bit_idx) & 1
            cur_byte = (cur_byte << 1) | bit
            bit_count += 1
            if bit_count == 8:
                packed.append(cur_byte)
                cur_byte = 0
                bit_count = 0
    if bit_count > 0:
        packed.append(cur_byte << (8 - bit_count))

    adv_fp4 = ft_adv_to_fp4(face.glyph.advance.x)
    left = face.glyph.bitmap_left
    top = face.glyph.bitmap_top
    return (bytes(packed), w, h, adv_fp4, left, top)


def make_epdf(font_path: str, output_path: str, size_pt: int, codepoints: list) -> bool:
    """Generate a single .epdf file."""
    import freetype

    face = freetype.Face(font_path)
    # Match fontconvert.py exactly: size << 6, 150 DPI
    face.set_char_size(size_pt << 6, size_pt << 6, 150, 150)

    index_entries = []
    bitmap_section = bytearray()
    # Bitmap section starts right after header + index
    bitmaps_start = 32 + len(codepoints) * 16
    max_glyph_bytes = 0

    print(f"  Rasterizing {len(codepoints)} codepoints at {size_pt}pt...")
    skipped = 0
    for cp in codepoints:
        result = rasterize_glyph(face, cp)
        if result is None:
            skipped += 1
            continue
        glyph_bytes, w, h, adv, left, top = result
        file_off = bitmaps_start + len(bitmap_section)
        index_entries.append((cp, file_off, w, h, adv, left, top))
        bitmap_section.extend(glyph_bytes)
        max_glyph_bytes = max(max_glyph_bytes, len(glyph_bytes))

    if not index_entries:
        print(f"  ERROR: no glyphs rasterized")
        return False

    count = len(index_entries)
    if skipped:
        print(f"  Skipped {skipped} empty/missing glyphs")

    # Font line metrics (from freetype face.size, in 26.6 → pixels)
    advance_y = max(1, face.size.height   >> 6) if face.size.height   > 0 else size_pt
    ascender  = face.size.ascender  >> 6
    descender = face.size.descender >> 6       # typically negative

    # Clamp to int16 range
    ascender  = max(-32768, min(32767, ascender))
    descender = max(-32768, min(32767, descender))
    advance_y = min(255, advance_y)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    with open(output_path, "wb") as f:
        # Header: 4+1+2+1+2+2+2+18 = 32 bytes
        hdr = struct.pack(
            "<4sBHBhhH18s",
            b"EPDF",
            1,                            # version
            count,                        # glyph count (uint16)
            advance_y,                    # advanceY (uint8)
            ascender,                     # ascender (int16)
            descender,                    # descender (int16, negative)
            min(max_glyph_bytes, 0xFFFF), # maxGlyphBytes (uint16)
            b"\x00" * 18,
        )
        assert len(hdr) == 32, f"Header size is {len(hdr)}"
        f.write(hdr)

        # Index: 16 bytes per glyph  (I I B B H h h) = 4+4+1+1+2+2+2 = 16
        for cp, file_off, w, h, adv, left, top in index_entries:
            entry = struct.pack("<IIBBHhh", cp, file_off, w, h, adv, left, top)
            assert len(entry) == 16
            f.write(entry)

        # Bitmaps
        f.write(bitmap_section)

    file_size = os.path.getsize(output_path)
    print(f"  {output_path}: {count} glyphs, max {max_glyph_bytes}B/glyph, "
          f"advY={advance_y} asc={ascender} desc={descender}, "
          f"file={file_size // 1024}KB")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate CJK .epdf font files for CrossPoint SD card")
    parser.add_argument("--noto-sc-path", default=None,
                        help="Path to NotoSansSC directory")
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS,
                        help=f"Maximum CJK codepoints per file (default {DEFAULT_MAX_CHARS})")
    parser.add_argument("--out-dir", default="/.crosspoint",
                        help="Output directory on SD card (default: /.crosspoint)")
    args = parser.parse_args()

    noto_sc_dir = args.noto_sc_path or NOTO_SC_DIR
    font_path_ttf = os.path.join(noto_sc_dir, "NotoSansSC-Regular.ttf")
    font_path_otf = os.path.join(noto_sc_dir, "NotoSansSC-Regular.otf")
    font_path = font_path_ttf if os.path.exists(font_path_ttf) else font_path_otf

    if not os.path.exists(font_path):
        print(f"ERROR: NotoSansSC-Regular.ttf/.otf not found in {noto_sc_dir}")
        print("Download from https://fonts.google.com/noto/specimen/Noto+Sans+SC")
        return 1

    try:
        import freetype
    except ImportError:
        print("ERROR: freetype-py not installed. Run: pip install freetype-py")
        return 1

    print("=== CrossPoint CJK SD Font Generator ===")
    print(f"Font:      {font_path}")
    print(f"Max chars: {args.max_chars}")
    print()

    print("Scanning font for available CJK codepoints...")
    codepoints = collect_codepoints(font_path, args.max_chars)
    if not codepoints:
        print("ERROR: No CJK codepoints found in font")
        return 1
    print(f"Found {len(codepoints)} CJK codepoints to include")
    print()

    out_dir = args.out_dir
    reader_path = os.path.join(out_dir, "reader_cjk.epdf")
    ui_path     = os.path.join(out_dir, "ui_cjk.epdf")

    print("--- Generating reader_cjk.epdf (14pt, for EPUB reader) ---")
    ok1 = make_epdf(font_path, reader_path, 14, codepoints)

    print()
    print("--- Generating ui_cjk.epdf (12pt, for file browser) ---")
    ok2 = make_epdf(font_path, ui_path, 12, codepoints)

    print()
    if ok1 and ok2:
        print("Done! Copy both files to /.crosspoint/ on your SD card:")
        print(f"  {reader_path}")
        print(f"  {ui_path}")
        print()
        print("CrossPoint will load them automatically at startup.")
        return 0
    else:
        print("WARNING: one or more files failed to generate.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
