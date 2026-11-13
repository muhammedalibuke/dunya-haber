// Maps drawn from bundled Natural Earth TopoJSON with d3-geo. No tile services.
// spreadPoints is pure (tested in node); the drawing functions need a browser.

const SVG_NS = "http://www.w3.org/2000/svg";
const GOLDEN_ANGLE = 2.399963229728653;

export function spreadPoints(points, minDist = 10) {
  const pts = points.map((p) => ({ ...p }));
  for (let iter = 0; iter < 60; iter++) {
    let moved = false;
    for (let i = 0; i < pts.length; i++) {
      for (let j = i + 1; j < pts.length; j++) {
        let dx = pts[j].x - pts[i].x;
        let dy = pts[j].y - pts[i].y;
        let d = Math.hypot(dx, dy);
        if (d >= minDist - 1e-9) continue;
        if (d < 1e-9) {
          const a = (i + j) * GOLDEN_ANGLE;
          dx = Math.cos(a);
          dy = Math.sin(a);
          d = 1;
        } else {
          dx /= d;
          dy /= d;
        }
        const push = (minDist - Math.min(d, minDist) + 1e-6) / 2;
        pts[i].x -= dx * push;
        pts[i].y -= dy * push;
        pts[j].x += dx * push;
        pts[j].y += dy * push;
        moved = true;
      }
    }
    if (!moved) break;
  }
  return pts;
}

// Place name labels next to dots: right, else left, else nudged up/down; skipped if nothing fits.
export function placeLabels(points, width, height, { charW = 6, gap = 11, lineH = 12, dotR = 8 } = {}) {
  const placed = [];
  const boxOf = (l) => {
    const x0 = l.anchor === "end" ? l.x - l.w : l.x;
    return { x0, x1: x0 + l.w, y0: l.y - lineH / 2, y1: l.y + lineH / 2 };
  };
  const hits = (a, b) => a.x0 < b.x1 && b.x0 < a.x1 && a.y0 < b.y1 && b.y0 < a.y1;
  const dots = points.map((p) => ({ x0: p.x - dotR, x1: p.x + dotR, y0: p.y - dotR, y1: p.y + dotR }));
  for (const p of points) {
    if (!p.text) continue;
    const w = p.text.length * charW;
    const tries = [];
    for (const dy of [0, -lineH, lineH]) {
      tries.push({ x: p.x + gap, y: p.y + dy, anchor: "start" });
      tries.push({ x: p.x - gap, y: p.y + dy, anchor: "end" });
    }
    for (const t of tries) {
      const l = { id: p.id, text: p.text, w, ...t };
      const b = boxOf(l);
      if (b.x0 < 0 || b.x1 > width || b.y0 < 0 || b.y1 > height) continue;
      if (placed.some((q) => hits(b, boxOf(q))) || dots.some((d) => hits(b, d))) continue;
      placed.push(l);
      break;
    }
  }
  return placed;
}

// ---- browser-only below ----

const libs = { ready: null };

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = src;
    s.onload = resolve;
    s.onerror = () => reject(new Error(`failed to load ${src}`));
    document.head.append(s);
  });
}

function ensureLibs() {
  if (!libs.ready) {
    libs.ready = loadScript("vendor/d3-array.min.js")
      .then(() => loadScript("vendor/d3-geo.min.js"))
      .then(() => loadScript("vendor/topojson-client.min.js"));
  }
  return libs.ready;
}

const topoCache = new Map();
function loadTopo(name) {
  if (!topoCache.has(name)) {
    topoCache.set(name, fetch(`map/${name}.topo.json`).then((r) => {
      if (!r.ok) throw new Error(`map ${name}: ${r.status}`);
      return r.json();
    }));
  }
  return topoCache.get(name);
}

function svgEl(tag, attrs = {}) {
  const n = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  return n;
}

function countries(topo) {
  return topojson.feature(topo, topo.objects.countries).features;
}

export async function worldMap(container, events, onSelect) {
  try {
    await ensureLibs();
    const topo = await loadTopo("world");
    const feats = countries(topo).filter((f) => f.properties.iso !== "AQ");
    const width = Math.max(280, container.clientWidth || 360);
    const height = Math.round(width * 0.5);
    const projection = d3.geoEqualEarth().fitSize([width, height], { type: "FeatureCollection", features: feats });
    const path = d3.geoPath(projection);

    const tinted = new Set(events.filter((e) => e.location).map((e) => e.location.country));
    const svg = svgEl("svg", { viewBox: `0 0 ${width} ${height}`, class: "map-svg", role: "group",
      "aria-label": "map" });
    for (const f of feats) {
      svg.append(svgEl("path", { d: path(f), class: tinted.has(f.properties.iso) ? "m-land m-tint" : "m-land" }));
    }

    const placed = events
      .map((e, i) => ({ e, rank: i + 1 }))
      .filter(({ e }) => e.location)
      .map(({ e, rank }) => {
        const [x, y] = projection([e.location.lon, e.location.lat]);
        return { id: e.id, x, y, e, rank };
      });
    const spread = spreadPoints(placed.map(({ id, x, y }) => ({ id, x, y })), 17);
    const lang = document.documentElement.lang === "en" ? "en" : "tr";
    const labelText = (e) => (e.location.level === "country" ? e.country.name[lang] : e.location.name) || "";
    const labels = placeLabels(
      spread.map((p, i) => ({ ...p, text: labelText(placed[i].e) })), width, height, { charW: 6.2, gap: 11 });
    const labelLayer = svgEl("g", { class: "m-labels", "aria-hidden": "true" });
    for (const l of labels) {
      const tx = svgEl("text", { x: l.x, y: l.y, "text-anchor": l.anchor, "dominant-baseline": "central",
        class: "m-label" });
      tx.textContent = l.text;
      labelLayer.append(tx);
    }
    svg.append(labelLayer);
    spread.forEach((p, i) => {
      const { e, rank } = placed[i];
      const country = e.location.level === "country";
      const g = svgEl("g", { class: "m-point", tabindex: "0", role: "link",
        "aria-label": `${rank}. ${e.title[document.documentElement.lang] || e.title.tr}` });
      g.append(svgEl("circle", { cx: p.x, cy: p.y, r: 16, class: "m-hit" }));
      g.append(svgEl("circle", { cx: p.x, cy: p.y, r: 8, class: country ? "m-ring" : "m-dot" }));
      const num = svgEl("text", { x: p.x, y: p.y, class: country ? "m-num m-num-ring" : "m-num",
        "text-anchor": "middle", "dominant-baseline": "central" });
      num.textContent = String(rank);
      g.append(num);
      g.addEventListener("click", () => onSelect(e.id));
      g.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") onSelect(e.id); });
      svg.append(g);
    });
    container.replaceChildren(svg);
  } catch (err) {
    console.error(err);
    container.replaceChildren();
  }
}
