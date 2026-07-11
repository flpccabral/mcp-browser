# Relatório Técnico: Investigação de Indicadores Visuais em Agentes de Automação de Navegador

**Data:** 2026-07-01  
**Pesquisador:** Sub-agente de Investigação Técnica (Kimi Work)  
**Objetivo:** Analisar como os principais agentes de IA (Kimi WebBridge, Claude Desktop, Browser-Use, Gemini CLI, etc.) implementam indicadores visuais quando controlam o navegador Chrome do usuário, e propor um plano de implementação para o MCP Browser Server.

---

## 1. Resumo Executivo

Durante esta investigação, analisamos **cinco agentes/distribuições** de automação de navegador e identificamos **quatro tecnologias distintas** para indicadores visuais:

| Agente | Tecnologia de Indicador Visual | Tipo de Indicador | Persistência |
|--------|-------------------------------|-------------------|--------------|
| **Kimi WebBridge** | Chrome Tab Groups (`group_title`) | Agrupamento de abas colorido | Sessão |
| **Claude Desktop** | Chrome Extension Content Script (`agent-visual-indicator.js`) | Overlay CSS injetado na página | Tempo de execução |
| **Gemini CLI** | CDP `Runtime.evaluate` + CSS injection | Borda pulsante azul via div fixo | Tempo de execução |
| **cdpilot** | CDP + CSS overlay nativo | Green glow + cursor ripples + red toast | Tempo de execução |
| **OpenClaw Browser Relay** | Chrome Extension Badge (`chrome.action`) | Badge ON/OFF no ícone da extensão | Conexão |
| **Browser-Use** | *Nenhum nativo* — proposto via CDP overlay | — | — |

**Conclusão:** A tecnologia mais adequada para o MCP Browser Server é a **injeção de overlay CSS via CDP `Runtime.evaluate`**, pois não requer extensão Chrome, funciona com qualquer navegador Chromium-based, e pode ser facilmente ativada/desativada.

---

## 2. Metodologia

A investigação seguiu uma abordagem de **três vetores**:

1. **Pesquisa na Web:** Buscas direcionadas em documentações, issues de GitHub e análises de arquitetura.
2. **Análise Prática com Kimi WebBridge:** Navegação para `https://example.com`, inspeção do DOM, screenshots, e testes com CDP `Overlay` e `Runtime.evaluate`.
3. **Análise de Arquiteturas:** Estudo de como extensões Chrome (Claude, OpenClaw) estruturam seus content scripts e badges.

---

## 3. Análise Detalhada por Agente

### 3.1 Kimi WebBridge (Moonshot AI)

**Arquitetura:** Kimi WebBridge é uma solução local-first composta por:
- Um daemon local (`kimi-webbridge`) que escuta em `http://127.0.0.1:10086`
- Uma extensão Chrome que atua como ponte
- Comunicação via **Chrome DevTools Protocol (CDP)**

**Indicador Visual Implementado:**
- **Chrome Tab Groups:** Quando o agente abre uma aba via `navigate` com `newTab: true` e `group_title`, o Kimi WebBridge agrupa automaticamente todas as abas da mesma sessão em um grupo de abas colorido no Chrome.
- **Screenshot:** A página `https://example.com` navegada pelo Kimi WebBridge **não apresenta nenhum overlay CSS** injetado na página. O DOM continua limpo, sem divs fixos ou bordas adicionais.

**Evidência da Pesquisa:**
> "可视化任务追踪：运行时标记正在操作的浏览器标签页，不占用鼠标键盘，用户可与AI并行使用电脑。"  
> (Rastreamento visual de tarefas: marca as abas do navegador em operação durante a execução, sem ocupar mouse/teclado, permitindo que o usuário use o computador em paralelo com a IA.)

**Tecnologia:** Tab Groups nativo do Chrome (sem overlay na página).

**Prós:**
- Não interfere na renderização da página
- Visível para o usuário sem bloquear conteúdo
- Funciona nativamente no Chrome

**Contras:**
- Não mostra visualmente *dentro* da página que o agente está ativo
- Limitado ao Chrome/Edge (não funciona em Firefox/Safari)
- Não indica qual elemento específico está sendo manipulado

---

### 3.2 Claude Desktop (Anthropic) — "Claude in Chrome"

**Arquitetura:** Claude Desktop utiliza uma extensão Chrome robusta com a seguinte topologia:

```
Chrome browser
   ↓
MV3 service worker (orchestração, native messaging)
   ↓
sidepanel.html + React app (chat UI, permission manager)
   ↓
content scripts:
  - accessibility-tree.js (todas URLs, todos frames)
  - agent-visual-indicator.js (todas URLs)
  - content-script.ts (claude.ai only)
   ↓
offscreen.html (áudio, GIF generation)
   ↓
Anthropic API → native messaging → Claude desktop app / Claude Code
```

**Indicador Visual Implementado:**
- **`agent-visual-indicator.js`** — Este content script é injetado em **todas as URLs** (`<all_urls>`) e é responsável por desenhar o overlay visual na página quando o agente está ativo.
- O script provavelmente cria um div fixo na viewport com uma borda ou glow que indica "automação em andamento".
- A extensão também usa **native messaging** (`chrome.runtime.connectNative`) para comunicação bidirecional com o Claude Desktop.

**Evidência da Pesquisa:**
> "content scripts: - accessibility-tree.js (all URLs, all frames) - agent-visual-indicator.js (all URLs)"

**Tecnologia:** Chrome Extension Content Script + CSS injection.

**Prós:**
- Controle total sobre o DOM da página
- Pode responder a eventos (hover, cliques) para mostrar tooltips
- Funciona em todas as URLs sem permissões adicionais

**Contras:**
- Requer instalação de uma extensão Chrome
- Pode conflitar com CSP (Content Security Policy) de alguns sites
- Overhead de manter uma extensão (service worker, content scripts)
- Foi reportado consumo constante de 65% CPU pelo service worker em algumas versões

---

### 3.3 Gemini CLI (Google)

**Indicador Visual Proposto:**
A equipe do Gemini CLI propôs (via issue no GitHub) injetar um overlay CSS via CDP:

```javascript
// Injetado via evaluate_script após conexão
(() => {
  const overlay = document.createElement('div');
  overlay.id = '__gemini_automation_overlay';
  overlay.style.cssText = `
    position: fixed; inset: 0; z-index: 2147483647;
    pointer-events: none;
    border: 3px solid rgba(66, 133, 244, 0.4);
    animation: __gemini_pulse 2s ease-in-out infinite;
  `;
  const style = document.createElement('style');
  style.textContent = `
    @keyframes __gemini_pulse {
      0%, 100% { border-color: rgba(66, 133, 244, 0.2); box-shadow: inset 0 0 8px rgba(66, 133, 244, 0.1); }
      50% { border-color: rgba(66, 133, 244, 0.6); box-shadow: inset 0 0 16px rgba(66, 133, 244, 0.2); }
    }
  `;
  overlay.appendChild(style);
  document.body.appendChild(overlay);
})();
```

**Tecnologia:** CDP `Runtime.evaluate` (ou `Page.addStyleOverride`) + CSS injection.

**Prós:**
- Não requer extensão Chrome
- Funciona com qualquer navegador Chromium-based
- Simples de implementar e remover
- `pointer-events: none` garante que não bloqueia cliques do usuário

**Contras:**
- Pode ser removido por scripts da página (embora raro)
- Não funciona em sites com CSP estrito que bloqueia inline styles (embora o Chrome/CDP possa contornar isso)
- Não persiste entre navegações (precisa ser re-injetado após cada `navigate`)

---

### 3.4 cdpilot

**Indicador Visual Implementado:**
O cdpilot é um CLI de automação de browser que se conecta via CDP e implementa múltiplos indicadores visuais:

1. **Green glow overlay:** Borda verde brilhante ao redor da viewport
2. **Cursor visualization:** Cursor animado mostrando onde o agente está clicando
3. **Click ripples:** Efeito de ondulação ao clicar
4. **Keystroke display:** Mostra as teclas pressionadas
5. **AI control warning:** Toast vermelho aparece quando o usuário passa o mouse sobre a página durante automação ativa

**Tecnologia:** CDP + CSS injection nativo (zero dependências, ~50KB).

**Prós:**
- Rico em feedback visual
- Não requer extensão
- Muito leve

**Contras:**
- Complexidade maior de implementação
- Pode ser intrusivo dependendo do caso de uso

---

### 3.5 OpenClaw Browser Relay (PaioClaw)

**Indicador Visual Implementado:**
- **Badge state no ícone da extensão:** Usa `chrome.action.setBadgeText` para mostrar "ON", "..." (conectando) ou "!" (erro)
- **Action title:** Tooltip descrevendo o estado da conexão
- **Visual overlay:** Também possui overlay na página via CDP relay

**Tecnologia:** Chrome Extension Badge + CDP relay + WebSocket.

**Prós:**
- Indicador visível mesmo quando o navegador está minimizado
- Estados claros (ON/OFF/erro)

**Contras:**
- Requer extensão instalada
- Badge é limitado a 4 caracteres

---

### 3.6 Browser-Use

**Indicador Visual:**
O browser-use (biblioteca Python popular para automação com LLMs) **não possui um indicador visual nativo** permanente. A comunidade propôs (via GitHub issues) adicionar:

1. Um CLI command `browser-use elements` que tira screenshots com overlays numerados sobre elementos clicáveis
2. CDP-based visual overlays para debug

**Tecnologia:** Proposto — CDP + screenshot com anotações.

---

## 4. Análise Tecnológica

### 4.1 Comparativo de Tecnologias

| Tecnologia | Requer Extensão | Persiste na Navegação | Intrusividade | Complexidade | Multi-browser |
|-----------|----------------|----------------------|--------------|-------------|---------------|
| **Chrome Tab Groups** | Sim (indireto) | Sim (sessão) | Baixa | Baixa | Chrome/Edge only |
| **Content Script (Claude)** | Sim | Não (re-injetado) | Média | Alta | Chrome/Edge only |
| **CDP Runtime.evaluate + CSS** | **Não** | Não (re-injetado) | **Baixa** | **Baixa** | **Qualquer Chromium** |
| **CDP Overlay.highlightNode** | Não | Não (tempo real) | Média | Baixa | Qualquer Chromium |
| **Extension Badge** | Sim | Sim | Muito baixa | Média | Chrome/Edge only |
| **Cursor/Click Ripples** | Não | Não | Alta | Alta | Qualquer Chromium |

### 4.2 Testes Práticos Realizados

#### Teste 1: Kimi WebBridge — Estado Inicial
- **Página:** `https://example.com`
- **Resultado:** DOM limpo, nenhum elemento fixed/absolute overlay encontrado.
- **Screenshot:** Página renderizada normalmente, sem bordas ou indicadores.

#### Teste 2: CDP Overlay.highlightNode
- **Método:** `Overlay.enable` + `Overlay.highlightNode` no nó `<body>`
- **Resultado:** Highlight azul translúcido sobre o body + tooltip de informações do DevTools ("body 1152 × 96.08", accessibility info).
- **Screenshot:** Confirma o highlight do DevTools nativo.
- **Aplicação:** Útil para debug, mas não é um indicador de automação elegante.

#### Teste 3: CSS Overlay Injection via `Runtime.evaluate`
- **Método:** Injetar div fixo com borda azul pulsante e animação CSS via `document.createElement`
- **Resultado:** Borda azul pulsante ao redor de toda a viewport, com efeito glow.
- **Screenshot:** Confirma o overlay visual de automação.
- **Aplicação:** Ideal para indicador de "agente controlando esta página".

#### Teste 4: Tab Groups
- **Método:** Abrir aba com `group_title: "Investigação Indicadores Visuais"`
- **Resultado:** Aba agrupada em grupo colorido no Chrome.
- **Aplicação:** Útil para organização, mas não indica atividade dentro da página.

---

## 5. Recomendação para o MCP Browser Server

### 5.1 Tecnologia Selecionada: CDP Runtime.evaluate + CSS Injection

**Por quê:**
1. **Não requer extensão Chrome** — O MCP Browser Server já se conecta via CDP (`chrome.debugger` ou `chrome.remote-debugging-port`), então pode usar `Runtime.evaluate` diretamente.
2. **Funciona em qualquer Chromium** — Chrome, Edge, Brave, Opera, etc.
3. **Baixa intrusividade** — Com `pointer-events: none` e bordas sutis, não bloqueia a interação do usuário.
4. **Fácil de implementar** — ~20 linhas de JavaScript injetadas via CDP.
5. **Fácil de remover** — Basta remover o elemento pelo ID ou recarregar a página.
6. **Não conflita com CSP** — CDP opera no nível do browser, contornando restrições CSP de inline scripts/styles.

### 5.2 Implementação Recomendada

```javascript
// === INJEÇÃO DO OVERLAY ===
// Chamada via CDP: Runtime.evaluate

(() => {
  // Evita duplicar overlay
  if (document.getElementById('__mcp_browser_overlay')) return;

  const overlay = document.createElement('div');
  overlay.id = '__mcp_browser_overlay';
  overlay.style.cssText = `
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    z-index: 2147483647;
    pointer-events: none;
    border: 3px solid rgba(52, 152, 219, 0.5);
    border-radius: 0;
    animation: __mcp_pulse 2s ease-in-out infinite;
    box-sizing: border-box;
  `;

  const badge = document.createElement('div');
  badge.style.cssText = `
    position: fixed;
    top: 8px; right: 8px;
    z-index: 2147483648;
    pointer-events: none;
    background: rgba(52, 152, 219, 0.9);
    color: white;
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 11px;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 4px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
  `;
  badge.textContent = 'MCP Browser';

  const style = document.createElement('style');
  style.textContent = `
    @keyframes __mcp_pulse {
      0%, 100% { 
        border-color: rgba(52, 152, 219, 0.3); 
        box-shadow: inset 0 0 12px rgba(52, 152, 219, 0.1); 
      }
      50% { 
        border-color: rgba(52, 152, 219, 0.7); 
        box-shadow: inset 0 0 24px rgba(52, 152, 219, 0.25); 
      }
    }
  `;

  overlay.appendChild(style);
  overlay.appendChild(badge);
  document.body.appendChild(overlay);
})();
```

```javascript
// === REMOÇÃO DO OVERLAY ===
// Chamada via CDP: Runtime.evaluate

(() => {
  const el = document.getElementById('__mcp_browser_overlay');
  if (el) el.remove();
})();
```

---

## 6. Plano de Implementação para o MCP Browser Server

### Fase 1: Indicador de Sessão Ativa (MVP)
**Objetivo:** Mostrar visualmente quando o MCP Browser Server está controlando uma página.

**Tarefas:**
1. Adicionar método `injectSessionIndicator()` no servidor MCP
2. Após cada `navigate` ou `connect`, injetar o overlay CSS via CDP `Runtime.evaluate`
3. Adicionar opção `showIndicator` (default: `true`) na configuração do servidor
4. Remover o overlay ao desconectar (`disconnect`) ou ao fechar a sessão

**Entregável:** Overlay com borda pulsante azul e badge "MCP Browser" no canto superior direito.

### Fase 2: Indicador de Elemento Ativo
**Objetivo:** Mostrar qual elemento o agente está prestes a clicar/interagir.

**Tarefas:**
1. Antes de cada ação (`click`, `fill`, `type`), usar `Overlay.highlightNode` via CDP para destacar o elemento alvo
2. Aguardar 500ms antes da ação (para o usuário ver)
3. Remover o highlight após a ação

**Entregável:** Highlight estilo DevTools no elemento que será interagido.

### Fase 3: Indicador de Ação em Tempo Real
**Objetivo:** Mostrar o que o agente está fazendo no momento (clicando, digitando, scrollando).

**Tarefas:**
1. **Click indicator:** Injetar um ripple/círculo animado na coordenada do clique
2. **Type indicator:** Mostrar um cursor pulsante no campo de input ativo
3. **Scroll indicator:** Mostrar uma seta de direção na borda da viewport

**Entregável:** Feedbacks visuais ricos para cada tipo de ação.

### Fase 4: Indicador de Status no Navegador (Chrome Tab Groups)
**Objetivo:** Se o navegador for Chrome, agrupar abas controladas pelo agente.

**Tarefas:**
1. Usar CDP `Target.createTarget` com opções de grupo (se disponível)
2. Ou usar a extensão Chrome para gerenciar tab groups
3. Colorir o grupo com uma cor distinta (ex: azul)

**Entregável:** Abas do agente agrupadas e coloridas no Chrome.

### Fase 5: Indicador de Segurança (Opcional)
**Objetivo:** Alertar o usuário quando o agente está prestes a realizar ações sensíveis.

**Tarefas:**
1. Detectar ações sensíveis (submit em forms de login, cliques em "Delete", etc.)
2. Mudar a cor do overlay para **laranja** (atenção) ou **vermelho** (perigo)
3. Mostrar um toast de confirmação na página

**Entregável:** Sistema de alerta visual por nível de risco.

---

## 7. Referências e Fontes

1. **Kimi WebBridge Skill:** `kimi-webbridge/SKILL.md` (local)
2. **Kimi WebBridge Architecture:** Analytics Vidhya, I-Scoop (2026-05-19)
3. **Claude Desktop Chrome Extension Architecture:** `m365-ai-addins-snapshot/reports/ANALYSIS_REPORT.md` (GitHub)
4. **Gemini CLI Visual Overlay Proposal:** `google-gemini/gemini-cli/issues/21097` (GitHub)
5. **cdpilot Visual Feedback:** `github.com/mehmetnadir/cdpilot` (GitHub)
6. **OpenClaw Browser Relay:** `crxsoso.com` (Chrome Extension Store)
7. **Browser-Use Element Selector:** `github.com/browser-use/browser-use/issues/4274` (GitHub)
8. **CDP Overlay Domain:** `chromedevtools.github.io/devtools-protocol/tot/Overlay/`

---

## 8. Apêndice: Screenshots dos Testes

### Screenshot 1 — Estado Inicial (Kimi WebBridge)
Página `example.com` sem nenhum overlay. Confirma que Kimi WebBridge não injeta CSS na página.

### Screenshot 2 — CDP Overlay.highlightNode
Highlight azul DevTools nativo sobre o elemento `<body>` com tooltip de informações. Útil para debug, mas não elegante como indicador de automação.

### Screenshot 3 — CSS Overlay Injetado
Borda azul pulsante ao redor de toda a viewport, com efeito de glow. Ideal para indicar "agente controlando esta página".

---

*Relatório gerado em 2026-07-01. Dados coletados via pesquisa web, análise de arquiteturas de software e testes práticos com Kimi WebBridge e CDP.*
