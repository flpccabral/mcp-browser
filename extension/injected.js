/**
 * MCP Browser Bridge — Injected Script
 *
 * Script injetado no contexto da página (não isolado).
 * Pode acessar variáveis globais da página (jQuery, Vue, React, etc.)
 * e enviar dados para o content.js via window.postMessage.
 */

(function () {
  'use strict';

  // Evita dupla injeção
  if (window.__mcp_injected_active__) return;
  window.__mcp_injected_active__ = true;

  function sendToContent(type, payload) {
    window.postMessage(
      {
        source: 'mcp-injected',
        type,
        payload,
        timestamp: Date.now(),
      },
      '*'
    );
  }

  // ────────────────────────────────────────────────
  // Detectar frameworks globais
  // ────────────────────────────────────────────────

  function detectFrameworks() {
    const frameworks = [];

    if (typeof jQuery !== 'undefined') {
      frameworks.push({ name: 'jQuery', version: jQuery.fn?.jquery });
    }
    if (typeof Vue !== 'undefined') {
      frameworks.push({ name: 'Vue', version: Vue.version });
    }
    if (typeof React !== 'undefined') {
      frameworks.push({ name: 'React', version: React.version });
    }
    if (typeof angular !== 'undefined') {
      frameworks.push({ name: 'AngularJS', version: angular.version?.full });
    }
    if (window.__ng) {
      frameworks.push({ name: 'Angular', version: '2+' });
    }
    if (typeof Backbone !== 'undefined') {
      frameworks.push({ name: 'Backbone' });
    }
    if (typeof Ember !== 'undefined') {
      frameworks.push({ name: 'Ember' });
    }
    if (window.__VUE__) {
      frameworks.push({ name: 'Vue (detected via __VUE__)' });
    }
    if (window.__NUXT__) {
      frameworks.push({ name: 'Nuxt' });
    }
    if (window.__NEXT_DATA__) {
      frameworks.push({ name: 'Next.js' });
    }

    return frameworks;
  }

  // ────────────────────────────────────────────────
  // Detectar dados de SPA (React Router, Vue Router, etc.)
  // ────────────────────────────────────────────────

  function detectRoute() {
    const route = { path: location.pathname, hash: location.hash, search: location.search };

    // Vue Router
    if (window.__VUE_ROUTER__ && window.__VUE_ROUTER__.currentRoute) {
      route.vueRoute = window.__VUE_ROUTER__.currentRoute;
    }

    // Next.js data
    if (window.__NEXT_DATA__) {
      route.nextData = {
        page: window.__NEXT_DATA__.page,
        query: window.__NEXT_DATA__.query,
      };
    }

    return route;
  }

  // ────────────────────────────────────────────────
  // Interceptar console.warn / console.error (opcional)
  // ────────────────────────────────────────────────

  const originalWarn = console.warn;
  const originalError = console.error;

  console.warn = function (...args) {
    sendToContent('console', { level: 'warn', message: args.map(String).join(' ') });
    originalWarn.apply(console, args);
  };

  console.error = function (...args) {
    sendToContent('console', { level: 'error', message: args.map(String).join(' ') });
    originalError.apply(console, args);
  };

  // ────────────────────────────────────────────────
  // Notificar content script que o injected está pronto
  // ────────────────────────────────────────────────

  sendToContent('ready', {
    url: location.href,
    frameworks: detectFrameworks(),
    route: detectRoute(),
  });

  // Re-notificar em navegação SPA
  let lastUrl = location.href;
  const checkUrl = setInterval(() => {
    if (location.href !== lastUrl) {
      lastUrl = location.href;
      sendToContent('navigation', {
        url: lastUrl,
        route: detectRoute(),
      });
    }
  }, 500);

  // Cleanup não é realmente possível em script injetado,
  // mas podemos limpar se o script for removido
  window.addEventListener('beforeunload', () => {
    clearInterval(checkUrl);
  });

  console.log('[MCP Injected] Ativo em', location.href);
})();
