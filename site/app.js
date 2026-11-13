import { t, isNewDevelopment, formatAgo, formatToday, formatClock } from "./lib.js";

const params = new URLSearchParams(location.search);
const DATA = params.get("data") || "data";
const app = document.getElementById("app");

const store = {
  get(key, fallback) {
    try {
      const v = localStorage.getItem(key);
      return v === null ? fallback : JSON.parse(v);
    } catch {
      return fallback;
    }
  },
  set(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      /* private mode or storage disabled: keep working without it */
    }
  },
};

let lang = store.get("lang", "tr") === "en" ? "en" : "tr";
const cache = new Map();

async function getJSON(path) {
  if (!cache.has(path)) {
    cache.set(path, fetch(`${DATA}/${path}`, { cache: "no-cache" }).then((r) => {
      if (!r.ok) throw new Error(`${r.status} ${path}`);
      return r.json();
    }));
  }
  try {
    return await cache.get(path);
  } catch (e) {
    cache.delete(path);
    throw e;
  }
}

// Every piece of feed text goes through textContent: nothing from a feed is parsed as HTML.
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") node.className = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}

function langButton() {
  return el("button", {
    class: "lang", type: "button", lang: lang === "tr" ? "en" : "tr",
    "aria-label": t("langSwitchLabel", lang), text: t("langSwitch", lang),
    onclick: () => {
      lang = lang === "tr" ? "en" : "tr";
      store.set("lang", lang);
      render();
    },
  });
}

function eventRow(ev, rank, now, seen) {
  const meta = el("span", { class: "meta" },
    el("span", { text: ev.country.name[lang] || "" }),
    el("span", { text: formatAgo(ev.updated_at, now, lang) }),
    isNewDevelopment(ev, seen) ? el("span", { class: "new", text: t("newDev", lang) }) : null);
  return el("li", { class: "row" },
    el("a", { href: `#/e/${encodeURIComponent(ev.id)}` },
      rank ? el("span", { class: "rank", "aria-hidden": "true", text: String(rank) }) : null,
      meta,
      el("span", { class: "title", text: ev.title[lang] }),
      el("span", { class: "count", text: t("sourceCount", lang, { n: ev.source_count }) })));
}

function footer(generatedAt) {
  return el("footer", { class: "foot" },
    generatedAt ? el("p", { text: t("updated", lang, { t: formatClock(generatedAt, lang) }) }) : null,
    el("p", { text: t("credits", lang) }));
}

function message(text) {
  return el("p", { class: "quiet", text });
}

const mapHooks = { world: null, detail: null };
export function registerMaps(world, detail) {
  mapHooks.world = world;
  mapHooks.detail = detail;
}

async function viewToday() {
  const now = new Date();
  const data = await getJSON("today.json");
  const seen = store.get("seen", {});
  const mapBox = el("div", { class: "map" });
  const events = data.events;
  app.replaceChildren(
    el("header", { class: "top" },
      el("h1", { class: "date", text: formatToday(now, lang) }),
      langButton()),
    mapBox,
    ...(events.length
      ? [
        el("p", { class: "lede", text: t("todayCount", lang, { n: events.length }) }),
        el("ol", { class: "list ranked" }, events.map((ev, i) => eventRow(ev, i + 1, now, seen))),
      ]
      : [message(t("quiet", lang))]),
    el("p", { class: "end" },
      events.length ? `${t("end", lang)} ` : null,
      el("a", { href: "#/all", text: t("seeAll", lang) })),
    footer(data.generated_at));
  if (events.length && mapHooks.world) {
    mapHooks.world(mapBox, events, (id) => { location.hash = `#/e/${encodeURIComponent(id)}`; });
  }
}

async function viewAll() {
  const now = new Date();
  const data = await getJSON("all.json");
  const seen = store.get("seen", {});
  app.replaceChildren(
    el("a", { class: "back", href: "#/", text: `← ${t("back", lang)}` }),
    el("header", { class: "top" },
      el("h1", { class: "page-title", text: t("allTitle", lang) }),
      langButton()),
    data.events.length
      ? el("ul", { class: "list" }, data.events.map((ev) => eventRow(ev, 0, now, seen)))
      : message(t("quiet", lang)),
    footer(data.generated_at));
}

async function viewEvent(id) {
  const now = new Date();
  let ev;
  try {
    ev = await getJSON(`events/${encodeURIComponent(id)}.json`);
  } catch {
    app.replaceChildren(
      el("a", { class: "back", href: "#/", text: `← ${t("back", lang)}` }),
      message(t("notFound", lang)));
    return;
  }
  const seen = store.get("seen", {});
  seen[ev.id] = ev.updated_at;
  store.set("seen", seen);

  const mapBox = el("div", { class: "map" });
  const summary = ev.summary[lang];
  app.replaceChildren(
    el("header", { class: "top" },
      el("a", { class: "back", href: "#/", text: `← ${t("back", lang)}` }),
      langButton()),
    el("article", { class: "detail" },
      ev.image ? el("figure", { class: "photo" },
        el("img", { src: ev.image.url, alt: "", loading: "lazy", referrerpolicy: "no-referrer",
                    onerror: (e) => e.target.closest("figure")?.remove() }),
        el("figcaption", { text: t("photo", lang, { s: ev.image.source }) })) : null,
      el("h1", { class: "detail-title", text: ev.title[lang] }),
      el("p", { class: "meta" },
        el("span", { text: ev.country.name[lang] || "" }),
        el("span", { text: formatAgo(ev.updated_at, now, lang) })),
      mapBox,
      summary ? el("p", { class: "summary", text: summary }) : null,
      summary && ev.summary.ai ? el("p", { class: "ai", text: t("aiSummary", lang) }) : null,
      el("h2", { class: "section", text: t("sources", lang) }),
      el("ul", { class: "list" }, ev.sources.map((s) =>
        el("li", { class: "row src" },
          el("a", { href: s.url, target: "_blank", rel: "noopener noreferrer" },
            el("span", { class: "src-name", text: s.name }),
            el("span", { class: "src-title", text: s.title[lang] }),
            el("span", { class: "src-arrow", "aria-hidden": "true", text: "↗" })))))),
    footer(null));
  if (ev.location && mapHooks.detail) mapHooks.detail(mapBox, ev.location);
}

async function render() {
  document.documentElement.lang = lang;
  const hash = location.hash || "#/";
  try {
    if (hash.startsWith("#/e/")) await viewEvent(decodeURIComponent(hash.slice(4)));
    else if (hash === "#/all") await viewAll();
    else await viewToday();
  } catch (e) {
    console.error(e);
    app.replaceChildren(message(t("loadError", lang)));
  }
  window.scrollTo(0, 0);
}

window.addEventListener("hashchange", render);
render();
