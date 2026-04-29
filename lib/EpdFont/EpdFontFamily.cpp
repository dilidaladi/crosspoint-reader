#include "EpdFontFamily.h"

#include "SdFont.h"

const EpdFont* EpdFontFamily::getFont(const Style style) const {
  // Extract font style bits (ignore UNDERLINE bit for font selection)
  const bool hasBold = (style & BOLD) != 0;
  const bool hasItalic = (style & ITALIC) != 0;

  if (hasBold && hasItalic) {
    if (boldItalic) return boldItalic;
    if (bold) return bold;
    if (italic) return italic;
  } else if (hasBold && bold) {
    return bold;
  } else if (hasItalic && italic) {
    return italic;
  }

  return regular;
}

bool EpdFontFamily::isCjkCodepoint(const uint32_t cp) {
  return (cp >= 0x3000 && cp <= 0x303F) ||  // CJK Symbols and Punctuation
         (cp >= 0x4E00 && cp <= 0x9FFF) ||  // CJK Unified Ideographs
         (cp >= 0xF900 && cp <= 0xFAFF) ||  // CJK Compatibility Ideographs
         (cp >= 0xFF00 && cp <= 0xFFEF);    // Halfwidth and Fullwidth Forms
}

void EpdFontFamily::getTextDimensions(const char* string, int* w, int* h, const Style style) const {
  getFont(style)->getTextDimensions(string, w, h);
}

const EpdFontData* EpdFontFamily::getData(const Style style) const {
  if (lastWasFallback_ && cjkFallback_) {
    return cjkFallback_->getFontData();
  }
  return getFont(style)->data;
}

const EpdGlyph* EpdFontFamily::getGlyph(const uint32_t cp, const Style style) const {
  lastWasFallback_ = false;
  if (cjkFallback_ && isCjkCodepoint(cp)) {
    const EpdGlyph* g = cjkFallback_->getGlyph(cp);
    if (g != nullptr) {
      lastWasFallback_ = true;
      return g;
    }
  }
  return getFont(style)->getGlyph(cp);
}

int8_t EpdFontFamily::getKerning(const uint32_t leftCp, const uint32_t rightCp, const Style style) const {
  return getFont(style)->getKerning(leftCp, rightCp);
}

uint32_t EpdFontFamily::applyLigatures(const uint32_t cp, const char*& text, const Style style) const {
  return getFont(style)->applyLigatures(cp, text);
}
