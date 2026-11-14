import { t, isNewDevelopment, formatAgo, formatToday, formatUpdated, safeUrl, dataDir, nextEvents } from "./lib.js";
import { worldMap } from "./map.js";

const params = new URLSearchParams(location.search);
const DATA = dataDir(params.get("data"));
const CACHE_MS = 5 * 60 * 1000;
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
  const hit = cache.get(path);
  if (!hit || Date.now() - hit.at > CACHE_MS) {
    cache.set(path, {
      at: Date.now(),
      p: fetch(`${DATA}/${path}`, { cache: "no-cache" }).then((r) => {
        if (!r.ok) throw new Error(`${r.status} ${path}`);
        return r.json();
      }),
    });
  }
  try {
    return await cache.get(path).p;
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

function placeName(ev) {
  const country = ev.country.name[lang] || "";
  const loc = ev.location;
  if (loc && loc.level !== "country" && loc.name && loc.name !== country) return `${loc.name}, ${country}`;
  return country;
}

function photos(images) {
  const list = (images || []).filter((i) => safeUrl(i.url));
  if (!list.length) return { hero: null, thumbs: null };
  const img = el("img", { src: safeUrl(list[0].url), alt: "", referrerpolicy: "no-referrer" });
  const cap = el("figcaption", { text: t("photo", lang, { s: list[0].source }) });
  const hero = el("figure", { class: "photo" }, img, cap);
  const buttons = [];
  const show = (i) => {
    img.src = safeUrl(list[i].url);
    cap.textContent = t("photo", lang, { s: list[i].source });
    buttons.forEach((b, j) => b.setAttribute("aria-pressed", String(j === i)));
  };
  img.addEventListener("error", () => {
    const next = buttons.find((b) => b.isConnected && b.getAttribute("aria-pressed") !== "true");
    if (next) next.click();
    else hero.remove();
  });
  if (list.length > 1) {
    list.forEach((im, i) => {
      const b = el("button", { type: "button", class: "thumb", "aria-pressed": String(i === 0),
        "aria-label": t("photo", lang, { s: im.source }), onclick: () => show(i) },
        el("img", { src: safeUrl(im.url), alt: "", loading: "lazy", referrerpolicy: "no-referrer",
          onerror: (e) => e.target.closest("button")?.remove() }));
      buttons.push(b);
    });
  }
  return { hero, thumbs: buttons.length ? el("div", { class: "thumbs" }, buttons) : null };
}

function eventRow(ev, rank, now, seen, timeField = "updated_at") {
  const meta = el("span", { class: "meta" },
    el("span", { text: placeName(ev) }),
    el("span", { text: formatAgo(ev[timeField] || ev.updated_at, now, lang) }),
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
    generatedAt ? el("p", { text: t("updated", lang, { t: formatUpdated(generatedAt, new Date(), lang) }) }) : null,
    el("p", { text: t("credits", lang) }));
}

function message(text) {
  return el("p", { class: "quiet", text });
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
  if (events.some((e) => e.location)) {
    worldMap(mapBox, events, (id) => { location.hash = `#/e/${encodeURIComponent(id)}`; });
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
      ? el("ul", { class: "list" }, data.events.map((ev) => eventRow(ev, 0, now, seen, "created_at")))
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
  const [today, all] = await Promise.all([
    getJSON("today.json").catch(() => ({ events: [] })),
    getJSON("all.json").catch(() => ({ events: [] })),
  ]);
  const more = nextEvents(ev.id, today.events, all.events, seen, 5);
  seen[ev.id] = ev.updated_at;
  store.set("seen", seen);

  const { hero, thumbs } = photos(ev.images);
  const summary = ev.summary[lang];
  app.replaceChildren(
    el("header", { class: "top" },
      el("a", { class: "back", href: "#/", text: `← ${t("back", lang)}` }),
      langButton()),
    el("article", { class: "detail" },
      hero,
      el("h1", { class: "detail-title", text: ev.title[lang] }),
      el("p", { class: "meta" },
        el("span", { text: placeName(ev) }),
        el("span", { text: formatAgo(ev.updated_at, now, lang) })),
      thumbs,
      summary ? el("p", { class: "summary", text: summary }) : null,
      summary && ev.summary.ai ? el("p", { class: "ai", text: t("aiSummary", lang) }) : null,
      el("h2", { class: "section", text: t("sources", lang) }),
      el("ul", { class: "list" }, ev.sources.filter((s) => safeUrl(s.url)).map((s) =>
        el("li", { class: "row src" },
          el("a", { href: safeUrl(s.url), target: "_blank", rel: "noopener noreferrer" },
            el("span", { class: "src-name", text: s.name }),
            el("span", { class: "src-title", text: s.title[lang] }),
            el("span", { class: "src-arrow", "aria-hidden": "true", text: "↗" }))))),
      ev.source_total > ev.sources.length
        ? el("p", { class: "src-total", text: t("sourceTotal", lang, { n: ev.source_total }) })
        : null),
    more.length
      ? el("section", { class: "more" },
        el("h2", { class: "section", text: t("moreNews", lang) }),
        el("ul", { class: "list" }, more.map((m) => eventRow(m, 0, now, seen))),
        el("p", { class: "end" }, el("a", { href: "#/all", text: t("seeAll", lang) })))
      : null,
    footer(null));
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
// A home-screen app can stay open for days: refresh when it comes back to the foreground.
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") {
    cache.clear();
    render();
  }
});
render();
