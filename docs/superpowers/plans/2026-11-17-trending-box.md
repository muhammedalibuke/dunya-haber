# Trending Box Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show the multi-day, still-developing story in a box at the top of the home screen with its last update time and its 3 latest developments.

**Architecture:** The pipeline picks the story (`rank.select_featured`), makes sure the chosen developments are translated (`run`), and writes a `featured` object into `today.json` (`publish.featured_block`). The site renders it above the map and drops it from the list.

**Tech Stack:** Python 3.12 + pytest; vanilla JS ES modules + node --test.

**Spec:** docs/superpowers/specs/2026-11-17-trending-box-design.md

## Global Constraints
- Selection: topic "general", created_at ≤ now−24h, updated_at ≥ now−6h, ≥10 distinct sources; best = most distinct sources among articles of the last 24h; tie → newer updated_at.
- Developments: newest first, one per source, skip titles with word-overlap ≥ 0.5 with an already chosen one, skip garbled titles, max 3.
- Detail: first 2 sentences (≤ 240 chars) of the translated `default_summary(description)`.
- Days = (now.date() − created_at.date()).days + 1 (UTC).
- Garbled translations fall back to the original text.

## Review Focus
- No story qualifies → `featured` is null and the site shows no box, no gap.
- Featured story also selected for today → appears only in the box.
- Development without description → shown with headline only.
- Missing translation (budget ran out) → original-language text, never blank.
- Old `today.json` without `featured` (cached) → site still renders.

---

### Task 1: Garbled translations fall back to the original
**Files:** Modify `pipeline/translate.py`; Test `tests/test_translate.py`
- [ ] Test `test_garbled_translation_falls_back_to_original`: translator returns "mainstremainstremainstremainstre"; `translate_cached("Main street", "en", "tr", cache, tr) == "Main street"`; also a cached garbled hit returns the original.
- [ ] Test `test_translate_articles_redoes_garbled_titles`: article with title_tr garbled gets re-translated.
- [ ] Implement `is_garbled(text) -> bool` (move `_GARBLED` use from collect.py) and the checks. Run pytest → PASS. Commit.

### Task 2: Pick the featured story
**Files:** Modify `pipeline/rank.py`; Test `tests/test_rank.py`
**Produces:** `select_featured(events, articles, now) -> str | None`
- [ ] Tests: qualifies vs too young / stale / sport / <10 sources; picks most sources in last 24h.
- [ ] Implement; pytest PASS; commit.

### Task 3: Developments and `featured` in today.json; run wiring
**Files:** Modify `pipeline/publish.py`, `pipeline/run.py`; Test `tests/test_publish.py`, `tests/test_run_e2e.py`
**Consumes:** `select_featured`. **Produces:** `developments(event, articles, max_n=3) -> list[Article]`, `featured_block(event, articles, translations, now) -> dict`, `build_site_data(state, today_ids, now, featured_id=None)`; today.json `{"featured": {...summary fields, "days", "developments": [{"published","source","url","title":{tr,en},"detail":{tr,en}}]} | null}`; featured id removed from `events`.
- [ ] Tests for developments rules, detail text, exclusion from list, null when none, e2e run writes featured.
- [ ] Implement; run translates `default_summary` of the chosen developments and includes the featured event in `published_events`. pytest PASS; commit.

### Task 4: Site box
**Files:** Modify `site/lib.js`, `site/app.js`, `site/style.css`; Test `site/tests/lib.test.mjs`
**Produces:** `formatDateTime(iso, lang)` ("17 Kasım Salı, 19:12"), strings `trendingDays`, `lastUpdate`, `developments`, `readFull`.
- [ ] Tests for strings and formatDateTime; implement; render box above map; CSS; npm test PASS; screenshot check; commit, push, verify live run.
