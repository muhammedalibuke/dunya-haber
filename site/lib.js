// Pure helpers (no DOM). Tested with node --test site/tests/.

export const STRINGS = {
  tr: {
    todayCount: "Bugün {n} önemli olay",
    end: "Bugünlük bu kadar.",
    seeAll: "Son haberler",
    allTitle: "Son haberler",
    sources: "Kaynaklar",
    moreNews: "Diğer haberler",
    sourceTotal: "Bu olayı toplam {n} kaynak haberleştirdi.",
    sourceCount: "{n} kaynak",
    newDev: "yeni gelişme",
    quiet: "Şu an öne çıkan bir olay yok. Biraz sonra tekrar bak.",
    updated: "Son güncelleme: {t}",
    aiSummary: "Yapay zekâ özeti",
    back: "Geri",
    loadError: "Haberler yüklenemedi. İnternet bağlantını kontrol edip sayfayı yenile.",
    notFound: "Bu olay artık listede değil.",
    credits: "Haberler ilgili kaynaklara aittir. Yer verisi: GeoNames (CC-BY 4.0). Harita: Natural Earth.",
    photo: "Fotoğraf: {s}",
    langSwitch: "EN",
    langSwitchLabel: "Switch to English",
    trendingDays: "{n} gündür gündemde",
    developments: "Son gelişmeler",
    readFull: "Haberin tamamı",
    historyLink: "Tarihte bugün",
    historySub: "Dünyada bu tarihte yaşananlar",
    hEvents: "Olaylar",
    hBirths: "Doğumlar",
    hDeaths: "Ölümler",
    yearsAgo: "{n} yıl önce",
    readWiki: "Vikipedi'de oku",
    historySource: "Kaynak: İngilizce Vikipedi, \"On this day\". Metinler CC BY-SA lisanslıdır; Türkçeleri otomatik çeviridir.",
    historyNotReady: "Bugünün listesi henüz hazır değil. Birazdan tekrar bak.",
  },
  en: {
    todayCount: "{n} key events today",
    end: "That's all for today.",
    seeAll: "Latest news",
    allTitle: "Latest news",
    sources: "Sources",
    moreNews: "More stories",
    sourceTotal: "{n} outlets covered this event in total.",
    sourceCount: "{n} sources",
    newDev: "new development",
    quiet: "Nothing stands out right now. Check back a little later.",
    updated: "Last updated: {t}",
    aiSummary: "AI summary",
    back: "Back",
    loadError: "Couldn't load the news. Check your connection and refresh.",
    notFound: "This event is no longer listed.",
    credits: "News belongs to the respective sources. Places: GeoNames (CC-BY 4.0). Map: Natural Earth.",
    photo: "Photo: {s}",
    langSwitch: "TR",
    langSwitchLabel: "Türkçeye geç",
    trendingDays: "In the news for {n} days",
    developments: "Latest developments",
    readFull: "Full story",
    historyLink: "On this day",
    historySub: "What happened in the world on this date",
    hEvents: "Events",
    hBirths: "Births",
    hDeaths: "Deaths",
    yearsAgo: "{n} years ago",
    readWiki: "Read on Wikipedia",
    historySource: "Source: English Wikipedia, \"On this day\". Text available under CC BY-SA.",
    historyNotReady: "Today's list isn't ready yet. Check back shortly.",
  },
};

export function t(key, lang, vars = {}) {
  let s = STRINGS[lang]?.[key] ?? STRINGS.tr[key] ?? key;
  if (key === "sourceCount" && lang === "en" && vars.n === 1) s = "{n} source";
  if (key === "yearsAgo" && lang === "en" && vars.n === 1) s = "{n} year ago";
  return s.replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? ""));
}

export function isNewDevelopment(ev, seen) {
  const last = seen?.[ev.id];
  return Boolean(last) && Date.parse(ev.updated_at) > Date.parse(last);
}

export function formatAgo(iso, now, lang) {
  const min = Math.max(0, Math.round((now - Date.parse(iso)) / 60000));
  const tr = lang === "tr";
  if (min < 5) return tr ? "az önce" : "just now";
  if (min < 60) return tr ? `${min} dk önce` : `${min}m ago`;
  const h = Math.floor(min / 60);
  if (h < 24) return tr ? `${h} sa önce` : `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d === 1) return tr ? "dün" : "yesterday";
  return tr ? `${d} gün önce` : `${d}d ago`;
}

export function formatToday(now, lang, withWeekday = false) {
  return new Intl.DateTimeFormat(lang === "tr" ? "tr-TR" : "en-GB", {
    timeZone: "Europe/Istanbul",
    day: "numeric",
    month: "long",
    ...(withWeekday ? { weekday: "long" } : {}),
  }).format(now);
}

export function formatClock(iso, lang) {
  return new Intl.DateTimeFormat(lang === "tr" ? "tr-TR" : "en-GB", {
    timeZone: "Europe/Istanbul",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

export function formatDateTime(iso, lang) {
  return `${formatToday(new Date(iso), lang, true)}, ${formatClock(iso, lang)}`;
}

// births: "1889 – 1953", deaths: "1952 – 2024"; nothing when the other year is unknown
export function lifeYears(it, kind) {
  if (kind === "deaths" && it.born) return `${it.born} – ${it.year}`;
  if (kind === "births" && it.died) return `${it.year} – ${it.died}`;
  return "";
}

export function yearsAgo(year, now) {
  return now.getFullYear() - year;
}

// "2026-11-20" → "20 Kasım" (the date itself, not shifted by the reader's time zone)
export function formatDayMonth(isoDate, lang) {
  return new Intl.DateTimeFormat(lang === "tr" ? "tr-TR" : "en-GB", { day: "numeric", month: "long", timeZone: "UTC" })
    .format(new Date(`${isoDate}T12:00:00Z`));
}

export function safeUrl(u) {
  if (typeof u !== "string") return null;
  const s = u.trim();
  return /^https?:\/\//i.test(s) ? s : null;
}

export function dataDir(param) {
  return typeof param === "string" && /^[\w-]+$/.test(param) ? param : "data";
}

export function formatUpdated(iso, now, lang) {
  const day = (d) => formatToday(d, lang);
  const clock = formatClock(iso, lang);
  return day(new Date(iso)) === day(now) ? clock : `${day(new Date(iso))} ${clock}`;
}

// Stories to offer after an event page: newest first, unread before read.
export function nextEvents(currentId, today, all, seen, n = 5) {
  const pool = [];
  const ids = new Set([currentId]);
  for (const ev of [...(today || []), ...(all || [])]) {
    if (ids.has(ev.id)) continue;
    ids.add(ev.id);
    pool.push(ev);
  }
  pool.sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at));
  const unseen = pool.filter((ev) => !seen?.[ev.id]);
  const already = pool.filter((ev) => seen?.[ev.id]);
  return [...unseen, ...already].slice(0, n);
}
