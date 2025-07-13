# POC Recursive Crawler - Detailed Findings

## 🎯 Overview

Successfully crawled 3 CultFit MindLive sections and extracted **31 media files** with proper hierarchical titles.

## ✅ Results Summary

| Section | Packs Found | Media Files | Type |
|---------|-------------|-------------|------|
| 5 Minute Meditations | 14 | 14 | Audio |
| Sleep Meditation | 12 | 12 | Audio |
| Yoga Asanas | 5 | 5 | Video |
| **Total** | **31** | **31** | - |

## 📊 Extraction Details

### 1. 5 Minute Meditations
**URL**: https://www.cult.fit/live/mindfulness/5-minute-meditations/MED_SERIES_12/s

**Content Found**:
- Stop Panic - Session 1
- Boost Confidence - Session 1
- Beat Cravings - Session 1 (3 sessions total)
- Morning Boost - Fresh Air (4 sessions total)
- Pre exam Stress - Session 1
- Flight Anxiety - Session 1
- Public Speaking - Session 1
- Post workout Meditation - Session 1 (6 sessions total)
- Working Mindfully - Session 1
- Take a Breather - Session 1 (3 sessions total)
- Heartfelt Gratitude - Session 1
- Anger - Session 1 (3 sessions total)
- Stress - Session 1 (3 sessions total)
- Mindful Eating - Session 1 (2 sessions total)

**Key Finding**: Each pack shows subtitle with total sessions (e.g., "3 sessions") but currently only extracting the intro session from `packIntroAction`.

### 2. Sleep Meditation
**URL**: https://www.cult.fit/live/mindfulness/meditation-for-sleep/MED_SERIES_3/s

**Content Found**:
- Sleep Stories by Dr Shyam Bhat - Follow the River (7 sessions total)
- Sleep Stories-2 by Dr Shyam Bhat - The Bamboo Cutter (8 sessions total)
- Falling into Sleep - Session 1 (6 sessions total)
- Sleep Easy - Session 1 (7 sessions total)
- Sleep Better - Session 1 (7 sessions total)
- Sleeping by the River - Session 1 (7 sessions total)
- Yoga Nidra for Relaxation - Session 1 (5 sessions total)
- Yoga Nidra Series-1 - Session 1 (2 sessions total)
- Yoga Nidra Series -2 - Session 1 (7 sessions total)
- Yoga Nidra Series -3 - Session 1 (7 sessions total)
- Yoga Nidra Series - 4 - Session 1 (7 sessions total)
- Sleep - Session 1 (6 sessions total)

### 3. Yoga Asanas
**URL**: https://www.cult.fit/live/mindfulness/yoga-asanas/MED_SERIES_21/s

**Content Found** (Video):
- Balancing Postures - Bakkasana (13 sessions total)
- Inversions - Halasana (3 sessions total)
- Seated Postures - Ardha Matsyendrasana (6 sessions total)
- Standing Postures - Adho Mukha Svanasana (18 sessions total)
- Back Bends - Bhujangasana (4 sessions total)

## 🔍 Technical Findings

### Data Structure
```json
{
  "cultDIYPackBrowse": {
    "widgets": [{
      "items": [{
        "title": "Pack Name",
        "subTitle": "X sessions",
        "description": "Description",
        "packIntroAction": "curefit://audioplayer?...",
        "playAction": "curefit://...",
        "content": [
          // Additional sessions would be here
        ]
      }]
    }]
  }
}
```

### Media URL Extraction
- URLs are encoded in `curefit://` protocol format
- Contains `absoluteAudioUrl` or `absoluteVideoUrl` parameters
- Direct CDN URLs: `https://cdn-media.cure.fit/audio/[uuid].mp3`

### Current Limitation
The crawler currently extracts only the intro/first session from each pack via `packIntroAction`. The `subTitle` field indicates there are more sessions available, but they would need to be accessed by:
1. Following the pack's detail page link
2. Extracting the full `content` array
3. Or making additional API calls

## 📁 Output Files

1. **all_content.json** - Complete list of all extracted media
2. **content_hierarchy.json** - Hierarchical view of content
3. **section_results.json** - Detailed crawl results per section
4. **poc_report.txt** - Summary report
5. **HTML files** - Saved page content for each section

## ✅ Verification

The crawler successfully:
1. ✅ Navigates to each section URL
2. ✅ Extracts `__PRELOADED_STATE__` data
3. ✅ Parses the nested widget/items structure
4. ✅ Decodes `curefit://` URLs to get actual media URLs
5. ✅ Extracts proper titles (not generic "Track 1, Track 2")
6. ✅ Handles both audio and video content types
7. ✅ Maintains hierarchical structure (Section > Pack > Session)

## 🚀 Next Steps

To get ALL sessions from each pack (not just the intro), the crawler would need to:
1. Check if `content` array exists in each item
2. Parse all sessions from the `content` array
3. Or follow pack links to detail pages for complete session lists

The current implementation provides a solid foundation and proves the concept works across different section types. 