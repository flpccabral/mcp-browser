/**
 * MCP Browser Bridge — Content Script
 *
 * Injetado em todas as páginas (document_start).
 * Responsabilidades:
 * - Interceptar XMLHttpRequest e fetch (monkey-patch)
 * - Observar DOM com MutationObserver
 * - Enviar eventos para background.js via chrome.runtime.sendMessage
 * - Injetar injected.js no contexto da página para acesso a variáveis globais
 * - Escutar postMessage do injected.js
 */

(function () {
  'use strict';

  // ───────────────────────────────────────────────────────────────────────────
  // Configuração
  // ───────────────────────────────────────────────────────────────────────────
  const CONFIG = {
    maxBodyLength: 50000,
    maxEventsPerSecond: 100,
    domThrottleMs: 50,
  };

  // ───────────────────────────────────────────────────────────────────────────
  // Throttle de envio
  // ───────────────────────────────────────────────────────────────────────────
  let eventQueue = [];
  let flushTimer = null;

  function enqueueEvent(eventType, data) {
    eventQueue.push({ type: 'event', eventType, data });
    if (!flushTimer) {
      flushTimer = setTimeout(flushEvents, CONFIG.domThrottleMs);
    }
  }

  function flushEvents() {
    flushTimer = null;
    if (eventQueue.length === 0) return;
    const batch = eventQueue.splice(0, eventQueue.length);
    for (const msg of batch) {
      console.log('[MCP-CS] Sending to background:', msg.eventType || msg.type, 'data:', JSON.stringify(msg.data || {}).substring(0,80));
      try {
        chrome.runtime.sendMessage(msg).then(() => {
          console.log('[MCP-CS] Background ACK for:', msg.eventType);
        }).catch((err) => {
          console.error('[MCP-CS] Background NACK:', err.message);
        });
      } catch (e) {
        // noop
      }
    }
  }

  // ───────────────────────────────────────────────────────────────────────────
  // Interceptar XMLHttpRequest
  // ───────────────────────────────────────────────────────────────────────────
  (function interceptXHR() {
    const OriginalXHR = window.XMLHttpRequest;

    function MCPXHR() {
      const xhr = new OriginalXHR();
      const startTime = performance.now();
      let method = 'GET';
      let url = '';
      let requestBody = null;
      let openArgs = [];

      const originalOpen = xhr.open.bind(xhr);
      const originalSend = xhr.send.bind(xhr);
      const originalSetRequestHeader = xhr.setRequestHeader.bind(xhr);
      let requestHeaders = {};

      xhr.open = function (m, u, async, user, password) {
        method = m;
        url = u;
        openArgs = [m, u, async, user, password];
        return originalOpen.apply(xhr, arguments);
      };

      xhr.setRequestHeader = function (header, value) {
        requestHeaders[header] = value;
        return originalSetRequestHeader(header, value);
      };

      xhr.send = function (body) {
        requestBody = body;
        const onLoad = () => {
          let responseBody = null;
          try {
            responseBody = xhr.responseText;
            if (responseBody && responseBody.length > CONFIG.maxBodyLength) {
              responseBody = responseBody.substring(0, CONFIG.maxBodyLength) + '\n... [truncated]';
            }
          } catch (e) {
            responseBody = null;
          }
          enqueueEvent('xhr', {
            url,
            method,
            status: xhr.status,
            statusText: xhr.statusText,
            requestHeaders,
            requestBody: requestBody ? String(requestBody).substring(0, CONFIG.maxBodyLength) : null,
            responseBody,
            responseHeaders: parseResponseHeaders(xhr.getAllResponseHeaders()),
            duration: Math.round(performance.now() - startTime),
            timestamp: Date.now(),
          });
        };

        xhr.addEventListener('load', onLoad);
        xhr.addEventListener('error', () => {
          enqueueEvent('xhr', {
            url,
            method,
            status: 0,
            statusText: 'error',
            requestHeaders,
            requestBody: requestBody ? String(requestBody).substring(0, CONFIG.maxBodyLength) : null,
            responseBody: null,
            responseHeaders: {},
            duration: Math.round(performance.now() - startTime),
            timestamp: Date.now(),
            error: true,
          });
        });

        return originalSend(body);
      };

      return xhr;
    }

    MCPXHR.prototype = OriginalXHR.prototype;
    window.XMLHttpRequest = MCPXHR;
  })();

  // ───────────────────────────────────────────────────────────────────────────
  // Interceptar fetch
  // ───────────────────────────────────────────────────────────────────────────
  (function interceptFetch() {
    const originalFetch = window.fetch;

    window.fetch = async function (resource, init = {}) {
      const startTime = performance.now();
      const url = typeof resource === 'string' ? resource : resource.url;
      const method = init.method || 'GET';
      let requestBody = init.body || null;

      try {
        const response = await originalFetch.apply(window, arguments);
        let responseBody = null;
        try {
          const clone = response.clone();
          const text = await clone.text();
          responseBody = text.length > CONFIG.maxBodyLength
            ? text.substring(0, CONFIG.maxBodyLength) + '\n... [truncated]'
            : text;
        } catch (e) {
          responseBody = null;
        }

        enqueueEvent('xhr', {
          url,
          method,
          status: response.status,
          statusText: response.statusText,
          requestHeaders: init.headers || {},
          requestBody: requestBody ? String(requestBody).substring(0, CONFIG.maxBodyLength) : null,
          responseBody,
          responseHeaders: Object.fromEntries([...response.headers.entries()]),
          duration: Math.round(performance.now() - startTime),
          timestamp: Date.now(),
          isFetch: true,
        });

        return response;
      } catch (error) {
        enqueueEvent('xhr', {
          url,
          method,
          status: 0,
          statusText: 'error',
          requestHeaders: init.headers || {},
          requestBody: requestBody ? String(requestBody).substring(0, CONFIG.maxBodyLength) : null,
          responseBody: null,
          responseHeaders: {},
          duration: Math.round(performance.now() - startTime),
          timestamp: Date.now(),
          error: true,
          errorMessage: error.message,
        });
        throw error;
      }
    };
  })();

  // ───────────────────────────────────────────────────────────────────────────
  // MutationObserver — observar DOM
  // ───────────────────────────────────────────────────────────────────────────
  (function observeDOM() {
    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        if (mutation.type === 'childList') {
          mutation.addedNodes.forEach((node) => {
            if (node.nodeType === Node.ELEMENT_NODE) {
              enqueueEvent('dom', {
                action: 'added',
                tag: node.tagName?.toLowerCase(),
                id: node.id || null,
                class: node.className || null,
                text: node.innerText?.substring(0, 200) || null,
                selector: getUniqueSelector(node),
                timestamp: Date.now(),
              });
            }
          });
          mutation.removedNodes.forEach((node) => {
            if (node.nodeType === Node.ELEMENT_NODE) {
              enqueueEvent('dom', {
                action: 'removed',
                tag: node.tagName?.toLowerCase(),
                id: node.id || null,
                class: node.className || null,
                timestamp: Date.now(),
              });
            }
          });
        } else if (mutation.type === 'attributes') {
          const target = mutation.target;
          enqueueEvent('dom', {
            action: 'changed',
            tag: target.tagName?.toLowerCase(),
            id: target.id || null,
            attribute: mutation.attributeName,
            value: target.getAttribute(mutation.attributeName),
            selector: getUniqueSelector(target),
            timestamp: Date.now(),
          });
        }
      }
    });

    observer.observe(document.documentElement, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeOldValue: false,
    });
  })();

  // ───────────────────────────────────────────────────────────────────────────
  // Listener de navegação (pushState, replaceState, hashchange)
  // ───────────────────────────────────────────────────────────────────────────
  (function interceptNavigation() {
    const originalPushState = history.pushState.bind(history);
    const originalReplaceState = history.replaceState.bind(history);

    history.pushState = function (...args) {
      originalPushState(...args);
      enqueueEvent('navigation', {
        url: location.href,
        title: document.title,
        type: 'pushState',
        timestamp: Date.now(),
      });
    };

    history.replaceState = function (...args) {
      originalReplaceState(...args);
      enqueueEvent('navigation', {
        url: location.href,
        title: document.title,
        type: 'replaceState',
        timestamp: Date.now(),
      });
    };

    window.addEventListener('hashchange', () => {
      enqueueEvent('navigation', {
        url: location.href,
        title: document.title,
        type: 'hashchange',
        timestamp: Date.now(),
      });
    });

    window.addEventListener('popstate', () => {
      enqueueEvent('navigation', {
        url: location.href,
        title: document.title,
        type: 'popstate',
        timestamp: Date.now(),
      });
    });
  })();

  // ───────────────────────────────────────────────────────────────────────────
  // Injetar injected.js no contexto da página (isolação do content script)
  // ───────────────────────────────────────────────────────────────────────────
  (function injectScript() {
    const script = document.createElement('script');
    script.src = chrome.runtime.getURL('injected.js');
    script.onload = () => script.remove();
    (document.head || document.documentElement).appendChild(script);
  })();

  // Escuta postMessage do injected.js
  window.addEventListener('message', (event) => {
    if (event.source !== window) return;
    if (!event.data || event.data.source !== 'mcp-injected') return;
    console.log('[MCP-CS] Received from injected:', event.data.type, JSON.stringify(event.data.payload).substring(0,100));
    enqueueEvent(event.data.type, event.data.payload);
  });

  // ───────────────────────────────────────────────────────────────────────────
  // Escuta mensagens do background.js
  // ───────────────────────────────────────────────────────────────────────────
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === 'export_har') {
      const har = buildHAR();
      sendResponse({ ok: true, har });
    }
    return true;
  });

  // ───────────────────────────────────────────────────────────────────────────
  // Utilitários
  // ───────────────────────────────────────────────────────────────────────────

  function parseResponseHeaders(headerStr) {
    const headers = {};
    if (!headerStr) return headers;
    const lines = headerStr.split('\r\n');
    for (const line of lines) {
      const parts = line.split(': ');
      if (parts.length === 2) {
        headers[parts[0]] = parts[1];
      }
    }
    return headers;
  }

  function getUniqueSelector(el) {
    if (el.id) return `#${el.id}`;
    if (el.className) {
      const classes = el.className.toString().split(/\s+/).filter(Boolean).join('.');
      if (classes) return `${el.tagName.toLowerCase()}.${classes}`;
    }
    // Path simplificado
    let path = [];
    let current = el;
    while (current && current !== document.body) {
      let selector = current.tagName.toLowerCase();
      const siblings = current.parentElement
        ? [...current.parentElement.children].filter(c => c.tagName === current.tagName)
        : [];
      if (siblings.length > 1) {
        const index = [...current.parentElement.children].indexOf(current) + 1;
        selector += `:nth-child(${index})`;
      }
      path.unshift(selector);
      current = current.parentElement;
      if (path.length > 5) break;
    }
    return path.join(' > ');
  }

  // Acumulador de requests para HAR export
  const capturedRequests = [];

  // Sobrescreve enqueueEvent para também acumular em capturedRequests
  const originalEnqueue = enqueueEvent;
  enqueueEvent = function (eventType, data) {
    if (eventType === 'xhr') {
      capturedRequests.push(data);
      if (capturedRequests.length > 1000) {
        capturedRequests.splice(0, capturedRequests.length - 1000);
      }
    }
    originalEnqueue(eventType, data);
  };

  function buildHAR() {
    const entries = capturedRequests.map((req) => ({
      startedDateTime: new Date(req.timestamp).toISOString(),
      time: req.duration || 0,
      request: {
        method: req.method,
        url: req.url,
        httpVersion: 'HTTP/1.1',
        headers: Object.entries(req.requestHeaders || {}).map(([name, value]) => ({ name, value })),
        queryString: [],
        cookies: [],
        headersSize: -1,
        bodySize: req.requestBody ? req.requestBody.length : -1,
        postData: req.requestBody ? { mimeType: 'application/json', text: req.requestBody } : undefined,
      },
      response: {
        status: req.status,
        statusText: req.statusText || '',
        httpVersion: 'HTTP/1.1',
        headers: Object.entries(req.responseHeaders || {}).map(([name, value]) => ({ name, value })),
        cookies: [],
        content: {
          size: req.responseBody ? req.responseBody.length : 0,
          mimeType: req.responseHeaders?.['content-type'] || 'application/octet-stream',
          text: req.responseBody || '',
        },
        redirectURL: '',
        headersSize: -1,
        bodySize: -1,
      },
      cache: {},
      timings: {
        blocked: -1,
        dns: -1,
        connect: -1,
        send: -1,
        wait: req.duration || -1,
        receive: -1,
        ssl: -1,
      },
    }));

    return {
      log: {
        version: '1.2',
        creator: { name: 'MCP Browser Bridge', version: '1.0.0' },
        entries,
      },
    };
  }

  // ───────────────────────────────────────────────────────────────────────────
  // Log de inicialização
  // ───────────────────────────────────────────────────────────────────────────
  console.log('[MCP-CS] Content script inicializado em', location.href);

  // TEST: Send a direct ping to background to verify connectivity
  try {
    chrome.runtime.sendMessage({type: 'test_ping', url: location.href}, (response) => {
      if (chrome.runtime.lastError) {
        console.error('[MCP-CS] Background ping FAILED:', chrome.runtime.lastError.message);
      } else {
        console.log('[MCP-CS] Background ping OK:', response);
      }
    });
  } catch(e) {
    console.error('[MCP-CS] Background ping exception:', e.message);
  }
})();
