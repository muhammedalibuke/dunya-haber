import { test } from "node:test";
import assert from "node:assert/strict";
import { isNewDevelopment, formatAgo, formatToday, t, STRINGS } from "../lib.js";

const NOW = new Date("2026-11-13T12:00:00Z");

test("isNewDevelopment only when seen before and updated since", () => {
  const ev = { id: "e1", updated_at: "2026-11-13T11:00:00+00:00" };
  assert.equal(isNewDevelopment(ev, {}), false);
  assert.equal(isNewDevelopment(ev, { e1: "2026-11-13T10:00:00+00:00" }), true);
  assert.equal(isNewDevelopment(ev, { e1: "2026-11-13T11:00:00+00:00" }), false);
});

test("formatAgo tr/en with boundaries", () => {
  const ago = (min) => new Date(NOW - min * 60000).toISOString();
  assert.equal(formatAgo(ago(2), NOW, "tr"), "az önce");
  assert.equal(formatAgo(ago(2), NOW, "en"), "just now");
  assert.equal(formatAgo(ago(30), NOW, "tr"), "30 dk önce");
  assert.equal(formatAgo(ago(30), NOW, "en"), "30m ago");
  assert.equal(formatAgo(ago(120), NOW, "tr"), "2 sa önce");
  assert.equal(formatAgo(ago(120), NOW, "en"), "2h ago");
  assert.equal(formatAgo(ago(26 * 60), NOW, "tr"), "dün");
  assert.equal(formatAgo(ago(26 * 60), NOW, "en"), "yesterday");
  assert.equal(formatAgo(ago(72 * 60), NOW, "tr"), "3 gün önce");
  assert.equal(formatAgo(ago(72 * 60), NOW, "en"), "3d ago");
});

test("formatToday uses Istanbul time", () => {
  const late = new Date("2026-11-13T22:30:00Z");
  assert.equal(formatToday(late, "tr"), "14 Kasım");
  assert.equal(formatToday(late, "en"), "14 November");
});

test("t fills placeholders and both languages share keys", () => {
  assert.equal(t("todayCount", "tr", { n: 7 }), "Bugün 7 önemli olay");
  assert.equal(t("sourceCount", "en", { n: 1 }), "1 source");
  assert.equal(t("sourceCount", "en", { n: 3 }), "3 sources");
  assert.deepEqual(Object.keys(STRINGS.tr).sort(), Object.keys(STRINGS.en).sort());
});

import { safeUrl, dataDir, formatUpdated } from "../lib.js";

test("safeUrl allows only absolute http(s)", () => {
  assert.equal(safeUrl("https://example.com/a"), "https://example.com/a");
  assert.equal(safeUrl("http://example.com/a"), "http://example.com/a");
  assert.equal(safeUrl("javascript:alert(1)"), null);
  assert.equal(safeUrl(" JavaScript:alert(1)"), null);
  assert.equal(safeUrl("data:text/html,x"), null);
  assert.equal(safeUrl("/relative"), null);
  assert.equal(safeUrl(undefined), null);
});

test("dataDir accepts only a plain folder name", () => {
  assert.equal(dataDir(null), "data");
  assert.equal(dataDir("dev-data"), "dev-data");
  assert.equal(dataDir("https://evil.example"), "data");
  assert.equal(dataDir("../x"), "data");
});

test("formatUpdated shows the date when data is not from today", () => {
  const now = new Date("2026-11-14T09:00:00Z");
  assert.equal(formatUpdated("2026-11-14T08:30:00Z", now, "tr"), "11:30");
  assert.equal(formatUpdated("2026-11-13T19:30:00Z", now, "tr"), "13 Kasım 22:30");
  assert.equal(formatUpdated("2026-11-13T19:30:00Z", now, "en"), "13 November 22:30");
});

test("sourceTotal copy", () => {
  assert.equal(t("sourceTotal", "tr", { n: 42 }), "Bu olayı toplam 42 kaynak haberleştirdi.");
  assert.equal(t("sourceTotal", "en", { n: 42 }), "42 outlets covered this event in total.");
});

import { nextEvents } from "../lib.js";

test("nextEvents: today first, unseen before seen, no current, no duplicates, max n", () => {
  const ev = (id) => ({ id, updated_at: "2026-11-13T10:00:00Z" });
  const today = ["a", "b", "c", "d"].map(ev);
  const all = ["e", "b", "f", "g", "h"].map(ev);
  const seen = { c: "2026-11-13T10:00:00Z", e: "2026-11-13T10:00:00Z" };
  assert.deepEqual(nextEvents("a", today, all, seen, 5).map((e) => e.id), ["b", "d", "f", "g", "h"]);
  assert.deepEqual(nextEvents("a", today, all, seen, 7).map((e) => e.id), ["b", "d", "f", "g", "h", "c", "e"]);
  assert.deepEqual(nextEvents("z", [], [], {}, 5), []);
});

test("moreNews copy", () => {
  assert.equal(t("moreNews", "tr"), "Diğer haberler");
  assert.equal(t("moreNews", "en"), "More stories");
});

test("nextEvents lists newest first within unseen and seen groups", () => {
  const ev = (id, h) => ({ id, updated_at: new Date(Date.UTC(2026, 10, 14, h)).toISOString() });
  const today = [ev("a", 1), ev("b", 3)];
  const all = [ev("c", 5), ev("d", 2), ev("e", 4)];
  const seen = { e: "x" };
  assert.deepEqual(nextEvents("z", today, all, seen, 5).map((e) => e.id), ["c", "b", "d", "a", "e"]);
});

test("latest-news copy", () => {
  assert.equal(t("seeAll", "tr"), "Son haberler");
  assert.equal(t("allTitle", "tr"), "Son haberler");
  assert.equal(t("allTitle", "en"), "Latest news");
});
