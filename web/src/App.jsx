import React, { useEffect, useRef, useState } from 'react';
import Icon from './Icon.jsx';
import { buildAdvanced, formatSearchError, search, safeUrl } from './api.js';
import { HISTORY_KEY, PRIVATE_KEY, readHistory, readPrivate, remember, store } from './storage.js';

const ideas = [
  { label: 'Coś nowego do odkrycia', query: 'najciekawsze odkrycia naukowe', icon: 'spark' },
  { label: 'Pomysł na weekend', query: 'Pomorze ciekawe miejsca na weekend', icon: 'globe' },
  { label: 'Świat technologii', query: 'nowości technologiczne open source', icon: 'search' },
];

const EMPTY_FILTERS = { exclude: '', include: '', phrase: '', site: '', notSite: '', language: '', timeRange: '', category: '' };
const LANGUAGES = [['', 'Domyślny'], ['pl', 'Polski'], ['en', 'Angielski'], ['de', 'Niemiecki'], ['fr', 'Francuski'], ['es', 'Hiszpański'], ['uk', 'Ukraiński'], ['ru', 'Rosyjski']];
const TIME_RANGES = [['', 'Dowolny'], ['day', 'Dzień'], ['week', 'Tydzień'], ['month', 'Miesiąc'], ['year', 'Rok']];
const CATEGORIES = [['', 'Wszystkie'], ['general', 'Ogólne'], ['images', 'Obrazy'], ['videos', 'Wideo'], ['news', 'Wiadomości'], ['it', 'IT'], ['music', 'Muzyka'], ['files', 'Pliki'], ['science', 'Nauka'], ['social media', 'Społeczności']];

function withoutListItem(value, item) {
  return value.split(',').map(part => part.trim()).filter(part => part && part !== item).join(', ');
}

function activeChips(filters) {
  const chips = [];
  const addList = (value, field, decorate) => value.split(',').map(item => item.trim()).filter(Boolean).forEach(item =>
    chips.push({ key: `${field}:${item}`, label: decorate(item), remove: current => ({ ...current, [field]: withoutListItem(current[field], item) }) }));
  addList(filters.exclude, 'exclude', item => `−${item}`);
  addList(filters.include, 'include', item => `+${item}`);
  if (filters.phrase.trim()) chips.push({ key: 'phrase', label: `„${filters.phrase.trim()}”`, remove: current => ({ ...current, phrase: '' }) });
  addList(filters.site, 'site', item => `site: ${item}`);
  addList(filters.notSite, 'notSite', item => `poza ${item}`);
  if (filters.language) chips.push({ key: 'language', label: (LANGUAGES.find(([code]) => code === filters.language) || ['', filters.language])[1], remove: current => ({ ...current, language: '' }) });
  if (filters.timeRange) chips.push({ key: 'timeRange', label: (TIME_RANGES.find(([code]) => code === filters.timeRange) || ['', filters.timeRange])[1], remove: current => ({ ...current, timeRange: '' }) });
  if (filters.category) chips.push({ key: 'category', label: (CATEGORIES.find(([code]) => code === filters.category) || ['', filters.category])[1], remove: current => ({ ...current, category: '' }) });
  return chips;
}

function Result({ result, index }) {
  const url = safeUrl(result.url);
  if (!url) return null;
  const siteName = url.hostname.replace(/^www\./, '') || url.hostname;
  return <article className="result" style={{ '--order': index }}>
    <div className="result-site"><span className="site-symbol">{(siteName[0] || '?').toUpperCase()}</span>
      <div><span className="site-name">{siteName}</span><span className="site-path">{url.pathname === '/' ? 'Strona główna' : url.pathname.slice(0, 75)}</span></div>
    </div>
    <a className="result-title" href={url.href} target="_blank" rel="noopener noreferrer">{result.title || url.hostname}<Icon name="external" size={17} /></a>
    <p>{result.snippet || 'Ta strona nie udostępnia opisu. Otwórz ją, aby dowiedzieć się więcej.'}</p>
  </article>;
}

export default function App() {
  const [query, setQuery] = useState('');
  const [searched, setSearched] = useState('');
  const [history, setHistory] = useState(readHistory);
  const [privateMode, setPrivate] = useState(readPrivate);
  const [maxResults, setMaxResults] = useState(10);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [storageNotice, setStorageNotice] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [mobile, setMobile] = useState(() => window.matchMedia?.('(max-width: 760px)').matches ?? false);
  const sidebar = useRef(null);
  const menuButton = useRef(null);
  const returnFocus = useRef(null);
  const mobileOpen = mobile && sidebarOpen;
  const input = useRef(null);
  const request = useRef(null);
  const requestId = useRef(0);

  useEffect(() => () => request.current?.abort(), []);
  useEffect(() => {
    const media = window.matchMedia?.('(max-width: 760px)');
    if (!media) return;
    const changed = () => { setMobile(media.matches); setSidebarOpen(false); };
    media.addEventListener('change', changed);
    return () => media.removeEventListener('change', changed);
  }, []);
  useEffect(() => {
    if (!mobileOpen) return;
    returnFocus.current = menuButton.current;
    sidebar.current.querySelector('button')?.focus();
    const trap = event => {
      if (event.key !== 'Tab') return;
      const buttons = [...sidebar.current.querySelectorAll('button:not(:disabled), a[href], input, select')];
      const first = buttons[0], last = buttons[buttons.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    window.addEventListener('keydown', trap);
    return () => {
      window.removeEventListener('keydown', trap);
      returnFocus.current?.focus();
    };
  }, [mobileOpen]);
  useEffect(() => {
    const shortcut = event => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault(); returnFocus.current = input.current; setSidebarOpen(false); input.current?.focus();
      }
      if (event.key === 'Escape') { setSidebarOpen(false); setDetailsOpen(false); }
    };
    window.addEventListener('keydown', shortcut);
    return () => window.removeEventListener('keydown', shortcut);
  }, []);

  const updateFilter = field => event => setFilters(current => ({ ...current, [field]: event.target.value }));

  function saveHistory(next) {
    setHistory(next);
    if (!store(HISTORY_KEY, next)) setStorageNotice('Przeglądarka nie pozwala zapisać historii. Jest dostępna tylko w tej karcie.');
  }

  async function runSearch(value = query) {
    const normalized = value.trim();
    if (!normalized) { input.current?.focus(); return; }
    request.current?.abort();
    const id = ++requestId.current;
    const controller = new AbortController();
    request.current = controller;
    const timeout = window.setTimeout(() => controller.abort(), 60000);
    setQuery(normalized); setSearched(normalized); setLoading(true);
    setData(null); setError(''); returnFocus.current = input.current; setSidebarOpen(false);
    if (!privateMode) saveHistory(remember(history, normalized));
    const started = performance.now();
    try {
      const result = await search(normalized, maxResults, controller.signal, buildAdvanced(filters));
      if (id !== requestId.current) return;
      setData(result); setElapsed((performance.now() - started) / 1000);
      if (result.status === 'error' || (result.source === null && result.status !== 'empty')) setError('Nie udało się pobrać wyników z dostępnych wyszukiwarek. Spróbuj ponownie za moment.');
    } catch (failure) {
      if (id !== requestId.current) return;
      setError(formatSearchError(failure));
    } finally {
      clearTimeout(timeout);
      if (id === requestId.current) setLoading(false);
    }
  }

  function resetSearch() {
    requestId.current += 1; request.current?.abort();
    setQuery(''); setSearched(''); setData(null); setError(''); setLoading(false);
    setFilters(EMPTY_FILTERS); setDetailsOpen(false);
    returnFocus.current = input.current; setSidebarOpen(false); input.current?.focus();
  }

  const results = data?.results.filter(result => safeUrl(result.url)) || [];

  return <div className="app-shell">
    <a className="skip-link" href="#main">Przejdź do wyszukiwarki</a>
    {sidebarOpen && <button className="sidebar-backdrop" aria-label="Zamknij historię" onClick={() => setSidebarOpen(false)} />}
    <aside ref={sidebar} id="search-history" inert={mobile && !sidebarOpen} role={mobileOpen ? 'dialog' : undefined} aria-modal={mobileOpen ? true : undefined} className={`sidebar ${sidebarOpen ? 'is-open' : ''}`} aria-label="Historia wyszukiwania">
      <button className="brand" onClick={resetSearch} aria-label="Szukaj — strona główna"><span className="brand-mark"><Icon name="search" size={24} /></span><span>szukaj<span className="brand-dot">.</span>dom</span></button>
      <button className="new-search" onClick={resetSearch}><Icon name="plus" size={18} /> Nowe wyszukiwanie <kbd>⌘ / Ctrl K</kbd></button>
      <div className="history-heading"><span>TWOJA HISTORIA</span><Icon name="clock" size={15} /></div>
      <div className="history-list">
        {history.length === 0 ? <div className="history-empty"><Icon name="clock" size={28} /><p>Tu zaczyna się Twoja<br />historia odkryć.</p><span>Ostatnie zapytania będą<br />zawsze pod ręką.</span></div> : <>
          <p className="history-period">Ostatnie wyszukiwania</p>
          {history.map(item => <div className={`history-row ${searched === item.query ? 'active' : ''}`} key={item.query}>
            <button className="history-query" onClick={() => { void runSearch(item.query); }} title={item.query}><Icon name="clock" size={15} /><span>{item.query}</span></button>
            <button className="icon-button remove-history" aria-label={`Usuń z historii: ${item.query}`} onClick={() => saveHistory(history.filter(entry => entry.query !== item.query))}><Icon name="close" size={14} /></button>
          </div>)}
        </>}
      </div>
      <div className="sidebar-bottom">
        {history.length > 0 && <div className="clear-history-area">{confirmClear ? <div className="clear-confirm"><span>Usunąć całą historię?</span><button onClick={() => { saveHistory([]); setConfirmClear(false); }}>Usuń</button><button onClick={() => setConfirmClear(false)}>Anuluj</button></div> : <button className="text-button" onClick={() => setConfirmClear(true)}><Icon name="trash" size={15} /> Wyczyść historię</button>}</div>}
        <div className="privacy-card"><span className="privacy-icon"><Icon name="shield" size={20} /></span><div><strong>Historia zostaje u Ciebie</strong><p>Zapisujemy ją tylko w tej przeglądarce.</p></div></div>
        <div className="sidebar-signature"><span className="tiny-dot" /> TWOJE MIEJSCE W SIECI</div>
      </div>
    </aside>

    <div className="workspace" inert={mobileOpen}>
      <header className="topbar"><div className="topbar-left"><button ref={menuButton} aria-expanded={mobileOpen} aria-controls="search-history" className="icon-button mobile-menu" aria-label="Otwórz historię" onClick={() => setSidebarOpen(true)}><Icon name="menu" /></button><span className="breadcrumb">Wyszukiwarka <span>/</span> <strong>{searched ? 'Wyniki' : 'Odkrywaj'}</strong></span></div><span className="engine-badge"><span className="tiny-dot" /> SearXNG + Perplexity</span></header>
      <main id="main" className={searched ? 'main-content has-results' : 'main-content'}>
        {!searched && <section className="hero"><div className="eyebrow"><span className="eyebrow-line" /> MNIEJ SZUMU. WIĘCEJ ODKRYĆ.</div><h1>Ciekawość to<br />dobry <span>początek<svg viewBox="0 0 390 20" aria-hidden="true"><path d="M4 14 Q160 -1 385 10" /></svg></span>.</h1><p>Wielki internet. Twoje pytania.<br className="mobile-break" /> Znajdź to, czego szukasz.</p></section>}
        <section className="search-section" aria-label="Wyszukiwarka">
          <form className={`search-form ${loading ? 'is-loading' : ''}`} onSubmit={event => { event.preventDefault(); void runSearch(); }}>
            <Icon name="search" size={24} /><label className="sr-only" htmlFor="search-input">Czego szukasz?</label>
            <input ref={input} id="search-input" value={query} onChange={event => setQuery(event.target.value)} placeholder="Co chcesz dziś odkryć?" maxLength={500} autoComplete="off" />
            {query && <button type="button" className="icon-button" aria-label="Wyczyść zapytanie" onClick={() => { setQuery(''); input.current?.focus(); }}><Icon name="close" size={17} /></button>}
            <button type="button" className={`icon-button details-toggle ${detailsOpen ? 'is-active' : ''}`} aria-expanded={detailsOpen} aria-controls="detailed-search" title="Szukanie szczegółowe" aria-label="Szukanie szczegółowe" onClick={() => setDetailsOpen(open => !open)}><Icon name="sliders" size={18} /></button>
            <button className="submit-search" type="submit" disabled={!query.trim()} aria-label="Szukaj"><span>Szukaj</span><Icon name="arrow" size={20} /></button>
          </form>
          {detailsOpen && <div id="detailed-search" className="details-panel">
            <p className="details-hint">Słowa i domeny rozdzielaj przecinkami. Cudzysłowy oraz operatory (−, +, site:) dodajemy za Ciebie.</p>
            <div className="details-grid">
              <label>Wyklucz słowa<input value={filters.exclude} onChange={updateFilter('exclude')} placeholder="używany, promocja" maxLength={500} autoComplete="off" /></label>
              <label>Muszą wystąpić<input value={filters.include} onChange={updateFilter('include')} placeholder="recenzja, premiera" maxLength={500} autoComplete="off" /></label>
              <label>Dokładna fraza<input value={filters.phrase} onChange={updateFilter('phrase')} placeholder="napęd paskowy" maxLength={200} autoComplete="off" /></label>
              <label>W witrynie<input value={filters.site} onChange={updateFilter('site')} placeholder="wikipedia.org, gov.pl" maxLength={500} autoComplete="off" /></label>
              <label>Poza witryną<input value={filters.notSite} onChange={updateFilter('notSite')} placeholder="pinterest.com" maxLength={500} autoComplete="off" /></label>
              <label>Język<select aria-label="Język wyników" value={filters.language} onChange={updateFilter('language')}>{LANGUAGES.map(([code, label]) => <option key={code} value={code}>{label}</option>)}</select></label>
              <label>Czas<select aria-label="Zakres czasu" value={filters.timeRange} onChange={updateFilter('timeRange')}>{TIME_RANGES.map(([code, label]) => <option key={code} value={code}>{label}</option>)}</select></label>
              <label>Kategoria<select aria-label="Kategoria" value={filters.category} onChange={updateFilter('category')}>{CATEGORIES.map(([code, label]) => <option key={code} value={code}>{label}</option>)}</select></label>
            </div>
            <div className="details-actions"><button type="button" className="text-button" onClick={() => setFilters(EMPTY_FILTERS)}><Icon name="close" size={14} /> Wyczyść filtry</button></div>
          </div>}
          <div className="search-options"><label className="private-toggle"><input type="checkbox" checked={privateMode} onChange={event => { setPrivate(event.target.checked); if (!store(PRIVATE_KEY, event.target.checked)) setStorageNotice('Ustawienie historii obowiązuje tylko w tej karcie.'); }} /><span className="toggle-track" /><Icon name="shield" size={14} /><span>Bez zapisywania historii</span></label><label className="results-select">Wyników <select aria-label="Liczba wyników" value={maxResults} onChange={event => setMaxResults(Number(event.target.value))}><option value={5}>5</option><option value={10}>10</option></select></label></div>
          {activeChips(filters).length > 0 && <div className="filter-chips" aria-label="Aktywne filtry">{activeChips(filters).map(chip => <span className="filter-chip" key={chip.key}><span>{chip.label}</span><button type="button" aria-label={`Usuń filtr: ${chip.label}`} onClick={() => setFilters(current => chip.remove(current))}><Icon name="close" size={12} /></button></span>)}</div>}
        </section>
        {storageNotice && <p className="storage-notice" role="status">{storageNotice}</p>}
        {!searched && <><section className="inspiration" aria-label="Inspiracje"><div className="section-label">NIE WIESZ, OD CZEGO ZACZĄĆ?</div><div className="idea-grid">{ideas.map(idea => <button className="idea-card" key={idea.label} onClick={() => { void runSearch(idea.query); }}><span className="idea-icon"><Icon name={idea.icon} size={19} /></span><span>{idea.label}</span><Icon name="arrow" size={16} /></button>)}</div></section><section className="feature-strip" aria-label="Jak działa wyszukiwarka"><div><Icon name="globe" size={21} /><span><strong>Szersza perspektywa</strong><small>Wyniki z wielu wyszukiwarek</small></span></div><span className="feature-divider" /><div><Icon name="shield" size={21} /><span><strong>Ty decydujesz</strong><small>Historia pod Twoją kontrolą</small></span></div></section></>}
        <section className="search-feedback" aria-live="polite" aria-atomic="true">
          {loading && <div className="loading-state" role="status"><span className="spinner" /><div><strong>Szukamy dobrych odpowiedzi…</strong><p>Przeszukujemy sieć dla Ciebie.</p></div></div>}
          {!loading && error && <div className="message-card error-message" role="alert"><Icon name="globe" size={30} /><h2>Błąd. Przepraszamy</h2><p>{error}</p><button className="secondary-button" onClick={() => { void runSearch(searched); }}>Spróbuj ponownie <Icon name="arrow" size={16} /></button></div>}
          {!loading && !error && data && <div className="results-summary"><span>{results.length ? `${results.length} wyników` : 'Brak wyników'} dla <strong>„{searched}”</strong></span><span>{data.source === 'perplexity-fast' ? 'Perplexity · źródło awaryjne' : 'SearXNG'} <span className="summary-dot">·</span> {elapsed.toFixed(1)} s</span></div>}
          {!loading && !error && data && !results.length && <div className="message-card"><Icon name="search" size={32} /><h2>Spróbuj spojrzeć inaczej</h2><p>Nie znaleźliśmy wyników. Skróć zapytanie lub użyj innych słów.</p></div>}
        </section>
        {!loading && !error && results.length > 0 && <section className="results-list" aria-label="Wyniki wyszukiwania">{results.map((result, index) => <Result key={`${result.url}-${index}`} result={result} index={index} />)}</section>}
      </main>
      <footer className="footer"><span>Od pytania zaczyna się odkrywanie.</span><span>SearXNG <span>↗</span> <span className="footer-divider">/</span> Perplexity awaryjnie</span></footer>
    </div>
  </div>;
}
