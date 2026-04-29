#include "SdFont.h"

#include <Logging.h>

#include <algorithm>
#include <cstring>

bool SdFont::readAt(size_t pos, void* buf, size_t len) {
  if (memData_) {
    if (pos + len > memSize_) return false;
    memcpy(buf, memData_ + pos, len);
    return true;
  }
  if (!file_.seekSet(pos)) return false;
  return file_.read(buf, len) == static_cast<int>(len);
}

bool SdFont::initFromHeader(const uint8_t* hdr) {
  if (hdr[0] != 'E' || hdr[1] != 'P' || hdr[2] != 'D' || hdr[3] != 'F' || hdr[4] != 1) {
    LOG_ERR("SDF", "Bad EPDF magic or version");
    return false;
  }

  uint16_t cnt;
  memcpy(&cnt, hdr + 5, 2);
  if (cnt == 0) {
    LOG_ERR("SDF", "Empty EPDF file");
    return false;
  }
  count_ = cnt;

  uint8_t advanceY = hdr[7];
  int16_t ascender, descender;
  memcpy(&ascender, hdr + 8, 2);
  memcpy(&descender, hdr + 10, 2);
  memcpy(&maxBytes_, hdr + 12, 2);

  if (maxBytes_ > MAX_GLYPH_BYTES) {
    LOG_ERR("SDF", "EPDF maxGlyphBytes %u > %u — rebuild with smaller size", maxBytes_, MAX_GLYPH_BYTES);
    return false;
  }

  cpList_ = new uint32_t[count_];
  if (!cpList_) {
    LOG_ERR("SDF", "OOM for cpList");
    return false;
  }

  for (uint32_t i = 0; i < count_; i++) {
    uint8_t entry[INDEX_ENTRY_BYTES];
    if (!readAt(HEADER_SIZE + i * INDEX_ENTRY_BYTES, entry, INDEX_ENTRY_BYTES)) {
      LOG_ERR("SDF", "Failed reading index entry %u", i);
      delete[] cpList_;
      cpList_ = nullptr;
      return false;
    }
    memcpy(&cpList_[i], entry, 4);
  }

  for (int s = 0; s < CACHE_SLOTS; s++) cacheSlots_[s] = {};
  memset(bitmapPool_, 0, sizeof(bitmapPool_));
  lruClock_ = 0;

  memset(&fontData_, 0, sizeof(fontData_));
  fontData_.bitmap     = bitmapPool_;
  fontData_.glyph      = nullptr;
  fontData_.advanceY   = advanceY;
  fontData_.ascender   = ascender;
  fontData_.descender  = descender;
  fontData_.is2Bit     = false;
  fontData_.groups     = nullptr;
  fontData_.groupCount = 0;
  interval_.first      = cpList_[0];
  interval_.last       = cpList_[count_ - 1];
  interval_.offset     = 0;
  fontData_.intervals     = &interval_;
  fontData_.intervalCount = 1;

  loaded_ = true;
  LOG_DBG("SDF", "EPDF loaded: %u glyphs, ascender=%d advY=%u", count_, ascender, advanceY);
  return true;
}

bool SdFont::load(const char* path) {
  unload();

  if (!Storage.openFileForRead("SDF", path, file_)) {
    return false;
  }

  uint8_t hdr[HEADER_SIZE];
  if (file_.read(hdr, HEADER_SIZE) != static_cast<int>(HEADER_SIZE)) {
    LOG_ERR("SDF", "Failed to read EPDF header from %s", path);
    file_.close();
    return false;
  }

  if (!initFromHeader(hdr)) {
    file_.close();
    return false;
  }

  LOG_INF("SDF", "Loaded EPDF from SD: %s (%u glyphs)", path, count_);
  return true;
}

bool SdFont::loadFromMemory(const uint8_t* data, size_t size) {
  unload();

  if (!data || size < HEADER_SIZE) {
    LOG_ERR("SDF", "Invalid memory EPDF data");
    return false;
  }

  memData_ = data;
  memSize_ = size;

  if (!initFromHeader(data)) {
    memData_ = nullptr;
    memSize_ = 0;
    return false;
  }

  LOG_INF("SDF", "Loaded EPDF from flash (%u glyphs)", count_);
  return true;
}

void SdFont::unload() {
  if (!loaded_) return;
  if (!memData_) file_.close();
  memData_ = nullptr;
  memSize_ = 0;
  delete[] cpList_;
  cpList_  = nullptr;
  count_   = 0;
  loaded_  = false;
  lruClock_ = 0;
  for (int s = 0; s < CACHE_SLOTS; s++) cacheSlots_[s] = {};
}

int SdFont::findInIndex(uint32_t cp) const {
  int lo = 0, hi = static_cast<int>(count_) - 1;
  while (lo <= hi) {
    const int mid = (lo + hi) >> 1;
    if (cpList_[mid] == cp) return mid;
    if (cpList_[mid] < cp) lo = mid + 1;
    else hi = mid - 1;
  }
  return -1;
}

int SdFont::findInCache(uint32_t cp) const {
  for (int i = 0; i < CACHE_SLOTS; i++) {
    if (cacheSlots_[i].cp == cp) return i;
  }
  return -1;
}

int SdFont::evictSlot() const {
  // Prefer an empty slot
  for (int i = 0; i < CACHE_SLOTS; i++) {
    if (cacheSlots_[i].cp == 0) return i;
  }
  // Otherwise find the oldest (LRU)
  int minSlot = 0;
  uint32_t minAge = cacheSlots_[0].age;
  for (int i = 1; i < CACHE_SLOTS; i++) {
    if (cacheSlots_[i].age < minAge) {
      minAge = cacheSlots_[i].age;
      minSlot = i;
    }
  }
  return minSlot;
}

bool SdFont::loadSlot(int slot, const FileIndexEntry& entry) {
  const uint16_t bits = static_cast<uint16_t>(entry.width) * entry.height;
  const uint16_t bytes = (bits + 7) / 8;
  if (bytes > MAX_GLYPH_BYTES) {
    LOG_ERR("SDF", "Glyph too large: %u bytes", bytes);
    return false;
  }
  if (!readAt(entry.bitmapOffset, bitmapPool_ + slot * MAX_GLYPH_BYTES, bytes)) {
    LOG_ERR("SDF", "Bitmap read failed at 0x%x (%u bytes)", entry.bitmapOffset, bytes);
    return false;
  }
  CacheSlot& cs     = cacheSlots_[slot];
  cs.cp             = entry.cp;
  cs.age            = ++lruClock_;
  cs.width          = entry.width;
  cs.height         = entry.height;
  cs.advanceX       = entry.advanceX;
  cs.left           = entry.left;
  cs.top            = entry.top;
  return true;
}

const EpdGlyph* SdFont::getGlyph(uint32_t cp) {
  if (!loaded_) return nullptr;

  const int idx = findInIndex(cp);
  if (idx < 0) return nullptr;

  // Cache hit?
  int slot = findInCache(cp);
  if (slot < 0) {
    // Cache miss — read index entry then bitmap
    const size_t filePos = HEADER_SIZE + static_cast<size_t>(idx) * INDEX_ENTRY_BYTES;
    FileIndexEntry entry{};
    if (!readAt(filePos, &entry, INDEX_ENTRY_BYTES)) {
      LOG_ERR("SDF", "Index read failed at entry %d", idx);
      return nullptr;
    }
    slot = evictSlot();
    if (!loadSlot(slot, entry)) return nullptr;
  } else {
    cacheSlots_[slot].age = ++lruClock_;
  }

  const CacheSlot& cs = cacheSlots_[slot];
  activeGlyph_.width      = cs.width;
  activeGlyph_.height     = cs.height;
  activeGlyph_.advanceX   = cs.advanceX;
  activeGlyph_.left       = cs.left;
  activeGlyph_.top        = cs.top;
  activeGlyph_.dataOffset = static_cast<uint32_t>(slot) * MAX_GLYPH_BYTES;
  activeGlyph_.dataLength = (static_cast<uint16_t>(cs.width) * cs.height + 7) / 8;
  return &activeGlyph_;
}
