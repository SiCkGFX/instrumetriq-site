---
title: "Archive Cleanup - Schema v6 Removal"
date: 2026-01-27
description: "Removed incomplete schema v6 entries from December 9-14, 2025"
author: "System"
---

## Archive Maintenance

Removed 6 days of early archive data (2025-12-09 through 2025-12-14) due to incomplete schema version 6 coverage. These entries predated the full v7 schema implementation and lacked critical sentiment metadata fields.

## Impact Summary

| Metric | Before | After | Change |
| :--- | :--- | :--- | :--- |
| **Total Entries** | 110,940 | 106,400 | -4,540 |
| **Days Archived** | 50 | 44 | -6 |
| **Date Range** | 2025-12-09 to 2026-01-27 | 2025-12-15 to 2026-01-27 | Start +6 days |

## Rationale

The removed entries were incompatible with tier 2 and tier 3 transformations, causing build failures due to missing required fields:
- `twitter_sentiment_meta` (entire struct)
- Sentiment breakdown fields (`posts_pos`, `posts_neu`, `posts_neg`)
- Archive schema version tracking

All removed data has been compressed and archived as `archive_schema_v6_backup_20251209-20251214.tar.gz` (50 MB) for historical reference.

## Current State

The archive now begins at **2025-12-15** with full v7 schema compliance across all 44 days. All tier builds (tier1, tier2, tier3) now complete successfully without schema-related failures.

***
*Archive integrity maintained. Historical data preserved in backup.*
