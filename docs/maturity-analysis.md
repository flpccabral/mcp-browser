# MCP Browser — Análise de Maturidade vs Mercado

Data: 2026-07-02

## Resumo

MCP Browser tem o **maior toolset MCP do mercado** (36 ferramentas) e diferenciais únicos
(Extension mode, visual indicators, network monitoring com HAR), mas ainda não é um
projeto maduro — falta publicação em registry, documentação, e features que os líderes já têm.

---

## Projetos Comparáveis

| Projeto | Estrelas | Linguagem | Tools | Diferencial |
|---------|----------|-----------|-------|-------------|
| [executeautomation/mcp-playwright](https://github.com/executeautomation/mcp-playwright) | ★5,566 | TypeScript | 24 | Docs site, 143 device presets, multi-browser, npm published |
| [browserbase/mcp-server-browserbase](https://github.com/browserbase/mcp-server-browserbase) | ★3,390 | TypeScript | 6 | Cloud-hosted, Stagehand, enterprise stealth |
| [kontext-security/browser-use-mcp-server](https://github.com/kontext-security/browser-use-mcp-server) | ★825 | Python | ~10 | PyPI published, agent-first, SSE + stdio |
| [co-browser/agent-browser](https://github.com/co-browser/agent-browser) | N/A | N/A | N/A | Multi-MCP manager, Web UI, brew install |
| **MCP Browser (este projeto)** | ★0 | Python | **36** | **Extension mode**, **visual indicators**, **network HAR**, Hermes integration |

---

## O Que o MCP Browser Já Tem de Superior

| Diferencial | Detalhe | Concorrentes |
|-------------|---------|-------------|
| **36 ferramentas** | Maior toolset MCP de browser | Playwright MCP: 24, Browserbase: 6 |
| **3 modos de operação** | Playwright + CDP + Chrome Extension | Todos: 1-2 modos |
| **Extension mode** | Chrome real do usuário (cookies, sessão, extensões) | Nenhum tem |
| **Network monitoring** | Start/stop/list/export HAR de requisições | Nenhum tem completo |
| **Visual indicators** | Overlay pulsante, highlight de elementos, cores por nível de segurança | Nenhum tem |
| **Hermes integration** | Engine replacement (`browser.engine=mcp`), nomes limpos | Nenhum tem |
| **Stealth mode** | Anti-detection script (webdriver, plugins, chrome runtime) | Browserbase (pago) |
| **Qualidade de código** | mypy strict 0 erros, ruff 0 erros, 43 testes passando | Variável |

---

## O Que Falta — Por Prioridade

### 🔴 ALTA PRIORIDADE — Bloqueiam adoção

| # | Item | Estado Atual | Referência |
|---|------|-------------|------------|
| 1 | **Publicar no PyPI** | Wheel/sdist prontos, `twine check` passou, mas NÃO publicado. `pip install browser-mcp-server` não funciona. | Playwright MCP: `npm install`. browser-use: PyPI. |
| 2 | **Site de documentação** | Só README.md. Sem API reference, guia de troubleshooting, exemplos por modo. | Playwright MCP: site completo com busca. |
| 3 | **Smithery / MCP Catalog** | Zero presença em catálogos MCP. Usuários não descobrem o projeto. | Playwright MCP: badge Smithery + Glama + MseeP. |
| 4 | **Multi-browser** | Só Chromium. Sem Firefox ou WebKit. | Playwright MCP: Chromium + Firefox + WebKit. |
| 5 | **Device emulation** | Só `resize_viewport` manual. Sem presets de devices reais. | Playwright MCP: 143 presets (iPhone, Pixel, Galaxy, etc). |
| 6 | **Docker image** | Sem Dockerfile. Impossível usar em CI/CD ou servidores headless sem setup manual. | Browserbase e Playwright MCP: Docker images prontas. |

### 🟡 MÉDIA PRIORIDADE — Qualidade de produto

| # | Item | Detalhe |
|---|------|---------|
| 7 | **PDF generation** | Playwright MCP tem `playwright_save_as_pdf`. Muito útil pra recibos/relatórios. |
| 8 | **Console log capture** | Playwright MCP tem `playwright_console_logs`. Essencial pra debug de SPAs. |
| 9 | **Drag & drop** | Playwright MCP tem `playwright_drag`. Interações complexas de UI. |
| 10 | **iframe support** | Playwright MCP tem `playwright_iframe_click` / `playwright_iframe_fill`. |
| 11 | **Auto browser install** | Playwright MCP detecta falta de browser e instala automaticamente. |
| 12 | **Health endpoint** | Playwright MCP expõe `GET /health`. Essencial pra Docker healthcheck e monitoramento. |
| 13 | **Video recording** | `start_recording`/`stop_recording` estão no `manage_session` mas não documentados nem testados. |
| 14 | **Response assertion** | Playwright MCP tem `playwright_assert_response` / `playwright_expect_response`. Testes E2E. |

### 🟢 BAIXA PRIORIDADE — Marketing & Comunidade

| # | Item | Detalhe |
|---|------|---------|
| 15 | **GitHub stars** | 0 vs 5,566 do líder. Precisa de divulgação. |
| 16 | **README em inglês** | Atual está em PT-BR. Limita audiência global (90%+ dos devs MCP falam inglês). |
| 17 | **CHANGELOG.md** | Inexistente. Usuários não sabem o que mudou entre versões. |
| 18 | **ROADMAP.md** | Inexistente. Transparência sobre direção do projeto. |
| 19 | **Contributing guide** | Inexistente. Bloqueia contribuidores externos. |
| 20 | **VS Code badge** | Playwright MCP tem botão "Install in VS Code" one-click. |
| 21 | **Code generation** | Playwright MCP gera código Playwright a partir de ações. |
| 22 | **Discord / comunidade** | browser-use e Browserbase têm Discord ativo. MCP Browser: zero canais. |
| 23 | **Test coverage badge** | Sem badge no README. Transparência sobre qualidade. |
| 24 | **Dependabot / Renovate** | Sem atualização automática de dependências. |

---

## Plano de Ação

### Fase 1 — Publicação (Semana 1)

- [ ] Publicar no PyPI: `pip install browser-mcp-server`
- [ ] README.md traduzido para inglês
- [ ] Smithery catalog listing + badge no README
- [ ] Glama.ai MCP catalog listing
- [ ] Testar `pip install` em VM limpa (macOS + Linux)

### Fase 2 — Documentação (Semana 2)

- [ ] GitHub Pages com mkdocs ou docusaurus
- [ ] API reference completa (todas as 36 tools com exemplos)
- [ ] Guia de modos: Playwright vs CDP vs Extension
- [ ] Troubleshooting page (erros comuns + soluções)
- [ ] CHANGELOG.md inicial (`git log --oneline` → changelog)
- [ ] Health endpoint (`GET /health`)
- [ ] Badges no README: PyPI version, Python versions, tests, license

### Fase 3 — Features (Semanas 3-4)

- [ ] `browser_save_as_pdf` — PDF generation
- [ ] `browser_console_logs` — Console log capture
- [ ] `browser_drag` — Drag & drop
- [ ] Docker image + docker-compose.yml
- [ ] Device emulation (top 15 presets: iPhone, iPad, Pixel, Galaxy, Desktop)
- [ ] Auto browser install on first use
- [ ] Video recording documentation + tests

### Fase 4 — Comunidade (Contínuo)

- [ ] Divulgar no r/mcp, r/LocalLLaMA, r/Python
- [ ] Post no X/Twitter com demo da Extension mode
- [ ] Discord server
- [ ] CONTRIBUTING.md
- [ ] ROADMAP.md
- [ ] Dependabot config
- [ ] Coverage badge (codecov.io)

---

## Comparação Tool-by-Tool

### Ferramentas que MCP Browser tem E o Playwright MCP NÃO tem

| Ferramenta | Categoria |
|------------|-----------|
| `browser_connect_to_extension` | Extension mode |
| `browser_disconnect_extension` | Extension mode |
| `browser_extension_get_network_log` | Extension network |
| `browser_extension_get_dom_snapshot` | Extension DOM |
| `browser_network_start` | Network monitoring |
| `browser_network_stop` | Network monitoring |
| `browser_network_list` | Network monitoring |
| `browser_network_clear` | Network monitoring |
| `browser_get_network_log` | Network monitoring |
| `browser_export_har` | Network monitoring |
| `browser_inject_indicator` | Visual indicators |
| `browser_remove_indicator` | Visual indicators |
| `browser_highlight_element` | Visual indicators |
| `browser_set_security_level` | Visual indicators |
| `browser_agent_task` | Autonomous agent |
| `browser_new_tab` | Tab management |
| `browser_get_title` | Page info |
| `browser_accessibility_tree` | Accessibility |
| `browser_hover` | Interaction |
| `browser_upload_file` | File operations |

### Ferramentas que o Playwright MCP tem E o MCP Browser NÃO tem

| Ferramenta | Sugestão para MCP Browser |
|------------|--------------------------|
| `playwright_save_as_pdf` | Adicionar `browser_save_as_pdf` |
| `playwright_console_logs` | Adicionar `browser_console_logs` |
| `playwright_drag` | Adicionar `browser_drag` |
| `playwright_iframe_click` | Adicionar suporte a iframe no `browser_click` |
| `playwright_iframe_fill` | Adicionar suporte a iframe no `browser_type` |
| `playwright_resize` (143 devices) | Expandir `browser_manage_session(action="resize_viewport")` |
| `playwright_custom_user_agent` | Já existe via `browser_manage_session` |
| `playwright_assert_response` | Feature nova: assertion |
| `playwright_expect_response` | Feature nova: assertion |
| `playwright_click_and_switch_tab` | Feature nova: popup handling |
| `playwright_get_visible_html` | Já existe via `browser_get_content(as_html=True)` |
| `playwright_get_visible_text` | Já existe via `browser_get_content()` |

---

## Notas

- MCP Browser tem o toolset mais completo do mercado (36 tools vs 24 do líder)
- O diferencial REAL é Extension mode — ninguém mais conecta ao Chrome do usuário real
- Visual indicators são um "delighter" que nenhum concorrente tem
- O gargalo #1 é distribuição: sem PyPI, o projeto é invisível
- Documentação é o #2: sem docs, mesmo publicado ninguém adota
- README em inglês é pré-requisito pra qualquer coisa — audiência global não lê PT-BR
