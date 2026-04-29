#pragma once
#include <HalStorage.h>

#include <EpdFontData.h>
#include <cstdint>
#include <vector>

/// Streams CJK glyph bitmaps from an .epdf file (SD card or flash-embedded data).
/// Index is kept in RAM for O(log N) lookup; bitmaps are fetched on demand
/// into a fixed LRU cache pool.
class SdFont {
 public:
  static constexpr int CACHE_SLOTS = 64;
  // 14pt @ 150 DPI → ~29px glyph → 29×29/8 ≈ 106 bytes; 128 gives headroom
  static constexpr int MAX_GLYPH_BYTES = 128;

  bool load(const char* path);
  bool loadFromMemory(const uint8_t* data, size_t size);
  void unload();
  bool isLoaded() const { return loaded_; }

  /// Returns a pointer to EpdGlyph for cp, or nullptr if not in this font.
  /// The returned pointer is valid only until the next getGlyph() call.
  const EpdGlyph* getGlyph(uint32_t cp);

  const EpdFontData* getFontData() const { return &fontData_; }

 private:
  static constexpr uint32_t HEADER_SIZE = 32;
  static constexpr uint32_t INDEX_ENTRY_BYTES = 16;

  struct __attribute__((packed)) FileIndexEntry {
    uint32_t cp;
    uint32_t bitmapOffset;
    uint8_t  width;
    uint8_t  height;
    uint16_t advanceX;
    int16_t  left;
    int16_t  top;
  };
  static_assert(sizeof(FileIndexEntry) == INDEX_ENTRY_BYTES, "FileIndexEntry size mismatch");

  struct CacheSlot {
    uint32_t cp      = 0;
    uint32_t age     = 0;
    uint8_t  width   = 0;
    uint8_t  height  = 0;
    uint16_t advanceX = 0;
    int16_t  left    = 0;
    int16_t  top     = 0;
  };

  bool loaded_     = false;
  uint32_t count_  = 0;
  uint16_t maxBytes_ = 0;

  uint32_t* cpList_ = nullptr;           // heap: sorted codepoints for binary search

  CacheSlot   cacheSlots_[CACHE_SLOTS];  // per-slot metadata
  uint8_t     bitmapPool_[CACHE_SLOTS * MAX_GLYPH_BYTES] = {};
  uint32_t    lruClock_ = 0;

  EpdGlyph        activeGlyph_ = {};
  EpdUnicodeInterval interval_ = {};
  EpdFontData     fontData_    = {};
  HalFile         file_;

  // Memory mode (flash-embedded EPDF): non-null overrides file_
  const uint8_t* memData_ = nullptr;
  size_t         memSize_ = 0;

  bool     readAt(size_t pos, void* buf, size_t len);
  bool     initFromHeader(const uint8_t* hdr);

  int      findInIndex(uint32_t cp) const;
  int      findInCache(uint32_t cp) const;
  int      evictSlot()              const;
  bool     loadSlot(int slot, const FileIndexEntry& entry);
};
