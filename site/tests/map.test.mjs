import { test } from "node:test";
import assert from "node:assert/strict";
import { spreadPoints } from "../map.js";

const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);

test("identical points end at least minDist apart", () => {
  const out = spreadPoints([{ id: "a", x: 100, y: 50 }, { id: "b", x: 100, y: 50 }], 10);
  assert.ok(dist(out[0], out[1]) >= 10 - 1e-9);
});

test("three clustered points all separated", () => {
  const pts = [{ id: "a", x: 0, y: 0 }, { id: "b", x: 2, y: 1 }, { id: "c", x: 1, y: 3 }];
  const out = spreadPoints(pts, 12);
  for (let i = 0; i < 3; i++) for (let j = i + 1; j < 3; j++) assert.ok(dist(out[i], out[j]) >= 12 - 1e-6);
});

test("isolated point unchanged and input not mutated", () => {
  const pts = [{ id: "a", x: 0, y: 0 }, { id: "b", x: 200, y: 200 }];
  const out = spreadPoints(pts, 10);
  assert.deepEqual(out, pts);
  assert.notEqual(out[0], pts[0]);
});

test("deterministic", () => {
  const pts = [{ id: "a", x: 5, y: 5 }, { id: "b", x: 5, y: 5 }, { id: "c", x: 6, y: 5 }];
  assert.deepEqual(spreadPoints(pts, 10), spreadPoints(pts, 10));
});

import { placeLabels } from "../map.js";

const box = (l) => { const x0 = l.anchor === "end" ? l.x - l.w : l.x; return { x0, x1: x0 + l.w, y0: l.y - 6, y1: l.y + 6 }; };
const overlap = (a, b) => a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1;

test("labels go right of the dot, flip left near the edge, never overlap", () => {
  const pts = [
    { id: "a", x: 50, y: 50, text: "Kobe" },
    { id: "b", x: 380, y: 50, text: "Wellington" },
    { id: "c", x: 52, y: 52, text: "Osaka" },
  ];
  const out = placeLabels(pts, 400, 200, { charW: 6, gap: 11 });
  const a = out.find((l) => l.id === "a");
  assert.ok(a.x > 50 && a.anchor === "start");
  const b = out.find((l) => l.id === "b");
  assert.ok(b.anchor === "end" && b.x < 380);
  const shown = out.map(box);
  for (let i = 0; i < shown.length; i++)
    for (let j = i + 1; j < shown.length; j++) assert.ok(!overlap(shown[i], shown[j]));
  for (const l of out) assert.ok(l.x - (l.anchor === "end" ? l.w : 0) >= 0);
});

test("labels never cover another dot", () => {
  const pts = [{ id: "a", x: 100, y: 100, text: "Brussels" }, { id: "b", x: 125, y: 100, text: "Paris" }];
  const out = placeLabels(pts, 400, 200, { charW: 6, gap: 11 });
  for (const l of out) {
    const x0 = l.anchor === "end" ? l.x - l.w : l.x;
    for (const p of pts) {
      if (p.id === l.id) continue;
      assert.ok(!(p.x + 8 > x0 && p.x - 8 < x0 + l.w && p.y + 8 > l.y - 6 && p.y - 8 < l.y + 6));
    }
  }
});
