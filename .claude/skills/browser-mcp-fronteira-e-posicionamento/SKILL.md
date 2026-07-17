---
name: browser-mcp-fronteira-e-posicionamento
description: >
  Posicionamento externo e fronteira de pesquisa do MCP Browser Server. Use ao
  comparar com browser-use, Playwright MCP ou qualquer concorrente; antes de
  reivindicar qualquer capacidade em README público, post, roadmap ou pitch;
  ao escrever sobre "estado da arte" em automação de browser; ao escolher qual
  problema aberto atacar; ao avaliar se uma feature nos diferencia ou apenas
  alcança o SOTA; ao redigir alegações de segurança, stealth ou confiabilidade
  do agente. Contém o mapa competitivo datado, a disciplina anti-inflação de
  claims e os 3 problemas abertos candidatos com marcos falsificáveis.
---

# Fronteira e posicionamento — MCP Browser Server

Esta skill responde três perguntas: **onde estamos no mapa** (Parte A),
**o que podemos afirmar publicamente** (Parte B) e **onde este projeto pode
avançar o estado da arte** (Parte C).

Regra mestra: capacidades NOSSAS só entram em qualquer texto com `file:line`
verificado no dia da escrita. Dados de concorrentes são VOLÁTEIS e entram
sempre com data.

## Quando NÃO usar esta skill

- **Executar ou depurar o servidor** → `browser-mcp-executar-e-operar`,
  `browser-mcp-playbook-de-depuracao`.
- **Detalhes internos do perfil restrito** (implementação, flags, testes) →
  `browser-mcp-perfil-restrito`. Aqui só o posicionamento dele como problema
  aberto #1.
- **Planejar/executar o benchmark de confiabilidade** →
  `browser-mcp-campanha-confiabilidade-do-agente`. Aqui só o porquê do nicho.
- **Barra de evidência e metodologia de prova** →
  `browser-mcp-metodologia-e-prova`.
- **Estilo de docs, changelog, versionamento** →
  `browser-mcp-controle-de-mudancas`.
- **Decisões de arquitetura interna** → `browser-mcp-contrato-de-arquitetura`;
  histórico de decisões → `browser-mcp-arqueologia-de-falhas`.
- **Referência de uso das tools** → `browser-automacao-referencia`,
  `browser-mcp-diagnosticos-e-ferramentas`.
- Build/ambiente/config → `browser-mcp-build-e-ambiente`,
  `browser-mcp-config-e-flags`; QA → `browser-mcp-validacao-e-qa`.

---

## Parte A — Mapa competitivo

> **AVISO DE VOLATILIDADE**: dados de concorrentes coletados em **07/2026**.
> Stars, versões e features de terceiros mudam semanalmente. Re-verifique
> antes de citar em qualquer material público (ver "Proveniência e
> manutenção").

### A.1 browser-use (dados de 07/2026 — voláteis)

O concorrente dominante em "agente de browser open source":

| Atributo (07/2026) | Valor |
|---|---|
| Stars / versão / licença | 104k / v0.13.4 / MIT |
| Driver | CDP puro, sem Playwright |
| Representação de elementos | Índices numéricos + `use_vision` (screenshots) |
| Resiliência | retry 5x, `fallback_llm`, `max_failures=3`, `flash_mode` |
| Saída | Estruturada via Pydantic |
| Benchmark | Odysseys: 87.4% em 200 tarefas |
| Modelo próprio | Fine-tuned `ChatBrowserUse` |
| Comercial | Cloud com CAPTCHA solving |

O que browser-use **não tem** (verificado 07/2026):
- Modo extensão sem debug port (conexão ao Chrome real do usuário via
  extensão + WebSocket loopback).
- Perfil restrito de segurança (allowlist de domínio/tool/hash de script
  imposta pelo servidor, não pelo prompt).
- Network/HAR como tool de primeira classe exposta ao agente.

### A.2 Kimi WebBridge (referência histórica interna)

Benchmark interno que originou três dos nossos diferenciais. Fonte:
`git show cbc8e28:aprendizado_webbridge.md`. De lá vieram:
- As **@e refs** sobre árvore de acessibilidade (mais estáveis que CSS).
- O **modo extensão** operando no perfil real do usuário (cookies, logins).
- O **network monitoring nativo** como comando de primeira classe
  (`network start/list/detail`), que replicamos como tools MCP.

### A.3 Playwright MCP oficial e afins (categoria)

Categoria: servidor MCP fino sobre Playwright. Expõem primitivas
(navigate/click/snapshot) e param aí — **sem agente embutido, sem camada de
segurança**. Quem monta o loop de decisão e quem decide o que é permitido é
o cliente. Competem em "dar mãos ao LLM", não em "agente confiável" nem em
"automação segura".

### A.4 Tabela de capacidades (só o verificável no nosso código)

Colunas de terceiros refletem 07/2026 e são voláteis. Coluna "Nós" cita
`file:line` verificado em 2026-07-17.

| Capacidade | Nós (file:line) | browser-use (07/2026) | Playwright MCP (categoria) |
|---|---|---|---|
| Refs semânticas de elementos | Sim — @e refs em click/type (`src/browser_mcp/tools.py:323-343`, `:369-396`) + `browser_accessibility_tree` (`src/browser_mcp/tools.py:511`) | Índices numéricos + visão | Snapshot a11y, sem loop de agente |
| Network monitoring como tool | Sim — `browser_network_start/list` (`src/browser_mcp/tools.py:753`, `:807`) | Não como tool de 1ª classe | Não |
| Export HAR | Sim — `browser_export_har` (`src/browser_mcp/tools.py:898`) | Não | Não |
| Modo extensão sem debug port | Sim — `browser_connect_to_extension` (`src/browser_mcp/tools.py:181`) + WS com token e validação de origin `chrome-extension://` (`src/browser_mcp/websocket_server.py:220-229`, `:260-265`) | Não | Não |
| Perfil restrito (allowlist domínio/tool/hash JS, loopback forçado) | Sim — `src/browser_mcp/restricted_profile.py:39-44` (hosts), `:76` (tools), `:101` (hashes, vazio = rejeita tudo, `:114-116`), `:242` (loopback); imposto no WS em `src/browser_mcp/websocket_server.py:74-84` | Não (modelo: confiar no agente/prompt) | Não |
| Testes adversariais de segurança | Sim — 42 testes em `tests/test_restricted_profile.py` (look-alike `:63`, subdomínio `:66`, loopback `:352-354`); **2 falham hoje** porque o WIP intencional do dono expandiu as allowlists (ver [[browser-mcp-perfil-restrito]]) | Não publicado | Não |
| Agente embutido | Sim — `browser_agent_task` (`src/browser_mcp/tools.py:1072`) | Sim (núcleo do produto) | Não |
| Remoção de sinais de automação | Parcial — `navigator.webdriver` (`src/browser_mcp/browser_manager.py:52-54`) | Sim (vários) | Não |
| Benchmark público reproduzível | **Não** (lacuna aberta) | Sim (Odysseys 87.4%) | N/A |
| Retry/fallback de LLM estruturado | **Não** no nível deles | Sim | N/A |
| Modelo fine-tuned próprio | Não | Sim | N/A |

Leitura honesta da tabela: nossos diferenciais reais são **segurança
verificável, modo extensão e network de 1ª classe**. Em confiabilidade de
agente e benchmark, browser-use está na frente — não finja o contrário.

---

## Parte B — O que provar antes de reivindicar

Disciplina anti-inflação. Toda alegação pública segue o padrão:
**comando + versão + data**. Sem os três, a alegação não sai.

| Alegação | Regra | Como provar |
|---|---|---|
| "N ferramentas" | Conte ANTES de publicar, com o grep ANCORADO. Nunca copie o número de outro doc. | `grep -c '^@app.tool' src/browser_mcp/tools.py` — em **2026-07-17** retorna **39**; o README diz **37** (`README.md:4`, `:8`, `:116`). Atenção: sem a âncora `^` o grep dá **41** (2 docstrings — falso positivo). **Divergência 37 (README) vs 39 (real) aberta** — corrija o README ou justifique antes de publicar. |
| "agente confiável" | **PROIBIDO** reivindicar. Não existe benchmark reproduzível hoje. | Só após executar a suíte de `browser-mcp-campanha-confiabilidade-do-agente` e publicar taxa + N tarefas + N runs. |
| "seguro" | Reivindique SOMENTE o que `tests/test_restricted_profile.py` prova adversarialmente (42 testes: look-alike, subdomínio, tool fora da allowlist, hash não aprovado, bind loopback). Hoje **2 testes falham** por WIP intencional (allowlists expandidas) — não reivindique "verde" até ressincronizar (ver [[browser-mcp-perfil-restrito]]). | `.venv/bin/python -m pytest tests/test_restricted_profile.py` verde + citar os casos adversariais. "Seguro" vira "bloqueia X, Y, Z sob perfil restrito — testado". |
| "stealth" | Reivindique remoção de **sinais específicos** (ex.: `navigator.webdriver`, `src/browser_mcp/browser_manager.py:52-54`). "Indetectável" é **PROIBIDO** — é infalsificável e envelhece mal. | Listar cada sinal removido com file:line. |
| Comparações com concorrentes | Sempre datadas e marcadas como voláteis. | Re-verificar fonte primária (repo/release notes) no dia da publicação. |

Barra de evidência completa: `browser-mcp-metodologia-e-prova`. Estilo e
processo de publicação: `browser-mcp-controle-de-mudancas`.

---

## Parte C — Fronteira: 3 problemas abertos

> **TUDO nesta parte é ABERTO/CANDIDATO.** Nada aqui é capacidade entregue.
> Não cite nenhum item da Parte C como feature em material público.

### Problema aberto #1 — Automação segura auditável no browser real [ABERTO/CANDIDATO]

- **Por que o SOTA falha**: o modelo do browser-use (07/2026) é confiar no
  agente — sem allowlist de domínio imposta pelo runtime, sem hash de
  scripts, sem bind loopback obrigatório. Segurança por prompt não é
  garantia verificável.
- **Nosso ativo**: `src/browser_mcp/restricted_profile.py` (allowlist de
  hosts `:39-44`, tools `:76`, hashes SHA-256 com rejeição por default
  `:101`/`:114-116`, loopback `:242`, ativação por `IFOOD_RESTRICTED_MODE=1`
  `:31`) + modo extensão (`src/browser_mcp/tools.py:181`,
  `src/browser_mcp/websocket_server.py:220-265`) + 44 testes adversariais
  (todos passando em 2026-07-17 — ver [[browser-mcp-perfil-restrito]]).
- **3 primeiros passos neste repo** (cada um relaxa/mexe num default de
  segurança → **todos passam pelo gate de [[browser-mcp-controle-de-mudancas]]**;
  mudança de segurança não entra sem o processo):
  1. Popular `ALLOWED_SCRIPT_HASHES` (hoje vazio) com os scripts do fluxo
     do piloto nos hosts permitidos (portal do parceiro), via
     `compute_script_hash` — via gate de
     [[browser-mcp-controle-de-mudancas]].
  2. ~~Commitar a integração~~ **FEITO em 2026-07-17** (commit `ed98aac`):
     enforcement integrado em `tools.py`/`websocket_server.py`, testes
     sincronizados (44 passando), allowlist ajustada ao escopo do piloto
     (`gestordepedidos` removido).
  3. Teste E2E adversarial do modo restrito de ponta a ponta (não só
     unitário): servidor real + extensão real + tentativas hostis.
- **Marco falsificável**: você tem um resultado quando **um fluxo real
  completa em modo restrito E todos os ataques adversariais (subdomínio não
  listado, domínio look-alike, JS não aprovado, bind em interface externa)
  são BLOQUEADOS** — qualquer ataque que passe invalida o claim.
- Detalhes de implementação: `browser-mcp-perfil-restrito`.

### Problema aberto #2 — Confiabilidade mensurável em sites legados [ABERTO/CANDIDATO]

Apenas o posicionamento aqui; o plano executável (COMO) está em
`browser-mcp-campanha-confiabilidade-do-agente`.

- **Por que o SOTA falha**: Odysseys (87.4%, 200 tarefas — 07/2026) mede
  tarefas genéricas na web moderna. Ninguém publica números em sistemas
  legados PT-BR (jQuery, dropdowns em cascata, sessões frágeis) — que é
  onde a automação corporativa brasileira vive.
- **Nosso ativo**: o nicho legado PT-BR com caso público reproduzível —
  **i-Educar** com credenciais demo `comunidade` / `Comunidade@1`
  (verificado em `git show cbc8e28:relatorio_ieducar.md`, que documenta
  login, filtros em cascata e endpoints AJAX do diário de classe).
- **Marco falsificável**: taxa de sucesso ≥ X% numa **suíte publicada de N
  tarefas i-Educar, em 3 runs**, com comando + versão + data. Sem suíte
  publicada, nenhum claim de confiabilidade.

### Problema aberto #3 — Agente que gera playbooks reutilizáveis [ABERTO/CANDIDATO]

- **A ideia**: o agente explora o site UMA vez e emite um mapa executável
  (endpoints AJAX, seletores/@e refs, ordem de preenchimento) que roda
  depois **sem LLM**.
- **Por que o SOTA falha**: em browser-use e afins, cada execução re-paga o
  custo de LLM e re-comete os mesmos erros — não há destilação da exploração
  em artefato determinístico.
- **Nosso ativo**: a matéria-prima já é capturada — network monitoring
  (`src/browser_mcp/tools.py:753`, `:807`, HAR `:898`) + accessibility tree
  com @e refs (`:511`). E a **prova de conceito humana existe**:
  `git show cbc8e28:relatorio_ieducar.md` é exatamente esse playbook, gerado
  MANUALMENTE — tabela de endpoints `/module/DynamicInput/*` e
  `/module/Avaliacao/diarioApi` com parâmetros e formatos de resposta.
- **3 primeiros passos neste repo**:
  1. Definir o esquema do playbook (JSON/YAML: passos, @e refs ou seletores,
     requests esperadas, asserts) traduzindo manualmente o
     `relatorio_ieducar.md` para esse formato.
  2. Escrever um executor determinístico (sem LLM) que consome o playbook
     usando as tools existentes (`browser_navigate`, `browser_click`,
     `browser_type`, `browser_network_list`).
  3. Instrumentar `browser_agent_task` (`src/browser_mcp/tools.py:1072`)
     para registrar trajetória (ação + @e ref + requests disparadas) e
     emitir o playbook ao final de uma exploração bem-sucedida.
- **Marco falsificável**: você tem um resultado quando **um playbook gerado
  do i-Educar re-executa o fluxo do diário sem LLM com sucesso em 3 runs**.

### Priorização candidata

| # | Problema | Esforço até o marco | Diferenciação vs SOTA |
|---|---|---|---|
| 1 | Segurança auditável | Baixo (código existe, falta integrar+E2E) | Alta — ninguém oferece |
| 2 | Confiabilidade legado | Médio (construir suíte) | Média — nicho defensável |
| 3 | Playbooks sem LLM | Alto (novo subsistema) | Alta — ataca o custo estrutural do SOTA |

---

## Proveniência e manutenção

- **Escrito em**: 2026-07-13, na branch `etapa-1-ifood-restricted-profile`;
  re-verificado em 2026-07-17.
- **Verificado no código em 2026-07-17**: contagem de tools
  (`grep -c '^@app.tool' src/browser_mcp/tools.py` → **39**; sem âncora dá 41
  por 2 docstrings), todos os `file:line` da tabela A.4 e da Parte C, e os 42
  testes de `tests/test_restricted_profile.py` (2 falham hoje por WIP das
  allowlists expandidas).
- **Fontes históricas**: `git show cbc8e28:aprendizado_webbridge.md` e
  `git show cbc8e28:relatorio_ieducar.md` (existem no commit; o relatório
  contém caminhos de screenshots locais que NÃO são fonte — use apenas o
  texto versionado).
- **Ao editar esta skill**:
  1. **Re-verifique stars/versão/features do browser-use** antes de citar —
     os números de 07/2026 (104k, v0.13.4, Odysseys 87.4%) envelhecem rápido.
     Atualize a data em todas as menções.
  2. Re-rode o grep ANCORADO de contagem de tools
     (`grep -c '^@app.tool' ...`) e confira se a divergência README(37) vs
     código(39) foi resolvida; se sim, remova o aviso da Parte B.
  3. Re-confira cada `file:line` (refactors movem linhas).
  4. Se um problema da Parte C for entregue, mova-o para a Parte A com
     evidência (file:line + teste) e retire o rótulo ABERTO/CANDIDATO.
- **Skills irmãs**: contrato de arquitetura, controle de mudanças, build e
  ambiente, executar e operar, config e flags, playbook de depuração,
  arqueologia de falhas, diagnósticos e ferramentas, validação e QA,
  referência de automação, perfil restrito (#1), campanha de confiabilidade
  (#2), metodologia e prova (barra de evidência).
