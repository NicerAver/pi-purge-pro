// Trace browser-hook profile: filtered cookie/header observation with request binding.
(function () {
  'use strict';

  const CONFIG = {
    cookieNameIncludes: ['token', 'auth', 'session', 'sign', 'acw'],
    headerNameIncludes: ['authorization', 'sign', 'token'],
    urlIncludes: ['/api/'],
    maxEvents: 50,
    logStack: false,
  };
  const registry = window.__traceHooks = window.__traceHooks || {};
  if (registry.cookieHeader && registry.cookieHeader.restore) registry.cookieHeader.restore();
  const originalOwnCookie = Object.getOwnPropertyDescriptor(document, 'cookie');
  const cookieDescriptor = Object.getOwnPropertyDescriptor(Document.prototype, 'cookie') ||
    (typeof HTMLDocument !== 'undefined' && Object.getOwnPropertyDescriptor(HTMLDocument.prototype, 'cookie'));
  const original = {
    open: XMLHttpRequest.prototype.open,
    setRequestHeader: XMLHttpRequest.prototype.setRequestHeader,
    fetch: window.fetch,
  };
  const xhrState = new WeakMap();
  let events = 0;

  function includesAny(value, filters) {
    const text = String(value || '').toLowerCase();
    return filters.length === 0 || filters.some((item) => text.includes(item.toLowerCase()));
  }

  function summarizeUrl(value) {
    const text = String(value || '');
    try {
      if (typeof URL === 'function') {
        const base = typeof location !== 'undefined' ? location.href : 'https://trace.invalid/';
        const parsed = new URL(text, base);
        return parsed.origin === 'https://trace.invalid' ? parsed.pathname : parsed.origin + parsed.pathname;
      }
    } catch (_) {}
    return text.split(/[?#]/, 1)[0];
  }

  function emit(label, meta) {
    if (events >= CONFIG.maxEvents) return;
    events += 1;
    console.log(label, JSON.stringify(meta));
    if (CONFIG.logStack) console.trace(label + ' stack');
  }

  if (cookieDescriptor && cookieDescriptor.get && cookieDescriptor.set) {
    Object.defineProperty(document, 'cookie', {
      configurable: true,
      get() { return cookieDescriptor.get.call(document); },
      set(value) {
        const pair = String(value).split(';', 1)[0];
        const separator = pair.indexOf('=');
        const name = (separator === -1 ? pair : pair.slice(0, separator)).trim();
        const cookieValue = separator === -1 ? '' : pair.slice(separator + 1);
        if (includesAny(name, CONFIG.cookieNameIncludes)) emit('[trace-cookie-set]', { name, valueLength: cookieValue.length });
        return cookieDescriptor.set.call(document, value);
      },
    });
  }

  function open(method, url) {
    xhrState.set(this, { method: String(method || 'GET'), url: String(url || '') });
    return original.open.apply(this, arguments);
  }

  function setRequestHeader(name, value) {
    const state = xhrState.get(this) || { method: '?', url: '' };
    if (includesAny(state.url, CONFIG.urlIncludes) && includesAny(name, CONFIG.headerNameIncludes)) {
      emit('[trace-xhr-header]', { target: 'xhr', event: 'setRequestHeader', method: state.method, url: summarizeUrl(state.url), name: String(name), valueLength: String(value).length });
    }
    return original.setRequestHeader.apply(this, arguments);
  }

  function fetchHook(input, init) {
    const url = typeof input === 'string' ? input : String(input && input.url || '');
    const method = String(init && init.method || input && input.method || 'GET');
    if (includesAny(url, CONFIG.urlIncludes)) {
      try {
        new Headers(init && init.headers || input && input.headers).forEach((value, name) => {
          if (includesAny(name, CONFIG.headerNameIncludes)) emit('[trace-fetch-header]', { target: 'fetch', event: 'send', method, url: summarizeUrl(url), name, valueLength: String(value).length });
        });
      } catch (_) {}
    }
    return original.fetch.apply(this, arguments);
  }

  XMLHttpRequest.prototype.open = open;
  XMLHttpRequest.prototype.setRequestHeader = setRequestHeader;
  window.fetch = fetchHook;

  registry.cookieHeader = {
    config: CONFIG,
    restore() {
      if (originalOwnCookie) Object.defineProperty(document, 'cookie', originalOwnCookie);
      else delete document.cookie;
      if (XMLHttpRequest.prototype.open === open) XMLHttpRequest.prototype.open = original.open;
      if (XMLHttpRequest.prototype.setRequestHeader === setRequestHeader) XMLHttpRequest.prototype.setRequestHeader = original.setRequestHeader;
      if (window.fetch === fetchHook) window.fetch = original.fetch;
      delete registry.cookieHeader;
    },
  };
  console.log('[trace-hook] cookieHeader installed; edit __traceHooks.cookieHeader.config and call .restore() when done');
})();
