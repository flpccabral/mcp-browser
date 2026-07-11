"""Indicadores visuais para o MCP Browser Server.
Implementa overlay CSS via page.evaluate() — Fase 1 do plano de investigação.
"""

ACTIVE_TAB_GROUP_TITLE = "MCP Browser"


def get_overlay_js(color: str = "blue") -> str:
    """Retorna o JavaScript que injeta o overlay visual de automação.
    Cores: blue (padrão), orange (atenção), red (perigo), green (concluído).
    """
    colors = {
        "blue": "rgba(52, 152, 219,", "orange": "rgba(243, 156, 18,",
        "red": "rgba(231, 76, 60,", "green": "rgba(46, 204, 113,",
    }
    c = colors.get(color, colors["blue"])
    return """
(() => {
  if (document.getElementById('__mcp_browser_overlay')) return;

  const overlay = document.createElement('div');
  overlay.id = '__mcp_browser_overlay';
  overlay.style.cssText = `
    position: fixed; top: 0; left: 0; right: 0; bottom: 0;
    z-index: 2147483647; pointer-events: none;
    border: 3px solid """ + c + """ 0.5);
    animation: __mcp_pulse 2s ease-in-out infinite;
    box-sizing: border-box;
  `;

  const badge = document.createElement('div');
  badge.style.cssText = `
    position: fixed; top: 8px; right: 8px;
    z-index: 2147483648; pointer-events: none;
    background: """ + c + """ 0.9); color: white;
    font-family: system-ui, sans-serif; font-size: 11px;
    font-weight: 600; padding: 4px 10px;
    border-radius: 4px; letter-spacing: 0.5px;
    text-transform: uppercase;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
  `;
  badge.textContent = 'MCP Browser';

  const style = document.createElement('style');
  style.textContent = `
    @keyframes __mcp_pulse {
      0%, 100% { opacity: 0.7; }
      50% { opacity: 1; }
    }
  `;

  overlay.appendChild(style);
  overlay.appendChild(badge);
  document.body.appendChild(overlay);
})();
"""


def get_remove_overlay_js() -> str:
    """Retorna o JavaScript que remove o overlay."""
    return """
(() => {
  const el = document.getElementById('__mcp_browser_overlay');
  if (el) el.remove();
})();
"""


def get_highlight_element_js() -> str:
    """Retorna o JavaScript que destaca um elemento específico (Fase 2).
    O seletor é passado como argumento via page.evaluate(js, selector)
    para evitar JS injection via f-string interpolation.
    """
    return """
(selector) => {
  const el = document.querySelector(selector);
  if (!el) return;
  const orig = el.style.outline;
  el.style.outline = '3px solid rgba(52, 152, 219, 0.8)';
  el.style.outlineOffset = '2px';
  setTimeout(() => { el.style.outline = orig; }, 1500);
}
"""


def get_status_overlay_js() -> str:
    """Retorna JavaScript que atualiza o badge de status (Fase 3).
    O status é passado como argumento via page.evaluate(js, status)
    para evitar JS injection via f-string interpolation.

    status: 'clicking', 'typing', 'scrolling', 'reading', 'error', 'done'
    """
    return """
(status) => {
  const colors = {
    "clicking": "rgba(231, 76, 60, 0.9)",
    "typing": "rgba(241, 196, 15, 0.9)",
    "scrolling": "rgba(46, 204, 113, 0.9)",
    "reading": "rgba(52, 152, 219, 0.9)",
    "error": "rgba(231, 76, 60, 1.0)",
    "done": "rgba(46, 204, 113, 1.0)",
  };
  const color = colors[status] || "rgba(52, 152, 219, 0.9)";
  const badge = document.querySelector('#__mcp_browser_overlay div');
  if (badge) {
    badge.style.background = color;
    badge.textContent = 'MCP BROWSER — ' + status.toUpperCase();
  }
}
"""


def get_click_ripple_js() -> str:
    """Retorna JavaScript que cria ripple de clique (Fase 3).
    As coordenadas são passadas como argumentos via page.evaluate(js, x, y)
    para evitar JS injection via f-string interpolation.
    """
    return """
({x, y}) => {
  const ripple = document.createElement('div');
  ripple.style.cssText = 'position: fixed; left: ' + (x - 10) + 'px; top: ' + (y - 10) + 'px; ' +
    'width: 20px; height: 20px; z-index: 2147483649; pointer-events: none; ' +
    'background: rgba(52, 152, 219, 0.4); border-radius: 50%; ' +
    'animation: __mcp_ripple 0.6s ease-out forwards;';
  const style = document.createElement('style');
  style.textContent = `
    @keyframes __mcp_ripple {
      0% { transform: scale(1); opacity: 1; }
      100% { transform: scale(4); opacity: 0; }
    }
  `;
  ripple.appendChild(style);
  document.body.appendChild(ripple);
  setTimeout(() => ripple.remove(), 600);
}
"""
