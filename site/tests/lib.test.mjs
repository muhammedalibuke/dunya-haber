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
