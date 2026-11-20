import { t, isNewDevelopment, formatAgo, formatToday, formatUpdated, formatClock, formatDateTime, safeUrl, dataDir, nextEvents, yearsAgo, formatDayMonth, lifeYears } from "./lib.js";
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

function shortPlace(ev) {
  const loc = ev.location;
  return loc && loc.level !== "country" && loc.name ? loc.name : ev.country.name[lang] || "";
}

function eventRow(ev, rank, now, seen, timeField = "updated_at") {
  const thumb = safeUrl(ev.thumb);
  return el("li", { class: "item" },
    el("a", { href: `#/e/${encodeURIComponent(ev.id)}` },
      el("span", { class: "top-row" },
        thumb ? el("img", { class: "item-thumb", src: thumb, alt: "", loading: "lazy", decoding: "async",
          referrerpolicy: "no-referrer", onerror: (e) => e.target.remove() }) : null,
        el("span", { class: "meta" },
          el("span", { class: "meta-line" },
            rank ? el("span", { class: "rank", text: String(rank) }) : null,
            el("span", { text: shortPlace(ev) })),
          el("span", { text: formatAgo(ev[timeField] || ev.updated_at, now, lang) }),
          isNewDevelopment(ev, seen)
            ? el("span", { class: "new", text: t("newDev", lang) })
            : el("span", { class: "count", text: t("sourceCount", lang, { n: ev.source_count }) }))),
      el("span", { class: "title", text: ev.title[lang] })));
}

// The story that has been in the news for days: what it is, when it last moved, what's new.
function featuredBox(f, now) {
  const href = `#/e/${encodeURIComponent(f.id)}`;
  const thumb = safeUrl(f.thumb);
  const today = formatToday(now, lang);
  const when = (iso) => (formatToday(new Date(iso), lang) === today ? "" : `${formatToday(new Date(iso), lang)} `)
    + formatClock(iso, lang);
  return el("section", { class: "featured", "aria-labelledby": "featured-title" },
    el("p", { class: "featured-kicker" },
      el("span", { class: "featured-days", text: t("trendingDays", lang, { n: f.days }) }),
      el("span", { text: t("sourceCount", lang, { n: f.source_count }) })),
    el("a", { class: "featured-head", href },
      thumb ? el("img", { class: "featured-thumb", src: thumb, alt: "", loading: "lazy", decoding: "async",
        referrerpolicy: "no-referrer", onerror: (e) => e.target.remove() }) : null,
      el("h2", { id: "featured-title", class: "featured-title", text: f.title[lang] })),
    el("p", { class: "featured-updated", text: t("updated", lang, { t: formatDateTime(f.updated_at, lang) }) }),
    f.developments?.length
      ? el("div", { class: "devs" },
        el("h3", { class: "devs-title", text: t("developments", lang) }),
        el("ol", { class: "devs-list" }, f.developments.map((d) => {
          const url = safeUrl(d.url);
          return el("li", { class: "dev" },
            el("p", { class: "dev-meta" },
              el("time", { class: "dev-time", datetime: d.published, text: when(d.published) }),
              el("span", { class: "dev-source", text: d.source })),
            el(url ? "a" : "span", url ? { class: "dev-title", href: url, target: "_blank", rel: "noopener noreferrer" }
              : { class: "dev-title" }, d.title[lang]),
            d.detail?.[lang] ? el("p", { class: "dev-detail", text: d.detail[lang] }) : null);
        })))
      : null,
    el("a", { class: "featured-more", href, text: t("readFull", lang) }));
}

// Date and time in the masthead, kept current while the page is open.
let clockTimer = null;
function mastheadClock(now) {
  const node = el("time", { class: "masthead-date", text: formatDateTime(now, lang) });
  clearInterval(clockTimer);
  clockTimer = setInterval(() => {
    if (!node.isConnected) { clearInterval(clockTimer); return; }
    node.textContent = formatDateTime(new Date(), lang);
  }, 15000);
  return node;
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
    el("header", { class: "masthead" },
      el("h1", { class: "masthead-name", text: "Nunti Orbis" }),
      el("div", { class: "masthead-line" },
        mastheadClock(now),
        el("a", { class: "history-link", href: "#/tarih", text: t("historyLink", lang) }),
        langButton())),
    data.featured ? featuredBox(data.featured, now) : null,
    mapBox,
    ...(events.length
      ? [
        el("p", { class: "lede", text: t("todayCount", lang, { n: events.length }) }),
        el("ol", { class: "grid" }, events.map((ev, i) => eventRow(ev, i + 1, now, seen))),
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
      ? el("ul", { class: "grid" }, data.events.map((ev) => eventRow(ev, 0, now, seen, "created_at")))
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
        el("ul", { class: "grid" }, more.map((m) => eventRow(m, 0, now, seen))),
        el("p", { class: "end" }, el("a", { href: "#/all", text: t("seeAll", lang) })))
      : null,
    footer(null));
}

// "Tarihte bugün": world events and deaths on today's date (from Wikipedia)
let historyTab = "events";
async function viewHistory() {
  const now = new Date();
  let data = null;
  try { data = await getJSON("history.json"); } catch (e) { console.warn(e); }
  const top = [
    el("div", { class: "hist-top" },
      el("a", { class: "back", href: "#/", text: `← ${t("back", lang)}` }),
      langButton()),
    el("p", { class: "hist-kicker", text: t("historyLink", lang) }),
    el("h1", { class: "hist-date", text: data ? formatDayMonth(data.date, lang) : formatToday(now, lang) }),
    el("p", { class: "hist-sub", text: t("historySub", lang) }),
  ];
  if (!data) {
    app.replaceChildren(el("main", { class: "hist" }, ...top, message(t("historyNotReady", lang))));
    return;
  }
  const listBox = el("div", { class: "hist-list" });
  const tabs = ["events", "deaths"].filter((k) => data[k]?.length);
  if (!tabs.includes(historyTab)) historyTab = tabs[0] || "events";
  const tabKey = { events: "hEvents", deaths: "hDeaths" };
  const tabBar = el("div", { class: "hist-tabs", role: "group" }, tabs.map((k) => el("button", {
    class: "hist-tab", type: "button", "aria-pressed": String(k === historyTab), text: t(tabKey[k], lang),
    onclick: () => { historyTab = k; tabBar.querySelectorAll("button").forEach((b, i) => b.setAttribute("aria-pressed", String(tabs[i] === k))); fill(); },
  })));
  const ago = (y) => (y > 0 ? t("yearsAgo", lang, { n: yearsAgo(y, now) }) : "");
  const img = (src, cls) => (safeUrl(src) ? el("img", { class: cls, src: safeUrl(src), alt: "", loading: "lazy",
    decoding: "async", referrerpolicy: "no-referrer", onerror: (e) => e.target.remove() }) : null);
  const wiki = (it) => (safeUrl(it.url) ? el("a", { class: "hist-more", href: safeUrl(it.url), target: "_blank",
    rel: "noopener noreferrer", text: t("readWiki", lang) }) : null);
  const life = (it) => (lifeYears(it, historyTab) ? el("p", { class: "hist-life", text: lifeYears(it, historyTab) }) : null);
  const ctx = (it) => (it.extract?.[lang] ? el("details", { class: "hist-ctx" },
    el("summary", { text: t("whatHappened", lang) }),
    el("p", { text: it.extract[lang] })) : null);
  function fill() {
    const items = (data[historyTab] || []).map((it, i) => ({ ...it, id: `h${i}` }));
    const [lead, ...rest] = items;
    const located = historyTab === "events" ? items.filter((it) => it.location) : [];
    const mapBox = located.length ? el("div", { class: "map hist-map" }) : null;
    listBox.replaceChildren(
      mapBox,
      lead ? el("section", { class: "hist-lead", id: lead.id },
        img(lead.image || lead.thumb, "hist-lead-img"),
        el("p", { class: "hist-year" }, el("b", { text: String(lead.year) }), el("span", { text: ago(lead.year) })),
        el("p", { class: "hist-lead-text", text: lead.text[lang] }),
        life(lead),
        ctx(lead),
        wiki(lead)) : null,
      el("ol", { class: "hist-tl" }, rest.map((it) => el("li", { id: it.id },
        el("div", { class: "hist-y" }, String(it.year), el("span", { class: "hist-ago", text: ago(it.year) })),
        el("div", { class: "hist-body" },
          el("div", { class: "hist-row" },
            el("div", { class: "hist-main" }, el("p", { class: "hist-text", text: it.text[lang] }), life(it)),
            img(it.thumb, "hist-thumb")),
          ctx(it),
          wiki(it))))));
    if (mapBox) {
      worldMap(mapBox, located, (id) => {
        const target = document.getElementById(id);
        target?.querySelector("details")?.setAttribute("open", "");
        target?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, { numbered: false, label: (e) => String(e.year), aria: (e) => `${e.year}: ${e.text[lang]}` });
    }
  }
  // observances get a box of their own after the list
  const daysBox = data.holidays?.length
    ? el("section", { class: "hist-days", "aria-labelledby": "hist-days-title" },
      el("h2", { id: "hist-days-title", class: "hist-days-title", text: t("holidaysTitle", lang) }),
      el("ul", { class: "hist-days-list" }, data.holidays.map((h) => el("li", {},
        safeUrl(h.url)
          ? el("a", { href: safeUrl(h.url), target: "_blank", rel: "noopener noreferrer", text: h.text[lang] })
          : el("span", { text: h.text[lang] })))))
    : null;
  app.replaceChildren(el("main", { class: "hist" }, ...top, tabBar, listBox, daysBox,
    el("p", { class: "hist-src", text: t("historySource", lang) })));
  fill(); // after the page is on screen: the map measures its box
}

async function render() {
  document.documentElement.lang = lang;
  const hash = location.hash || "#/";
  try {
    if (hash.startsWith("#/e/")) await viewEvent(decodeURIComponent(hash.slice(4)));
    else if (hash === "#/all") await viewAll();
    else if (hash === "#/tarih") await viewHistory();
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
