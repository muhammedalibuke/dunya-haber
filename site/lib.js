// Pure helpers (no DOM). Tested with node --test site/tests/.

export const STRINGS = {
  tr: {
    todayCount: "Bugün {n} önemli olay",
    end: "Bugünlük bu kadar.",
    seeAll: "Tümünü gör",
    allTitle: "Tüm olaylar",
    sources: "Kaynaklar",
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
  },
  en: {
    todayCount: "{n} key events today",
    end: "That's all for today.",
    seeAll: "See all",
    allTitle: "All events",
    sources: "Sources",
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
  },
};

export function t(key, lang, vars = {}) {
  let s = STRINGS[lang]?.[key] ?? STRINGS.tr[key] ?? key;
  if (key === "sourceCount" && lang === "en" && vars.n === 1) s = "{n} source";
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

export function formatToday(now, lang) {
  return new Intl.DateTimeFormat(lang === "tr" ? "tr-TR" : "en-GB", {
    timeZone: "Europe/Istanbul",
    day: "numeric",
    month: "long",
  }).format(now);
}

export function formatClock(iso, lang) {
  return new Intl.DateTimeFormat(lang === "tr" ? "tr-TR" : "en-GB", {
    timeZone: "Europe/Istanbul",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
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
