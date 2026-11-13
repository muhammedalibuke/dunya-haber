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
