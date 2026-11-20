# On This Day Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** A "Tarihte bugün" page with world events, births and deaths for today, in TR and EN.
**Architecture:** `pipeline/history.py` fetches + parses + translates once per Istanbul day; state keeps it; site renders `#/tarih`.
**Tech Stack:** Python 3.12, httpx, Argos; vanilla JS.
**Spec:** docs/superpowers/specs/2026-11-20-on-this-day-design.md

## Global Constraints
- Source URL: `https://en.wikipedia.org/api/rest_v1/feed/onthisday/all/{MM}/{DD}` with a User-Agent naming the project.
- Items: `{year, text:{tr,en}, title, url, thumb}`; births/deaths: with thumbnail, newest 20.
- Never blank: translation missing → English; fetch failed → keep last data.

## Review Focus
- Fetch fails on the first day (no previous data) → no history.json; page says it is not ready.
- Date changes at Istanbul midnight, not UTC.
- Items without pages/thumbnails.
- Unsafe URLs (only https wikipedia links/images).
- Translation budget exhausted → English shown, retried next run.

### Task 1: `pipeline/history.py` (parse, select, translate, refresh) + tests
### Task 2: State + run wiring + history.json output + tests
### Task 3: Site page `#/tarih`, masthead link, strings + tests; screenshot; push; verify live
