import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App.jsx';
import ErrorBoundary from './ErrorBoundary.jsx';
import { formatSearchError, search } from './api.js';
import { HISTORY_KEY, PRIVATE_KEY, readHistory, remember } from './storage.js';

const response = { source: 'searxng', results: [{ title: 'Wynik testowy', url: 'https://example.org/test', snippet: 'Opis wyniku' }] };

beforeEach(() => {
  localStorage.clear();
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => response }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.unstubAllEnvs(); });

async function submit(query = 'Pomorze') {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText('Czego szukasz?'), query);
  await user.click(screen.getByRole('button', { name: 'Szukaj', exact: true }));
  return user;
}

describe('search application', () => {
  it('preserves cancellation while reading an error response', async () => {
    const failure = Object.assign(new Error('aborted'), { name: 'AbortError' });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.reject(failure),
    }));
    await expect(search('query', 5)).rejects.toBe(failure);
  });

  it('preserves cancellation while reading a successful response', async () => {
    const failure = Object.assign(new Error('aborted'), { name: 'AbortError' });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.reject(failure),
    }));
    await expect(search('query', 5)).rejects.toBe(failure);
  });

  it('renders successful empty status without a provider failure alert', async () => {
    fetch.mockResolvedValueOnce({ ok: true, json: async () => ({ status: 'empty', source: null, results: [] }) });
    render(<App />); await submit();
    await screen.findByText('Spróbuj spojrzeć inaczej');
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('searches through the API, renders links and persists reusable history', async () => {
    render(<App />);
    const user = await submit();
    const link = await screen.findByRole('link', { name: /Wynik testowy/ });
    expect(link.getAttribute('href')).toBe('https://example.org/test');
    expect(fetch).toHaveBeenCalledWith('/api/search', expect.objectContaining({ body: JSON.stringify({ query: 'Pomorze', max_results: 10 }) }));
    expect(readHistory()[0].query).toBe('Pomorze');
    await user.click(screen.getByRole('button', { name: 'Pomorze', exact: true }));
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
    expect(readHistory()).toHaveLength(1);
  });

  it('does not save searches in private history mode, including after reload', async () => {
    render(<App />);
    const user = userEvent.setup();
    await user.click(screen.getByRole('checkbox', { name: /Bez zapisywania historii/ }));
    await submit('prywatne zapytanie');
    await screen.findByRole('link', { name: /Wynik testowy/ });
    expect(readHistory()).toEqual([]);
    expect(localStorage.getItem(PRIVATE_KEY)).toBe('true');
    cleanup(); render(<App />);
    expect(screen.getByRole('checkbox', { name: /Bez zapisywania historii/ }).checked).toBe(true);
  });

  it('restores history and supports removing one entry and clearing all with confirmation', async () => {
    localStorage.setItem(HISTORY_KEY, JSON.stringify([{ query: 'A', time: 1 }, { query: 'B', time: 2 }]));
    render(<App />); const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Usuń z historii: A' }));
    expect(readHistory().map(item => item.query)).toEqual(['B']);
    await user.click(screen.getByRole('button', { name: /Wyczyść historię/ }));
    expect(readHistory()).toHaveLength(1);
    await user.click(screen.getByRole('button', { name: 'Usuń', exact: true }));
    expect(readHistory()).toEqual([]);
  });

  it('explains provider failure and offers retry', async () => {
    fetch.mockResolvedValueOnce({ ok: true, json: async () => ({ source: null, results: [] }) });
    render(<App />); const user = await submit();
    await screen.findByRole('alert');
    await user.click(screen.getByRole('button', { name: /Spróbuj ponownie/ }));
    await screen.findByRole('link', { name: /Wynik testowy/ });
  });

  it('renders a hostname consisting only of www. without crashing', async () => {
    fetch.mockResolvedValueOnce({ ok: true, json: async () => ({ source: 'searxng',
      results: [{ title: 'Unusual host', url: 'https://www./', snippet: 'Text' }] }) });
    render(<App />); await submit();
    expect((await screen.findByRole('link', { name: /Unusual host/ })).getAttribute('href')).toBe('https://www./');
    expect(screen.getByText('www.')).toBeTruthy();
  });

  it('handles empty results and hides unsafe result URLs', async () => {
    fetch.mockResolvedValueOnce({ ok: true, json: async () => ({ source: 'searxng', results: [{ title: 'unsafe', url: 'javascript:alert(1)' }] }) });
    render(<App />); await submit();
    await screen.findByText('Spróbuj spojrzeć inaczej');
    expect(screen.queryByRole('link', { name: 'unsafe' })).toBeNull();
  });

  it.each([null, { source: 'searxng', results: [null] },
    { source: 'searxng', results: [{ title: {}, url: 'https://example.org' }] },
    { source: 'unknown', results: [] }])('handles malformed API data without crashing: %j', async data => {
    fetch.mockResolvedValueOnce({ ok: true, json: async () => data });
    render(<App />); await submit();
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain('Nie udało się odczytać wyników wyszukiwania.');
    expect(screen.queryByRole('link', { name: /Wynik testowy/ })).toBeNull();
  });

  it('ignores a late response after returning to the start page', async () => {
    let resolve;
    fetch.mockReturnValueOnce(new Promise(done => { resolve = done; }));
    render(<App />);
    const user = await submit();
    await user.click(screen.getByRole('button', { name: 'Szukaj — strona główna' }));
    resolve({ ok: true, json: async () => response });
    await waitFor(() => expect(screen.queryByRole('status')).toBeNull());
    expect(screen.queryByRole('link', { name: /Wynik testowy/ })).toBeNull();
    expect(screen.getByText('Ciekawość to', { exact: false })).toBeTruthy();
  });

  it('handles network errors without leaving stale results or leaking internal details in prod', async () => {
    fetch.mockRejectedValueOnce(new Error('TypeError: internal socket ECONNREFUSED 10.0.0.5'));
    render(<App />); await submit();
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain('Błąd. Przepraszamy');
    expect(alert.textContent).toContain('Wystąpił problem techniczny. Spróbuj ponownie za moment.');
    expect(alert.textContent).not.toContain('ECONNREFUSED');
    expect(screen.queryByRole('link', { name: /Wynik testowy/ })).toBeNull();
  });

  it('shows diagnostic error details in dev mode and hides them in prod mode', () => {
    const raw = new Error('debug stack detail');
    expect(formatSearchError(raw, 'prod')).not.toContain('debug stack detail');
    expect(formatSearchError(raw, 'dev')).toContain('debug stack detail');
    vi.stubEnv('VITE_APP_ENV', 'dev');
    expect(formatSearchError(raw)).toContain('debug stack detail');
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    function BrokenComponent() { throw new Error('render crash detail'); }
    render(<ErrorBoundary appEnv={import.meta.env?.VITE_APP_ENV}><BrokenComponent /></ErrorBoundary>);
    expect(screen.getByRole('alert').textContent).toContain('render crash detail');
    cleanup();
    vi.stubEnv('VITE_APP_ENV', 'prod');
    render(<ErrorBoundary appEnv="prod"><BrokenComponent /></ErrorBoundary>);
    expect(screen.getByRole('alert').textContent).toContain('Błąd. Przepraszamy');
    expect(screen.getByRole('alert').textContent).not.toContain('render crash detail');
    cleanup();
    render(<ErrorBoundary appEnv="dev"><BrokenComponent /></ErrorBoundary>);
    expect(screen.getByRole('alert').textContent).toContain('render crash detail');
    spy.mockRestore();
  });
});

describe('history integrity', () => {
  it('preserves valid entries when another stored entry is null', () => {
    localStorage.setItem(HISTORY_KEY, JSON.stringify([null, { query: 'valid', time: 1 }]));
    expect(readHistory()).toEqual([{ query: 'valid', time: 1 }]);
  });
  it('recovers from malformed storage and limits deduplicated history', () => {
    localStorage.setItem(HISTORY_KEY, '{broken'); expect(readHistory()).toEqual([]);
    localStorage.setItem(HISTORY_KEY, '{}'); expect(readHistory()).toEqual([]);
    let entries = [];
    for (let i = 0; i < 40; i++) entries = remember(entries, `query ${i}`, i);
    entries = remember(entries, 'QUERY 39', 50);
    expect(entries).toHaveLength(30);
    expect(entries[0]).toEqual({ query: 'QUERY 39', time: 50 });
  });
});


describe('mobile history keyboard access', () => {
  beforeEach(() => {
    vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
    localStorage.setItem(HISTORY_KEY, JSON.stringify([{ query: 'Pomorze', time: 1 }]));
  });

  it('hides a closed panel, traps focus when open and restores it on Escape', async () => {
    render(<App />);
    const user = userEvent.setup();
    const panel = document.getElementById('search-history');
    expect(panel.hasAttribute('inert')).toBe(true);
    const opener = screen.getByRole('button', { name: 'Otwórz historię' });
    await user.click(opener);
    expect(panel.hasAttribute('inert')).toBe(false);
    expect(panel.getAttribute('aria-modal')).toBe('true');
    const first = screen.getByRole('button', { name: 'Szukaj — strona główna' });
    expect(document.activeElement).toBe(first);
    expect(document.querySelector('.workspace').hasAttribute('inert')).toBe(true);
    await user.tab({ shift: true });
    expect(document.activeElement).toBe(screen.getByRole('button', { name: /Wyczyść historię/ }));
    await user.tab();
    expect(document.activeElement).toBe(first);
    await user.keyboard('{Escape}');
    expect(document.activeElement).toBe(opener);
    expect(panel.hasAttribute('inert')).toBe(true);
    expect(document.querySelector('.workspace').hasAttribute('inert')).toBe(false);
  });

  it('returns focus to the opener after backdrop dismissal', async () => {
    render(<App />); const user = userEvent.setup();
    const opener = screen.getByRole('button', { name: 'Otwórz historię' });
    await user.click(opener);
    await user.click(screen.getByRole('button', { name: 'Zamknij historię' }));
    expect(document.activeElement).toBe(opener);
  });

  it('focuses the search input after selecting a history entry', async () => {
    render(<App />); const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Otwórz historię' }));
    await user.click(screen.getByRole('button', { name: 'Pomorze', exact: true }));
    await screen.findByRole('link', { name: /Wynik testowy/ });
    expect(document.activeElement).toBe(screen.getByLabelText('Czego szukasz?'));
  });

  it('opens the detailed search panel and sends structured filters', async () => {
    render(<App />); const user = userEvent.setup();
    expect(document.querySelector('.details-panel')).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Szukanie szczegółowe' }));
    expect(screen.getByLabelText('Wyklucz słowa')).toBeTruthy();
    await user.type(screen.getByLabelText('Czego szukasz?'), 'switch');
    await user.type(screen.getByLabelText('Wyklucz słowa'), 'używany, promocja');
    await user.type(screen.getByLabelText('Muszą wystąpić'), 'recenzja');
    await user.selectOptions(screen.getByLabelText('Zakres czasu'), 'week');
    await user.selectOptions(screen.getByLabelText('Kategoria'), 'news');
    await user.click(screen.getByRole('button', { name: 'Szukaj', exact: true }));
    await screen.findByRole('link', { name: /Wynik testowy/ });
    expect(fetch).toHaveBeenCalledWith('/api/search', expect.objectContaining({ body: JSON.stringify({
      query: 'switch', max_results: 10,
      advanced: { exclude: ['używany', 'promocja'], include: ['recenzja'], phrase: '', site: [], not_site: [],
                 language: '', time_range: 'week', categories: ['news'] },
    }) }));
  });

  it('shows active filters as removable chips', async () => {
    render(<App />); const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Szukanie szczegółowe' }));
    await user.type(screen.getByLabelText('Wyklucz słowa'), 'używany');
    await user.type(screen.getByLabelText('Dokładna fraza'), 'napęd paskowy');
    const chip = await screen.findByText('−używany');
    expect(screen.getByText('„napęd paskowy”')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: 'Usuń filtr: −używany' }));
    expect(chip).toBeTruthy();
    expect(screen.queryByText('−używany')).toBeNull();
    expect(screen.getByText('„napęd paskowy”')).toBeTruthy();
  });

  it('clears all filters from the panel action', async () => {
    render(<App />); const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Szukanie szczegółowe' }));
    await user.type(screen.getByLabelText('W witrynie'), 'wikipedia.org');
    expect(screen.getByText('site: wikipedia.org')).toBeTruthy();
    await user.click(screen.getByRole('button', { name: /Wyczyść filtry/ }));
    expect(screen.queryByText('site: wikipedia.org')).toBeNull();
  });
});
