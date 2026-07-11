/**
 * MCP Browser Bridge — Popup UI
 *
 * Gerencia a interface do popup da extensão:
 * - Exibe status de conexão e gravação
 * - Contadores de eventos
 * - Botões: start/stop recording, export HAR, reset, reconnect
 */

document.addEventListener('DOMContentLoaded', () => {
  const els = {
    connectionStatus: document.getElementById('connection-status'),
    recordingStatus: document.getElementById('recording-status'),
    reqCount: document.getElementById('req-count'),
    domCount: document.getElementById('dom-count'),
    navCount: document.getElementById('nav-count'),
    btnRecord: document.getElementById('btn-record'),
    btnRecordText: document.getElementById('btn-record-text'),
    btnExport: document.getElementById('btn-export'),
    btnReset: document.getElementById('btn-reset'),
    btnReconnect: document.getElementById('btn-reconnect'),
  };

  let state = {
    connected: false,
    recording: false,
    requestCount: 0,
    domEventCount: 0,
    navigationCount: 0,
  };

  // ───────────────────────────────────────────────────────────────────────────
  // Atualizar UI com estado atual
  // ───────────────────────────────────────────────────────────────────────────
  function updateUI() {
    if (state.connected) {
      els.connectionStatus.textContent = 'Conectado';
      els.connectionStatus.className = 'status-badge connected';
    } else {
      els.connectionStatus.textContent = 'Desconectado';
      els.connectionStatus.className = 'status-badge disconnected';
    }

    if (state.recording) {
      els.recordingStatus.textContent = 'Gravando';
      els.recordingStatus.className = 'status-badge recording';
      els.btnRecord.className = 'btn btn-danger';
      els.btnRecordText.textContent = 'Parar Gravação';
    } else {
      els.recordingStatus.textContent = 'Parada';
      els.recordingStatus.className = 'status-badge inactive';
      els.btnRecord.className = 'btn btn-primary';
      els.btnRecordText.textContent = 'Iniciar Gravação';
    }

    els.reqCount.textContent = state.requestCount;
    els.domCount.textContent = state.domEventCount;
    els.navCount.textContent = state.navigationCount;
  }

  // ───────────────────────────────────────────────────────────────────────────
  // Comunicação com background.js
  // ───────────────────────────────────────────────────────────────────────────
  async function sendMessage(type) {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage({ type }, (response) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
        } else {
          resolve(response);
        }
      });
    });
  }

  async function refreshStatus() {
    try {
      const res = await sendMessage('popup_get_status');
      if (res) {
        state = {
          connected: res.connected,
          recording: res.recording,
          requestCount: res.capturedRequests || 0,
          domEventCount: res.capturedDomEvents || 0,
          navigationCount: 0, // TODO: add to background.js
        };
        updateUI();
      }
    } catch (e) {
      console.error('Erro ao obter status:', e);
      state.connected = false;
      updateUI();
    }
  }

  // ───────────────────────────────────────────────────────────────────────────
  // Listeners de eventos
  // ───────────────────────────────────────────────────────────────────────────
  els.btnRecord.addEventListener('click', async () => {
    try {
      if (state.recording) {
        await sendMessage('popup_stop_recording');
      } else {
        await sendMessage('popup_start_recording');
      }
      await refreshStatus();
    } catch (e) {
      console.error('Erro ao toggle recording:', e);
    }
  });

  els.btnExport.addEventListener('click', async () => {
    try {
      await sendMessage('popup_export_har');
      chrome.notifications?.create({
        type: 'basic',
        iconUrl: 'icons/icon48.png',
        title: 'MCP Browser Bridge',
        message: 'Exportação HAR solicitada. Verifique o console.',
      });
    } catch (e) {
      console.error('Erro ao exportar HAR:', e);
    }
  });

  els.btnReset.addEventListener('click', async () => {
    try {
      // Reset local counters via background.js
      await sendMessage('popup_reset');
      await refreshStatus();
    } catch (e) {
      console.error('Erro ao resetar:', e);
    }
  });

  els.btnReconnect.addEventListener('click', async () => {
    try {
      await sendMessage('popup_reconnect');
      await refreshStatus();
    } catch (e) {
      console.error('Erro ao reconectar:', e);
    }
  });

  // ───────────────────────────────────────────────────────────────────────────
  // Escuta atualizações de status do background.js
  // ───────────────────────────────────────────────────────────────────────────
  chrome.runtime.onMessage.addListener((message) => {
    if (message.type === 'status') {
      if (typeof message.connected === 'boolean') {
        state.connected = message.connected;
      }
      if (typeof message.recording === 'boolean') {
        state.recording = message.recording;
      }
      updateUI();
    }
  });

  // ───────────────────────────────────────────────────────────────────────────
  // Inicialização
  // ───────────────────────────────────────────────────────────────────────────
  refreshStatus();
});
