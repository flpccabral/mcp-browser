/**
 * background.js — Service Worker (Manifest V3)
 * Comunicação entre extensão Chrome e MCP Server via WebSocket.
 */

(function () {
  'use strict';

  // ───────────────────────────────────────────────
  // Estado global
  // ───────────────────────────────────────────────
  const STATE = {
    ws: null,
    wsUrl: 'ws://localhost:8765',
    connected: false,
    reconnectTimer: null,
    reconnectDelay: 2000,
    recording: false,
    capturedRequests: 0,
    capturedDomEvents: 0,
    pendingCommands: new Map(), // commandId -> {resolve, reject, timer}
    commandId: 0,
  };

  // ───────────────────────────────────────────────
  // WebSocket lifecycle
  // ───────────────────────────────────────────────
  async function getAuthToken() {
    try {
      const { mcpToken } = await chrome.storage.local.get('mcpToken');
      return mcpToken || null;
    } catch (e) {
      return null;
    }
  }

  async function connectWebSocket() {
    if (STATE.ws?.readyState === WebSocket.OPEN) return;
    if (STATE.ws?.readyState === WebSocket.CONNECTING) return;

    const token = await getAuthToken();
    if (!token) {
      console.warn('[MCP Bridge] Token ausente — configure em Options/Popup');
      broadcastToPopup({ type: 'status', connected: false, needsToken: true });
      scheduleReconnect();
      return;
    }
    const url = `${STATE.wsUrl}?token=${encodeURIComponent(token)}`;

    try {
      console.log('[MCP Bridge] Conectando ao WebSocket:', STATE.wsUrl);
      STATE.ws = new WebSocket(url);

      STATE.ws.onopen = () => {
        console.log('[MCP Bridge] WebSocket conectado');
        STATE.connected = true;
        STATE.reconnectDelay = 2000;
        // Cancela qualquer timer de reconexão pendente
        if (STATE.reconnectTimer) {
          clearTimeout(STATE.reconnectTimer);
          STATE.reconnectTimer = null;
        }
        broadcastToPopup({ type: 'status', connected: true });
        // Envia identificação da extensão
        sendToServer({
          type: 'hello',
          source: 'chrome-extension',
          version: chrome.runtime.getManifest().version,
        });
      };

      STATE.ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          console.log('[MCP Bridge] Mensagem do servidor:', msg.type, msg);
          handleServerMessage(msg);
        } catch (err) {
          console.error('[MCP Bridge] Erro ao parse mensagem:', err);
        }
      };

      STATE.ws.onclose = (event) => {
        console.log('[MCP Bridge] WebSocket fechado. Code:', event.code, 'Reason:', event.reason, 'WasClean:', event.wasClean);
        STATE.connected = false;
        STATE.ws = null;
        broadcastToPopup({ type: 'status', connected: false });
        scheduleReconnect();
      };

      STATE.ws.onerror = (err) => {
        console.error('[MCP Bridge] WebSocket error:', err);
        STATE.connected = false;
      };
    } catch (err) {
      console.error('[MCP Bridge] Falha ao criar WebSocket:', err);
      scheduleReconnect();
    }
  }

  function disconnectWebSocket() {
    if (STATE.reconnectTimer) {
      clearTimeout(STATE.reconnectTimer);
      STATE.reconnectTimer = null;
    }
    if (STATE.ws) {
      try {
        STATE.ws.close();
      } catch (e) {
        /* ignore */ }
      STATE.ws = null;
    }
    STATE.connected = false;
  }

  function scheduleReconnect() {
    if (STATE.ws?.readyState === WebSocket.OPEN) {
      console.log('[MCP Bridge] Já conectado, ignorando reconexão');
      return;
    }
    if (STATE.reconnectTimer) {
      console.log('[MCP Bridge] Reconnect já agendado, ignorando');
      return;
    }
    console.log('[MCP Bridge] Agendando reconexão em', STATE.reconnectDelay, 'ms');
    STATE.reconnectTimer = setTimeout(() => {
      STATE.reconnectTimer = null;
      console.log('[MCP Bridge] Executando reconexão agendada');
      connectWebSocket();
    }, STATE.reconnectDelay);
    // Backoff mais curto para MV3 (service worker pode suspender)
    STATE.reconnectDelay = Math.min(STATE.reconnectDelay + 500, 5000);
  }

  // Keep-alive via chrome.alarms para evitar suspensão do service worker
  try {
    chrome.alarms.create('ws-keepalive', { periodInMinutes: 0.3 });
    chrome.alarms.onAlarm.addListener((alarm) => {
      if (alarm.name === 'ws-keepalive' && !STATE.connected) {
        connectWebSocket();
      }
    });
  } catch(e) {
    console.log('[MCP Bridge] chrome.alarms não disponível:', e.message);
  }

  function sendToServer(msg) {
    if (STATE.ws?.readyState === WebSocket.OPEN) {
      STATE.ws.send(JSON.stringify(msg));
      return true;
    }
    return false;
  }

  // ───────────────────────────────────────────────
  // Handler de mensagens do servidor
  // ───────────────────────────────────────────────
  async function handleServerMessage(msg) {
    if (msg.type === 'command') {
      await executeCommand(msg);
      return;
    }

    if (msg.type === 'response' && msg.id) {
      const pending = STATE.pendingCommands.get(msg.id);
      if (pending) {
        STATE.pendingCommands.delete(msg.id);
        clearTimeout(pending.timer);
        if (msg.error) {
          pending.reject(new Error(msg.error));
        } else {
          pending.resolve(msg.result);
        }
      }
      return;
    }

    if (msg.type === 'ping') {
      sendToServer({ type: 'pong', timestamp: Date.now() });
      return;
    }

    if (msg.type === 'welcome') {
      console.log('[MCP Bridge] Servidor welcome recebido:', msg.server);
      return;
    }

    console.log('[MCP Bridge] Mensagem não tratada:', msg.type, msg);
  }

  // ───────────────────────────────────────────────
  // Execução de comandos vindos do servidor
  // ───────────────────────────────────────────────
  async function executeCommand(msg) {
    const { id, tool, params = {} } = msg;
    let result = null;
    let error = null;

    try {
      switch (tool) {
        case 'navigate': {
          if (params.newTab) {
            const newTab = await chrome.tabs.create({ url: params.url, active: true });
            result = { url: params.url, tabId: newTab.id, newTab: true };
          } else {
            const tab = await getActiveTab();
            const updated = await chrome.tabs.update(tab.id, { url: params.url });
            result = { url: params.url, tabId: updated.id, newTab: false };
          }
          break;
        }
        case 'new_tab': {
          const newTab = await chrome.tabs.create({ 
            url: params.url || 'about:blank', 
            active: params.active !== false 
          });
          result = { url: newTab.url, tabId: newTab.id, title: newTab.title };
          break;
        }
        case 'click': {
          const tab = await getActiveTab();
          result = await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            func: (selector, by) => {
              let el = null;
              if (by === 'css') el = document.querySelector(selector);
              else if (by === 'xpath') {
                const res = document.evaluate(selector, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
                el = res.singleNodeValue;
              } else if (by === 'text') {
                const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
                let node;
                while ((node = walker.nextNode())) {
                  if (node.textContent.includes(selector)) {
                    el = node.parentElement;
                    break;
                  }
                }
              }
              if (!el) throw new Error('Elemento não encontrado: ' + selector);
              el.scrollIntoView({ behavior: 'instant', block: 'center' });
              el.click();
              return { tag: el.tagName, id: el.id, class: el.className };
            },
            args: [params.selector, params.by || 'css'],
          });
          result = result[0]?.result;
          break;
        }
        case 'type': {
          const tab = await getActiveTab();
          result = await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            func: (selector, text, clear) => {
              const el = document.querySelector(selector);
              if (!el) throw new Error('Elemento não encontrado: ' + selector);
              el.focus();
              // Suporte para contenteditable (ProseMirror/ChatGPT)
              if (el.isContentEditable) {
                if (clear) el.innerHTML = '';
                el.innerText = text;
                el.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: text }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                return { tag: el.tagName, isContentEditable: true, value: el.innerText.substring(0, 100) };
              }
              // Input/textarea padrão
              if (clear) el.value = '';
              el.value = text;
              el.dispatchEvent(new Event('input', { bubbles: true }));
              el.dispatchEvent(new Event('change', { bubbles: true }));
              return { tag: el.tagName, value: el.value };
            },
            args: [params.selector, params.text, params.clear !== false],
          });
          result = result[0]?.result;
          break;
        }
        case 'screenshot': {
          const tab = await getActiveTab();
          const dataUrl = await chrome.tabs.captureVisibleTab(tab.windowId, { format: 'png' });
          result = { dataUrl, width: tab.width, height: tab.height };
          break;
        }
        case 'get_content': {
          const tab = await getActiveTab();
          const exec = await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            func: (selector, asHtml) => {
              if (selector) {
                const el = document.querySelector(selector);
                if (!el) return null;
                return asHtml ? el.innerHTML : el.innerText;
              }
              return asHtml ? document.documentElement.outerHTML : document.body.innerText;
            },
            args: [params.selector || null, params.as_html || false],
          });
          result = exec[0]?.result;
          break;
        }
        case 'execute_javascript': {
          const tab = await getActiveTab();
          let evalResult;
          // 1st attempt: normal eval via scripting
          try {
            const exec = await chrome.scripting.executeScript({
              target: { tabId: tab.id },
              world: 'MAIN',
              func: (code) => {
                try {
                  return { success: true, result: eval(code) };
                } catch (err) {
                  return { success: false, error: err.message };
                }
              },
              args: [params.code],
            });
            evalResult = exec[0]?.result ?? { success: false, error: 'sem resultado' };
          } catch (err) {
            evalResult = { success: false, error: err.message || String(err) };
          }
          // If CSP blocked (unsafe-eval), fall back to debugger
          const cspBlocked = evalResult && evalResult.success === false &&
            /content security policy|unsafe-eval|refused to evaluate|eval/i.test(evalResult.error || '');
          if (cspBlocked) {
            try {
              evalResult = await evalViaDebugger(tab.id, params.code);
            } catch (dbgErr) {
              evalResult = { success: false, error: `Debugger falhou: ${dbgErr.message || dbgErr}` };
            }
          }
          result = evalResult;
          break;
        }
        case 'get_dom_snapshot': {
          const tab = await getActiveTab();
          const exec = await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            func: () => {
              const getSelector = (el) => {
                if (el.id) return '#' + el.id;
                if (el.className) return el.tagName.toLowerCase() + '.' + el.className.split(' ').join('.');
                return el.tagName.toLowerCase();
              };
              const elements = [];
              document.querySelectorAll('a, button, input, select, textarea, [onclick]').forEach((el, i) => {
                if (i >= 100) return;
                const rect = el.getBoundingClientRect();
                if (rect.width === 0 && rect.height === 0) return;
                elements.push({
                  tag: el.tagName.toLowerCase(),
                  type: el.type || null,
                  id: el.id || null,
                  name: el.name || null,
                  text: el.innerText?.trim()?.substring(0, 100) || null,
                  href: el.href || null,
                  selector: getSelector(el),
                });
              });
              return {
                url: window.location.href,
                title: document.title,
                elements,
              };
            },
          });
          result = exec[0]?.result;
          break;
        }
        case 'press_key': {
          const tab = await getActiveTab();
          const exec = await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            func: (key, selector) => {
              const el = selector ? document.querySelector(selector) : document.body;
              if (!el) throw new Error('Elemento não encontrado: ' + selector);
              el.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true }));
              el.dispatchEvent(new KeyboardEvent('keyup', { key, bubbles: true }));
              return { key, selector };
            },
            args: [params.key, params.selector || null],
          });
          result = exec[0]?.result;
          break;
        }
        case 'get_url': {
          const tab = await getActiveTab();
          result = { url: tab.url };
          break;
        }
        case 'get_title': {
          const tab = await getActiveTab();
          result = { title: tab.title };
          break;
        }
        case 'go_back': {
          const tab = await getActiveTab();
          await chrome.tabs.goBack(tab.id);
          result = { action: 'go_back' };
          break;
        }
        case 'go_forward': {
          const tab = await getActiveTab();
          await chrome.tabs.goForward(tab.id);
          result = { action: 'go_forward' };
          break;
        }
        case 'reload': {
          const tab = await getActiveTab();
          await chrome.tabs.reload(tab.id);
          result = { action: 'reload' };
          break;
        }
        case 'get_visible_text': {
          const tab = await getActiveTab();
          const exec = await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            func: () => {
              const walker = document.createTreeWalker(
                document.body,
                NodeFilter.SHOW_TEXT,
                null,
                false
              );
              let node;
              let text = '';
              while ((node = walker.nextNode())) {
                if (node.parentElement && getComputedStyle(node.parentElement).display !== 'none') {
                  text += node.textContent + ' ';
                }
              }
              return text.trim().replace(/\s+/g, ' ').substring(0, 5000);
            },
          });
          result = exec[0]?.result;
          break;
        }
        case 'get_interactive_elements': {
          const tab = await getActiveTab();
          const exec = await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            func: () => {
              const selectors = [
                'a', 'button', 'input', 'select', 'textarea',
                '[onclick]', '[role="button"]'
              ];
              const found = new Set();
              const result = [];
              for (const sel of selectors) {
                for (const el of document.querySelectorAll(sel)) {
                  if (found.has(el)) continue;
                  found.add(el);
                  const rect = el.getBoundingClientRect();
                  if (rect.width === 0 && rect.height === 0) continue;
                  result.push({
                    tag: el.tagName.toLowerCase(),
                    type: el.type || null,
                    id: el.id || null,
                    class: el.className || null,
                    text: el.innerText?.trim()?.substring(0, 60) || null,
                    selector: el.id ? '#' + el.id : el.className ? el.tagName.toLowerCase() + '.' + el.className.split(' ')[0] : el.tagName.toLowerCase(),
                  });
                }
              }
              return result;
            },
          });
          result = exec[0]?.result;
          break;
        }
        case 'get_attributes': {
          const tab = await getActiveTab();
          const selector = params.selector || '';
          const attribute = params.attribute || null;
          const exec = await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            func: (sel, attr) => {
              const el = document.querySelector(sel);
              if (!el) throw new Error('Elemento não encontrado: ' + sel);
              if (attr) {
                return { [attr]: el.getAttribute(attr) };
              }
              const attrs = {};
              for (const a of el.attributes) {
                attrs[a.name] = a.value;
              }
              return attrs;
            },
            args: [selector, attribute],
          });
          result = exec[0]?.result;
          break;
        }
        case 'wait': {
          const tab = await getActiveTab();
          const condition = params.condition || 'timeout';
          const waitTimeout = params.timeout || 5000;
          const waitSelector = params.selector || null;
          
          const exec = await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            func: (cond, sel, t) => {
              return new Promise((resolve) => {
                if (cond === 'timeout') {
                  setTimeout(() => resolve(`Aguardado ${t}ms`), t);
                  return;
                }
                if (cond === 'element_visible' && sel) {
                  const start = Date.now();
                  const check = () => {
                    const el = document.querySelector(sel);
                    if (el && el.offsetParent !== null) {
                      resolve(`Elemento ${sel} está visível`);
                    } else if (Date.now() - start > t) {
                      resolve(`Timeout: Elemento ${sel} não ficou visível`);
                    } else {
                      setTimeout(check, 100);
                    }
                  };
                  check();
                  return;
                }
                if (cond === 'element_hidden' && sel) {
                  const start = Date.now();
                  const check = () => {
                    const el = document.querySelector(sel);
                    if (!el || el.offsetParent === null) {
                      resolve(`Elemento ${sel} está oculto`);
                    } else if (Date.now() - start > t) {
                      resolve(`Timeout: Elemento ${sel} não ficou oculto`);
                    } else {
                      setTimeout(check, 100);
                    }
                  };
                  check();
                  return;
                }
                if (cond === 'network_idle') {
                  // Simula network_idle com um delay maior
                  setTimeout(() => resolve('Network idle simulado'), Math.min(t, 3000));
                  return;
                }
                resolve(`Condição desconhecida: ${cond}`);
              });
            },
            args: [condition, waitSelector, waitTimeout],
          });
          result = exec[0]?.result;
          break;
        }
        case 'list_tabs': {
          const tabs = await chrome.tabs.query({});
          result = tabs.map(t => ({
            id: t.id,
            url: t.url,
            title: t.title,
            active: t.active,
            windowId: t.windowId,
          }));
          break;
        }
        case 'activate_tab': {
          const tabId = params.tabId;
          if (!tabId) { error = 'activate_tab requires tabId'; break; }
          const tabs = await chrome.tabs.query({});
          const targetTab = tabs.find(t => t.id === tabId || t.index === tabId);
          if (!targetTab) { error = 'Tab not found: ' + tabId; break; }
          await chrome.tabs.update(targetTab.id, { active: true });
          await chrome.windows.update(targetTab.windowId, { focused: true });
          result = { action: 'activate_tab', tabId: targetTab.id, title: targetTab.title };
          break;
        }
        case 'manage_session': {
          const action = params.action || '';
          if (action === 'list_tabs') {
            const tabs = await chrome.tabs.query({});
            result = tabs.map(t => ({
              id: t.id,
              url: t.url,
              title: t.title,
              active: t.active,
              windowId: t.windowId,
            }));
          } else if (action === 'start_recording') {
            STATE.recording = true;
            result = { action: 'start_recording', status: 'started' };
          } else if (action === 'stop_recording') {
            STATE.recording = false;
            result = { action: 'stop_recording', status: 'stopped' };
          } else {
            error = `manage_session action desconhecida: ${action}`;
          }
          break;
        }
        default:
          error = `Comando desconhecido: ${tool}`;
      }
    } catch (err) {
      console.error('[MCP Bridge] Erro executando comando:', tool, err);
      error = err.message || String(err);
    }

    // Envia response de volta para o servidor
    sendToServer({
      type: 'response',
      id,
      result,
      error,
    });
  }

  async function getActiveTab() {
    try {
      // Tenta janela mais recentemente focada
      const lastFocused = await chrome.windows.getLastFocused({ populate: true });
      if (lastFocused && lastFocused.tabs) {
        const activeTab = lastFocused.tabs.find(t => t.active);
        if (activeTab) return activeTab;
      }
    } catch (e) {
      console.log('[MCP Bridge] getLastFocused falhou:', e);
    }
    // Fallback: qualquer aba ativa
    const tabs = await chrome.tabs.query({ active: true });
    if (tabs.length) return tabs[0];
    // Último recurso: primeira aba normal disponível (não chrome://)
    const allTabs = await chrome.tabs.query({});
    const normalTab = allTabs.find(t => !t.url.startsWith('chrome://'));
    if (normalTab) return normalTab;
    // Cria nova aba se não houver nenhuma
    console.log('[MCP Bridge] Nenhuma aba normal encontrada, criando nova...');
    const newTab = await chrome.tabs.create({ url: 'about:blank', active: true });
    return newTab;
  }

  async function evalViaDebugger(tabId, expression) {
    const target = { tabId };
    await chrome.debugger.attach(target, '1.3');
    try {
      const res = await chrome.debugger.sendCommand(target, 'Runtime.evaluate', {
        expression,
        returnByValue: true,
        awaitPromise: true,
        userGesture: true,
      });
      if (res && res.exceptionDetails) {
        const ex = res.exceptionDetails;
        return {
          success: false,
          error: ex.exception?.description || ex.text || 'Erro na avaliação',
          via: 'debugger',
        };
      }
      return { success: true, result: res?.result?.value, via: 'debugger' };
    } finally {
      try { await chrome.debugger.detach(target); } catch (e) {}
    }
  }

  // ───────────────────────────────────────────────
  // Handlers de mensagens do content script
  // ───────────────────────────────────────────────
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (!message || !message.type) return false;

    const { type } = message;

    if (type === 'xhr' || type === 'fetch') {
      if (STATE.recording) {
        STATE.capturedRequests++;
        sendToServer({
          type: 'event',
          eventType: 'xhr',
          data: { ...message, tabId: sender.tab?.id, url: sender.url },
        });
      }
      sendResponse({ ok: true });
      return false;
    }

    if (type === 'dom') {
      if (STATE.recording) {
        STATE.capturedDomEvents++;
        sendToServer({
          type: 'event',
          eventType: 'dom',
          data: { ...message, tabId: sender.tab?.id, url: sender.url },
        });
      }
      sendResponse({ ok: true });
      return false;
    }

    if (type === 'navigation') {
      sendToServer({
        type: 'event',
        eventType: 'navigation',
        data: { ...message, tabId: sender.tab?.id },
      });
      sendResponse({ ok: true });
      return false;
    }

    // Always forward console events (errors/warnings from injected.js)
    if (type === 'event') {
      const eventType = message.eventType;
      console.log('[MCP Bridge] Received event from content:', eventType, JSON.stringify(message.data || {}).substring(0,120));
      if (eventType === 'console') {
        sendToServer({
          type: 'event',
          eventType: 'console',
          data: { ...message.data, tabId: sender.tab?.id, url: sender.url },
        });
      }
      sendResponse({ ok: true });
      return false;
    }

    if (type === 'popup_get_status') {
      sendResponse({
        connected: STATE.connected,
        recording: STATE.recording,
        capturedRequests: STATE.capturedRequests,
        capturedDomEvents: STATE.capturedDomEvents,
        wsUrl: STATE.wsUrl,
      });
      return false;
    }

    if (type === 'popup_start_recording') {
      STATE.recording = true;
      sendToServer({ type: 'event', eventType: 'recording', data: { action: 'start' } });
      broadcastToPopup({ type: 'status', recording: true });
      sendResponse({ ok: true });
      return false;
    }

    if (type === 'popup_stop_recording') {
      STATE.recording = false;
      sendToServer({ type: 'event', eventType: 'recording', data: { action: 'stop' } });
      broadcastToPopup({ type: 'status', recording: false });
      sendResponse({ ok: true });
      return false;
    }

    if (type === 'popup_export_har') {
      // Solicita HAR ao servidor
      const reqId = ++STATE.commandId;
      sendToServer({ type: 'request', tool: 'export_har', params: { id: reqId } });
      sendResponse({ ok: true, requested: true });
      return false;
    }

    if (type === 'popup_reset') {
      STATE.capturedRequests = 0;
      STATE.capturedDomEvents = 0;
      broadcastToPopup({
        type: 'status',
        connected: STATE.connected,
        recording: STATE.recording,
        requestCount: 0,
        domEventCount: 0,
      });
      sendResponse({ ok: true });
      return false;
    }

    if (type === 'popup_reconnect') {
      disconnectWebSocket();
      connectWebSocket();
      sendResponse({ ok: true });
      return false;
    }

    if (type === 'test_ping') {
      console.log('[MCP Bridge] Ping from content script at:', message.url);
      sendResponse({ ok: true, status: 'connected', wsOpen: STATE.connected });
      return true; // keep channel open for async response
    }

    return false;
  });

  // ───────────────────────────────────────────────
  // Comunicação com popup (broadcast)
  // ───────────────────────────────────────────────
  function broadcastToPopup(msg) {
    chrome.runtime.sendMessage(msg).catch(() => {
      // Popup pode não estar aberto — ignorar erro
    });
  }

  // ───────────────────────────────────────────────
  // Eventos de navegação (tabs)
  // ───────────────────────────────────────────────
  chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (changeInfo.url) {
      sendToServer({
        type: 'event',
        eventType: 'navigation',
        data: { url: changeInfo.url, timestamp: Date.now(), tabId },
      });
    }
  });

  // ───────────────────────────────────────────────
  // Startup
  // ───────────────────────────────────────────────
  connectWebSocket();

  // Mantém o service worker vivo (chrome.alarms)
  chrome.alarms?.create?.('keepalive', { periodInMinutes: 0.5 });
  chrome.alarms?.onAlarm?.addListener?.((alarm) => {
    if (alarm.name === 'keepalive') {
      console.log('[MCP Bridge] Keepalive');
      if (!STATE.connected) connectWebSocket();
    }
  });
})();
