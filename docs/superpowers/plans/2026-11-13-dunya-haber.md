# Dünya Haber Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A zero-cost personal news app that groups world news into events, translates them to TR/EN, shows a calm "today" list with a world map, and links each source's original article.

**Architecture:** A Python pipeline runs every 30 minutes on GitHub Actions: fetch RSS → embed → cluster into events → topic/location/translation → rank → write static JSON. State persists as JSON on an orphan `data` branch (force-pushed, one commit). A framework-free static site on GitHub Pages reads the JSON and draws maps from bundled Natural Earth TopoJSON.

**Tech Stack:** Python 3.12, feedparser, httpx, PyYAML, numpy, sentence-transformers (`paraphrase-multilingual-MiniLM-L12-v2`, Apache-2.0), argostranslate, geonamescache, babel, pytest · Vanilla HTML/CSS/JS (ES modules), d3-geo + topojson-client (vendored), node:test · mapshaper (build-time only) · GitHub Actions + Pages.

**Spec:** `docs/superpowers/specs/2026-11-13-dunya-haber-design.md`

## Global Constraints

- Cost: zero. No paid servers, no paid APIs, no map tile services.
- Repo: public, `github.com/muhammedalibuke/dunya-haber`. Secrets only in GitHub Secrets.
- Licenses: every model/dataset must allow later commercial use. No NLLB or other CC-BY-NC models. GeoNames (CC-BY 4.0) and Natural Earth (public domain) are credited in the site footer.
- Content: never store or show full article text. Only title, the feed's own short description (or our summary), source name, link.
- Languages: UI and content in `tr` and `en`; default `tr`.
- Update interval: 30 minutes. "Today" is computed in `Europe/Istanbul`.
- Event lifecycle: open while it received an article in the last 48 h; deleted 7 days after its last article.
- Today list: 5–10 events, sport and entertainment excluded. All list: everything.
- No country gets extra weight; per-country source contribution has diminishing returns.
- Lists show no images. Detail shows one image only if a feed supplied one; otherwise no image area at all.
- Map: red point at city/region level; ambiguous names fall back to country level (country tinted pale red); unknown → not on map.
- Card-style list design with two-line summaries is forbidden (user rejected it).
- AI summary (Gemini) is off unless `GEMINI_API_KEY` is set; failures fall back silently.

## Review Focus

1. A feed returns malformed XML, HTML error page, missing dates or future dates → that feed is skipped or the date is clamped to fetch time; the run continues. (Task 3)
2. The same story URL arrives again with tracking params (`utm_*`, `fbclid`) or `http`/`https` variants → treated as the same article, never duplicated in an event. (Task 3)
3. Place names that are also common words or ambiguous ("Nice", "Mobile", "Reading", "Georgia", "Washington") → no wrong red point; country-level or no location. (Task 6)
4. Titles/descriptions containing HTML or `<script>` → stored as plain text and rendered with `textContent`; nothing executes. (Tasks 3, 10)
5. First run with no `data` branch, or a quiet hour with zero events for "today" → pipeline creates empty state; UI shows a calm message, never a blank screen. (Tasks 1, 9, 10)

---

## File Structure

```
pyproject.toml                     deps + pytest config
config/sources.yaml                feed list
config/topics.yaml                 topic prototype phrases + URL/tag keywords
config/place_stoplist.txt          place names never matched
pipeline/models.py                 dataclasses
pipeline/state.py                  load/save/prune JSON state
pipeline/sources.py                load + validate sources.yaml
pipeline/collect.py                fetch + parse feeds, canonical URLs, cleaning
pipeline/embed.py                  Embedder protocol + sentence-transformers impl
pipeline/cluster.py                assign articles to events
pipeline/topics.py                 sport / entertainment / general
pipeline/geo.py                    gazetteer + event location
pipeline/translate.py              Translator protocol + Argos impl + cache
pipeline/summarize.py              default summary, optional Gemini
pipeline/rank.py                   score + today selection
pipeline/publish.py                site JSON
pipeline/run.py                    orchestration entry point
scripts/check_sources.py           live feed health report (runs in Actions)
scripts/build_gazetteer.py         geonamescache + NE admin1 → data/gazetteer.json.gz
scripts/build_map.sh               Natural Earth → site/map/*.topo.json
site/index.html, style.css, app.js, lib.js, map.js, manifest.webmanifest, vendor/
tests/…                            pytest; tests/fixtures/*.xml; site/tests/*.test.mjs
.github/workflows/update.yml
```

---

### Task 1: Skeleton, models, state store

**Files:**
- Create: `pyproject.toml`, `pipeline/__init__.py`, `pipeline/models.py`, `pipeline/state.py`
- Test: `tests/test_state.py`

**Interfaces:**
- Produces:
  - `Source(id: str, name: str, url: str, country: str, lang: str, region: str)`; `country` is ISO-3166 alpha-2 upper, `lang` ISO-639-1, `region` ∈ `{"africa","americas","asia","europe","middle_east","oceania"}`
  - `Article(id: str, url: str, title: str, description: str, source_id: str, source_name: str, country: str, lang: str, published: datetime, image_url: str | None, tags: list[str], topic: str = "general", title_tr: str | None = None, title_en: str | None = None)`; `id = sha1(canonical_url)[:16]`
  - `Location(level: Literal["city","region","country"], name: str, lat: float, lon: float, country: str)`
  - `Event(id: str, article_ids: list[str], centroid: np.ndarray, created_at: datetime, updated_at: datetime, topic: str = "general", location: Location | None = None, summary_tr: str = "", summary_en: str = "", summary_ai: bool = False)`
  - `State(articles: dict[str, Article], events: dict[str, Event], translations: dict[str, dict[str, str]])`
  - `load_state(dir: Path) -> State` (missing dir/files → empty State), `save_state(state: State, dir: Path) -> None`, `prune(state: State, now: datetime) -> None`
- All datetimes are timezone-aware UTC. Centroids are float32, L2-normalized, serialized as base64 of float16 bytes.

- [ ] **Step 1: Write failing tests**
  - `test_load_missing_dir_returns_empty_state`: `load_state(tmp/"nope")` → all three dicts empty.
  - `test_roundtrip`: State with one Article, one Event (centroid 384-dim random normalized), one translation → save → load → equal fields; `np.allclose(centroid, loaded, atol=1e-3)`.
  - `test_prune_deletes_events_7_days_after_last_article`: event `updated_at = now - 7d - 1min` removed together with its articles; event at `now - 6d` kept.
  - `test_prune_drops_orphan_translations_not_needed`: translations whose key isn't referenced by any kept article title/description are dropped.
- [ ] **Step 2: Run** `pytest tests/test_state.py -v` → FAIL (import error).
- [ ] **Step 3: Implement** models and state. Files: `articles.json`, `events.json`, `translations.json` under `dir`. Translation cache key: `sha1(f"{src}|{tgt}|{text}")[:20]`, value `{"text": translated}`; expose `cache_key(text, src, tgt) -> str` in `state.py`.
- [ ] **Step 4: Run** `pytest tests/test_state.py -v` → PASS.
- [ ] **Step 5: Commit** `feat: models and JSON state store`

### Task 2: Source list

**Files:**
- Create: `config/sources.yaml`, `pipeline/sources.py`, `scripts/check_sources.py`
- Test: `tests/test_sources.py`

**Interfaces:**
- Consumes: `Source` (Task 1)
- Produces: `load_sources(path: Path) -> list[Source]` (raises `ValueError` naming the bad entry on missing fields, bad country/lang/region, duplicate id or url)

- [ ] **Step 1: Write failing tests**
  - `test_load_sources_validates_fields` (tmp yaml with bad country `"XX"` → ValueError containing the id).
  - `test_real_list_coverage`: on `config/sources.yaml`: ≥150 sources, ≥100 distinct countries, every region ≥10 sources, includes `TR`, no duplicate ids/urls.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** `load_sources`; country codes validated against `geonamescache` countries.
- [ ] **Step 4: Write `config/sources.yaml`**: international wires/broadcasters (BBC World, Al Jazeera, DW, France 24, NHK World, AA English, Reuters-equivalent feeds where public RSS exists, etc.) plus each country's leading outlets with public RSS; prefer "world/general/top stories" feeds over section feeds; English-language national outlets preferred where available (better translation). Each entry: `id, name, url, country, lang, region`.
- [ ] **Step 5: Write `scripts/check_sources.py`**: fetches every feed (Task 3 fetcher), prints a table `id | status | items | newest age`, exits 0 always. Run in Actions via `workflow_dispatch`; dead feeds get replaced before Task 13 goes live.
- [ ] **Step 6: Run** `pytest tests/test_sources.py -v` → PASS.
- [ ] **Step 7: Commit** `feat: world source list with validation`

### Task 3: Collector and cleaning

**Files:**
- Create: `pipeline/collect.py`, `tests/fixtures/{rss_basic.xml, atom_basic.xml, broken.html, media_variants.xml}`
- Test: `tests/test_collect.py`

**Interfaces:**
- Consumes: `Source`, `Article`
- Produces:
  - `canonical_url(url: str) -> str` (lowercase scheme+host, `http`→`https`, strip `utm_*`, `fbclid`, `gclid`, `ref`, fragment, trailing slash)
  - `clean_text(html: str, max_chars: int = 600) -> str` (strip tags, unescape entities, collapse whitespace)
  - `parse_feed(content: bytes, source: Source, fetched_at: datetime) -> list[Article]`
  - `fetch_all(sources: list[Source], get: Callable[[str], bytes], now: datetime, workers: int = 16) -> tuple[list[Article], dict[str, str]]` → (articles deduped by id, failures `{source_id: reason}`)
  - `http_get(url: str) -> bytes` (httpx, timeout 15 s, follow redirects, UA `DunyaHaber/1.0 (+repo url)`, max 5 MB)

- [ ] **Step 1: Write failing tests**
  - `test_canonical_url_strips_tracking`: `"http://Example.com/a/?utm_source=x&id=3#top"` → `"https://example.com/a?id=3"`.
  - `test_parse_rss_basic`: titles/urls/dates parsed; `description` has no tags; `<script>` in title becomes plain text without the script body.
  - `test_parse_atom_basic`.
  - `test_image_from_media_content_thumbnail_enclosure`: each variant in `media_variants.xml` yields `image_url`; non-image enclosure (audio) → None.
  - `test_missing_or_future_date_clamped_to_fetched_at`.
  - `test_broken_feed_reported_not_raised`: `fetch_all` with one source returning `broken.html` and one good → articles from good one, `failures` has the broken id.
  - `test_duplicate_urls_across_sources_deduped`.
  - `test_tags_collected`: feed `<category>` values lowercased into `tags`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** with feedparser; entries with empty title or URL dropped.
- [ ] **Step 4: Run** `pytest tests/test_collect.py -v` → PASS.
- [ ] **Step 5: Commit** `feat: feed collection and cleaning`

### Task 4: Embedding and clustering

**Files:**
- Create: `pipeline/embed.py`, `pipeline/cluster.py`, `tests/fakes.py`
- Test: `tests/test_cluster.py`

**Interfaces:**
- Consumes: `Article`, `Event`
- Produces:
  - `class Embedder(Protocol): def encode(self, texts: list[str]) -> np.ndarray` (rows L2-normalized float32)
  - `SentenceEmbedder(model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")`
  - `embed_text(a: Article) -> str` = `a.title + ". " + a.description[:200]`
  - `assign(events: dict[str, Event], articles: list[Article], vectors: np.ndarray, now: datetime, threshold: float = 0.72, window_hours: int = 48) -> set[str]` → ids of events created or updated
  - `tests/fakes.py`: `FakeEmbedder(mapping: dict[str, list[float]])` returns the vector of the first keyword found in the text (normalized), else a hash-seeded random unit vector; `FakeTranslator` (Task 7) lives here too.
- Constants in `cluster.py`: `CLUSTER_THRESHOLD = 0.72`, `OPEN_WINDOW_HOURS = 48`.

- [ ] **Step 1: Write failing tests**
  - `test_similar_articles_join_one_event` (two "quake" articles, different languages/sources → one event, 2 article ids).
  - `test_dissimilar_articles_make_two_events`.
  - `test_article_joins_existing_open_event_and_bumps_updated_at`.
  - `test_closed_event_not_reused`: matching event with `updated_at = now - 49h` → new event created.
  - `test_same_article_id_never_added_twice`.
  - `test_centroid_is_normalized_running_mean`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** `assign`: process articles in `published` order; cosine vs open-event centroids; best ≥ threshold → append + `centroid = normalize(c*n + v)`; else new event `id = article.id`.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: multilingual event clustering`

### Task 5: Topic classification

**Files:**
- Create: `config/topics.yaml`, `pipeline/topics.py`
- Test: `tests/test_topics.py`

**Interfaces:**
- Produces:
  - `load_topic_config(path: Path) -> TopicConfig` with `url_keywords: dict[str, list[str]]`, `tag_keywords: dict[str, list[str]]`, `prototypes: dict[str, list[str]]` for topics `sport`, `entertainment`
  - `prototype_vectors(cfg: TopicConfig, embedder: Embedder) -> dict[str, np.ndarray]` (mean of phrase vectors, normalized)
  - `article_topic(a: Article, vector: np.ndarray, cfg: TopicConfig, protos: dict[str, np.ndarray], min_sim: float = 0.45) -> str` → `"sport" | "entertainment" | "general"`; checked in order: URL path segment keywords, then feed tags, then the most similar prototype if its cosine ≥ `min_sim`; otherwise `"general"`
  - `event_topic(topics: list[str]) -> str` → a non-general topic only if it is >50 % of the event's articles
- `topics.yaml` keywords include at least: sport `sport, sports, spor, deportes, esportes, football, futbol, soccer, nba, f1, tennis, cricket`; entertainment `entertainment, showbiz, celebrity, magazin, gossip, unluler, tv-show`. Culture/arts stays `general`.

- [ ] **Step 1: Write failing tests**: URL `/sport/football/…` → sport; tag `"Magazin"` → entertainment; neither, vector near sport prototype (FakeEmbedder) → sport; plain politics → general; `event_topic(["sport","general","general"])` → general; `["sport","sport","general"]` → sport.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: sport/entertainment topic tagging`

### Task 6: Gazetteer and event location

**Files:**
- Create: `scripts/build_gazetteer.py`, `data/gazetteer.json.gz` (generated, committed), `config/place_stoplist.txt`, `pipeline/geo.py`
- Test: `tests/test_geo.py`

**Interfaces:**
- Produces:
  - `Place(name: str, level: Literal["city","region","country"], lat: float, lon: float, country: str, population: int)`
  - `Gazetteer.load(path: Path, stoplist: Path) -> Gazetteer`; `Gazetteer.from_entries(entries: list[Place]) -> Gazetteer` (for tests)
  - `Gazetteer.find(text: str) -> list[list[Place]]` → one candidate list per matched name; matches 1–3-word spans that start with an uppercase letter, longest match wins, names in the stoplist never match
  - `locate_event(titles: list[str], source_countries: list[str], gaz: Gazetteer) -> Location | None`
  - `country_of_event(location: Location | None, source_countries: list[str]) -> str` (location's country, else most common source country)
- Gazetteer content: countries (geonamescache names + common English alt names + demonyms not included), cities with population ≥ 100 000 (geonamescache, English/ASCII names + alternate names that are ASCII and ≥4 chars), first-level regions worldwide from Natural Earth `ne_10m_admin_1_states_provinces` (`name`, `name_en`, `iso_a2`, `latitude`, `longitude`). Country entries use the country's capital-independent centroid from Natural Earth admin-0.
- Stoplist (initial, exact names only, one per line): `Nice, Mobile, Reading, Split, Bath, Orange, Victoria, March, Best, Of, Batman, Van, Mercedes, Union, Independence, Liberty, Concord`.

- [ ] **Step 1: Write failing tests** (all with `Gazetteer.from_entries`):
  - `test_unique_city_gives_city_level`: "Earthquake hits Kobe" → city Kobe, JP.
  - `test_us_state_gives_region_level`: "Wildfires spread across Oregon" → region Oregon, US.
  - `test_ambiguous_name_resolved_by_other_country_in_titles`: "Georgia" with titles also mentioning "Tbilisi" → country GE; with "Atlanta" → region Georgia US.
  - `test_ambiguous_unresolved_falls_back_to_country_or_none`: "Washington" only, source countries mixed → `None`; if all candidates share one country → country level.
  - `test_stoplisted_word_never_matches`: "Nice weather in Mobile" → None.
  - `test_most_frequent_place_across_titles_wins`.
  - `test_country_of_event_fallback_to_sources`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** `geo.py`. Resolution rule per event: collect all matches over titles (use `title_en` when present, else original); filter candidates by countries mentioned at country level in the same titles; if none mentioned, by majority source country; a match with exactly one remaining candidate is resolved; pick the resolved place matched most often (ties → more specific level, then larger population); if nothing resolved but every candidate of the most frequent name shares a country → country level; else None.
- [ ] **Step 4: Implement `scripts/build_gazetteer.py`** (downloads NE admin-0/admin-1 GeoJSON from `raw.githubusercontent.com/nvkelso/natural-earth-vector`), run it, commit the `.json.gz` (<5 MB).
- [ ] **Step 5: Run** `pytest tests/test_geo.py -v` → PASS.
- [ ] **Step 6: Commit** `feat: offline gazetteer and event location`

### Task 7: Translation and default summary

**Files:**
- Create: `pipeline/translate.py`, `pipeline/summarize.py`
- Test: `tests/test_translate.py`, `tests/test_summarize.py`

**Interfaces:**
- Consumes: `State.translations`, `cache_key`
- Produces:
  - `class Translator(Protocol): def translate(self, text: str, src: str, tgt: str) -> str | None`
  - `ArgosTranslator(install_dir: Path)` — installs needed packages from the Argos index on first use (cached by Actions), pivots via `en`; returns None for unsupported pairs
  - `translate_cached(text: str, src: str, tgt: str, cache: dict, tr: Translator) -> str` → original text when `src == tgt` or translation is None; caches successful results only
  - `translate_articles(articles: list[Article], cache: dict, tr: Translator) -> None` (fills `title_tr`, `title_en`)
  - `default_summary(description: str, max_sentences: int = 4, max_chars: int = 420) -> str`
- [ ] **Step 1: Write failing tests**: same-language passthrough with zero translator calls; second call served from cache; unsupported pair returns original and is not cached; `translate_articles` fills both fields (FakeTranslator prefixes `"[tr]"`); `default_summary` cuts at sentence boundary ≤ 420 chars, never mid-word, strips "Read more"/"Devamı için tıklayın" tails, returns "" for empty input.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: cached offline translation and default summaries`

### Task 8: Ranking and today selection

**Files:**
- Create: `pipeline/rank.py`
- Test: `tests/test_rank.py`

**Interfaces:**
- Produces:
  - `score(event: Event, articles: dict[str, Article], now: datetime) -> float`
  - `select_today(events: dict[str, Event], articles: dict[str, Article], now: datetime, min_n: int = 5, max_n: int = 10, rel_cutoff: float = 0.4) -> list[str]`
- Formula (fixed here so it's testable):
  ```
  per_country = Counter(distinct source_id per country)
  base = Σ_country (1 + log2(n_c))          # diminishing per country, every country counts ≥1
  freshness = exp(-age_hours / 12), age from event.updated_at
  score = base * freshness
  ```
- Selection: candidates = events with `topic == "general"` and `updated_at ≥ now - 24h` and ≥ 2 distinct sources; sort by score desc; take top `max_n`; drop those below `rel_cutoff × top_score` but never below `min_n` items (if that many candidates exist).
- [ ] **Step 1: Write failing tests**: 6 sources from 6 countries beats 12 sources from 1 country; sport event never selected; event older than 24 h never selected; single-source event never selected; returns ≤10; when only 3 candidates → 3; cutoff keeps at least 5 when ≥5 candidates.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: country-balanced ranking and today selection`

### Task 9: Publishing and pipeline run

**Files:**
- Create: `pipeline/publish.py`, `pipeline/run.py`
- Test: `tests/test_publish.py`, `tests/test_run_e2e.py`

**Interfaces:**
- Consumes: everything above
- Produces:
  - `build_site_data(state: State, today_ids: list[str], now: datetime) -> dict[str, object]` keyed by relative path:
    - `today.json`: `{"generated_at", "events": [EventSummary]}`
    - `all.json`: `{"generated_at", "events": [EventSummary]}` (open events, `updated_at` desc)
    - `events/<id>.json`: `{"id","title":{"tr","en"},"country":{"code","name":{"tr","en"}},"created_at","updated_at","summary":{"tr","en","ai"},"image":{"url","source"}|null,"location":{"level","name","lat","lon","country"}|null,"sources":[{"name","url","published","title":{"orig","tr","en"}}]}`
    - `EventSummary = {"id","title":{"tr","en"},"country":{…},"source_count","updated_at","topic","location":{…}|null}`
  - Event title = `title_tr`/`title_en` of the earliest-published article from an English-language source if the event has one (best translation quality), else of the earliest-published article.
  - Image = first article (by `published`) with `image_url`; `source` = its source name.
  - Country names via `babel.Locale("tr"/"en").territories`.
  - `write_site_data(out_dir: Path, files: dict[str, object]) -> None` (clears `out_dir/events/` first, writes UTF-8 JSON, `ensure_ascii=False`)
  - `run(state_dir: Path, out_dir: Path, now: datetime, sources: list[Source], get, embedder: Embedder, translator: Translator, gaz: Gazetteer, topic_cfg: TopicConfig) -> RunReport` and `main()` CLI (`python -m pipeline.run --state state --out site/data`) wiring the real implementations.
  - Order inside `run`: load → fetch → drop already-known article ids → embed → assign → topics (article + event) → translate new articles → for touched events: location, summaries → prune → rank/select → save state → write site data. `RunReport(new_articles: int, touched_events: int, failures: dict[str,str], today: int)` printed as one log line.
- [ ] **Step 1: Write failing tests**
  - `test_build_site_data_shapes` (keys and types exactly as above; no `description` full text beyond summary).
  - `test_event_without_image_has_null_image`.
  - `test_e2e_two_runs`: fixtures of 3 feeds (fake `get`), FakeEmbedder/FakeTranslator, small gazetteer. Run 1 → events written, `today.json` valid. Run 2 with one new matching article → same event id, `updated_at` advanced, `source_count` +1, no duplicate.
  - `test_e2e_first_run_empty_state_and_no_today`: all feeds fail → `today.json` has `events: []`, files still written, no exception.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** `pytest -v` (whole suite) → PASS.
- [ ] **Step 5: Commit** `feat: site data publishing and pipeline orchestration`

### Task 10: Site — lists and detail

**Files:**
- Create: `site/index.html`, `site/style.css`, `site/app.js`, `site/lib.js`, `site/manifest.webmanifest`, `site/icon.svg`, `site/tests/lib.test.mjs`, `site/dev-data/` (sample JSON for local preview, generated by running Task 9 e2e fixtures)

**Interfaces:**
- Consumes: JSON shapes from Task 9
- Produces (`lib.js`, pure, no DOM):
  - `isNewDevelopment(eventSummary, seen: Record<string,string>) -> boolean` → true only if `seen[id]` exists and `updated_at > seen[id]`
  - `formatAgo(iso: string, now: Date, lang: "tr"|"en") -> string` ("2 sa önce" / "2h ago", "az önce"/"just now" < 5 min, "dün"/"yesterday")
  - `formatToday(now: Date, lang) -> string` in `Europe/Istanbul` ("13 Kasım" / "13 November")
  - `STRINGS: {tr: {...}, en: {...}}` with keys `todayCount` ("Bugün {n} önemli olay"), `end` ("Bugünlük bu kadar"), `seeAll` ("Tümünü gör"), `allTitle` ("Tüm olaylar"), `sources` ("Kaynaklar"), `sourceCount` ("{n} kaynak"), `newDev` ("yeni gelişme"), `quiet` ("Şu an öne çıkan bir olay yok."), `updated` ("Son güncelleme: {t}"), `aiSummary` ("Yapay zekâ özeti"), `back` ("Geri")
- Routes (hash): `#/` today, `#/all`, `#/e/<id>`. `localStorage` keys `lang`, `seen` (wrapped in try/catch). Opening a detail sets `seen[id] = updated_at`.
- Rendering rules: every piece of feed text via `textContent`; links `target="_blank" rel="noopener noreferrer"`; list rows = meta line (country · ago) small muted, title, `{n} kaynak` muted; no images in lists; numbered today list; footer credits GeoNames (CC-BY 4.0), Natural Earth, and "Haberler ilgili kaynaklara aittir".
- Visual: single column max-width 560 px, system font stack, body 17 px/1.6, generous spacing, hairline dividers, light/dark via `prefers-color-scheme`, accent red only for map points and "yeni gelişme".

- [ ] **Step 1: Write failing node tests** for `isNewDevelopment`, `formatAgo` (tr/en, boundaries), `formatToday` (UTC 22:30 on Nov 13 → "14 Kasım" in Istanbul).
- [ ] **Step 2: Run** `node --test site/tests/` → FAIL.
- [ ] **Step 3: Implement** `lib.js`, then views in `app.js`, styles, manifest.
- [ ] **Step 4: Run** `node --test site/tests/` → PASS.
- [ ] **Step 5: Visual check**: serve `site/` with `python -m http.server` using `dev-data/` (`?data=dev-data`), screenshot today/all/detail at 390×844 with Playwright; verify: no images in lists, quiet message when `events: []`, a title containing `<b>x</b>` shows literally.
- [ ] **Step 6: Commit** `feat: calm today/all/detail views`

### Task 11: Maps

**Files:**
- Create: `scripts/build_map.sh`, `site/map/world.topo.json`, `site/map/admin1.topo.json`, `site/map.js`, `site/vendor/{d3-geo.min.js, topojson-client.min.js}` (+ LICENSE files)
- Modify: `site/app.js` (mount maps), `site/style.css`
- Test: `site/tests/map.test.mjs`

**Interfaces:**
- Produces (`map.js`):
  - `spreadPoints(points: {id,x,y}[], minDist: number = 10) -> {id,x,y}[]` (pure; nudges overlapping points apart, deterministic)
  - `worldMap(container, events: EventSummary[], onSelect: (id) => void)` — equal-earth projection, countries only (`world.topo.json`, ~110m simplified, <150 KB), red dots for city/region locations, pale red fill for country-level locations, tap target ≥ 32 px
  - `detailMap(container, location)` — lazy-loads `admin1.topo.json`, fits ~600 km around the point for city/region, the country's bounds for country level; nothing rendered when `location` is null
- `build_map.sh`: `npx mapshaper` on Natural Earth `ne_110m_admin_0_countries` → `world.topo.json` (keep `ISO_A2`), and `ne_10m_admin_1_states_provinces` simplified to ≤1.5 MB → `admin1.topo.json`. Vendored libs from npm (ISC licenses).
- Colors: land `--map-land`, borders `--map-border` (hairline), water = page background; point `#E24B4A`; pale fill `rgba(226,75,74,.18)`; dark-mode variants via CSS vars.

- [ ] **Step 1: Write failing test** for `spreadPoints` (two identical points end ≥ `minDist` apart; isolated point unchanged; same input → same output).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** script, run it, implement `map.js`, mount in today view (top) and detail view (under image). **Step 4: Run** node tests → PASS.
- [ ] **Step 5: Visual check** (Playwright screenshots, light + dark): world map with ≥5 dots, a US-state event zoomed in detail, country-level event tinted, event with null location shows no map.
- [ ] **Step 6: Commit** `feat: world and detail maps from Natural Earth`

### Task 12: GitHub Actions, Pages, data branch

**Files:**
- Create: `.github/workflows/update.yml`, `.github/workflows/check-sources.yml`, `README.md`

**Interfaces:**
- `update.yml`: triggers `schedule: "*/30 * * * *"` + `workflow_dispatch`; `concurrency: update` (cancel-in-progress false); permissions `contents: write, pages: write, id-token: write, actions: write`. Steps: checkout `main`; checkout `data` branch into `state/` if it exists (else empty dir); setup Python 3.12 with pip cache; `actions/cache` for `~/.cache/huggingface` and Argos packages; `pytest -q`; `python -m pipeline.run --state state --out build/data`; commit `state/` as a single orphan commit and `git push --force origin HEAD:data`; copy `site/` into `build/`; `actions/upload-pages-artifact` + `actions/deploy-pages`; finally `gh workflow enable update.yml` (keeps the schedule alive past 60 days of inactivity).
- If the pipeline step fails, later steps don't run → Pages keeps the previous version (spec 8.3).
- `check-sources.yml`: `workflow_dispatch` only, runs `scripts/check_sources.py`.
- README: what it is, one-time setup (Settings → Pages → Source: GitHub Actions), how to add a source, how to enable Gemini later, credits.

- [ ] **Step 1: Validate** workflows with `actionlint` (pip/npm-free binary from GitHub releases) → no errors.
- [ ] **Step 2: Push** to `github.com/muhammedalibuke/dunya-haber`; user enables Pages (GitHub Actions source).
- [ ] **Step 3: Run** `check-sources` via `workflow_dispatch`; replace feeds that fail; re-run until ≥150 healthy and ≥100 countries.
- [ ] **Step 4: Run** `update` via `workflow_dispatch` → green; `data` branch has one commit; site loads on phone URL `https://muhammedalibuke.github.io/dunya-haber/` with real events.
- [ ] **Step 5: Tune** `CLUSTER_THRESHOLD` by eyeballing 2 runs of real data (merged-but-different and split-but-same events); record final value and reason in README.
- [ ] **Step 6: Commit** `ci: scheduled pipeline, data branch, Pages deploy`

### Task 13 (optional, off by default): Gemini summaries

**Files:**
- Modify: `pipeline/summarize.py`, `pipeline/run.py`
- Test: `tests/test_summarize_gemini.py`

**Interfaces:**
- `gemini_summary(event_titles: list[str], descriptions: list[str], api_key: str, post: Callable = httpx.post) -> tuple[str, str] | None` → (tr, en) or None on any error/quota (429) /timeout (20 s). Model: the cheapest Flash-Lite available on the free tier, name in a constant `GEMINI_MODEL`.
- In `run`: only for today's events, only if `GEMINI_API_KEY` env is set; success sets `summary_ai = True`.
- [ ] **Step 1: Write failing tests** with a fake `post`: success → both strings; 429 → None; malformed JSON → None; key unset → `run` never calls `post`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: optional Gemini summaries with silent fallback`
