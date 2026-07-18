---
name: browser-mcp-fronteira-e-posicionamento
description: >
  Posicionamento externo e fronteira de pesquisa do MCP Browser Server. Use ao
  comparar com browser-use, Playwright MCP ou qualquer concorrente; antes de
  reivindicar qualquer capacidade em README público, post, roadmap ou pitch;
  ao escrever sobre "estado da arte" em automação de browser; ao escolher qual
  problema aberto atacar; ao avaliar se uma feature nos diferencia ou apenas
  alcança o SOTA; ao redigir alegações de stealth ou confiabilidade
  do agente. Contém o mapa competitivo datado, a disciplina anti-inflação de
  claims e os problemas abertos candidatos com marcos falsificáveis.
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
  extensão + WebSocket loopback, com token e validação de origin).
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
`file:line` verificado em 2026-07-18.

| Capacidade | Nós (file:line) | browser-use (07/2026) | Playwright MCP (categoria) |
|---|---|---|---|
| Refs semânticas de elementos | Sim — @e refs em click/type (`src/browser_mcp/tools.py:323-343`, `:369-396`) + `browser_accessibility_tree` (`src/browser_mcp/tools.py:511`) | Índices numéricos + visão | Snapshot a11y, sem loop de agente |
| Network monitoring como tool | Sim — `browser_network_start/list` (`src/browser_mcp/tools.py:753`, `:807`) | Não como tool de 1ª classe | Não |
| Export HAR | Sim — `browser_export_har` (`src/browser_mcp/tools.py:898`) | Não | Não |
| Modo extensão sem debug port | Sim — `browser_connect_to_extension` (`src/browser_mcp/tools.py:181`) + WS com token (`hmac.compare_digest`) e validação de origin `chrome-extension://` (`src/browser_mcp/websocket_server.py`) | Não | Não |
| Agente embutido | Sim — `browser_agent_task` (`src/browser_mcp/tools.py:1072`) | Sim (núcleo do produto) | Não |
| Remoção de sinais de automação | Parcial — `navigator.webdriver` (`src/browser_mcp/browser_manager.py:52-54`) | Sim (vários) | Não |
| Benchmark público reproduzível | **Não** (lacuna aberta) | Sim (Odysseys 87.4%) | N/A |
| Retry/fallback de LLM estruturado | **Não** no nível deles | Sim | N/A |
| Modelo fine-tuned próprio | Não | Sim | N/A |

Leitura honesta da tabela: nossos diferenciais reais são **modo extensão no
browser real do usuário e network/HAR de 1ª classe**. Em confiabilidade de
agente e benchmark, browser-use está na frente — não finja o contrário.

---

## Parte B — O que provar antes de reivindicar

Disciplina anti-inflação. Toda alegação pública segue o padrão:
**comando + versão + data**. Sem os três, a alegação não sai.

| Alegação | Regra | Como provar |
|---|---|---|
| "N ferramentas" | Conte ANTES de publicar, com o grep ANCORADO. Nunca copie o número de outro doc. | `grep -c '^@app.tool' src/browser_mcp/tools.py` — em **2026-07-17** retorna **39**; o README diz **37** (`README.md:4`, `:8`, `:116`). Atenção: sem a âncora `^` o grep dá **41** (2 docstrings — falso positivo). **Divergência 37 (README) vs 39 (real) aberta** — corrija o README ou justifique antes de publicar. |
| "agente confiável" | **PROIBIDO** reivindicar. Não existe benchmark reproduzível hoje. | Só após executar a suíte de `browser-mcp-campanha-confiabilidade-do-agente` e publicar taxa + N tarefas + N runs. |
| "seguro" | O controle de segurança do projeto é a autenticação do WebSocket bridge (token via `hmac.compare_digest` + origin `chrome-extension://`). Reivindique SÓ isso, e note que não há suíte adversarial dedicada. **PROIBIDO** afirmar "automação segura/auditável" de forma ampla. | Citar `websocket_server.py` (auth do bridge). Ver [[browser-mcp-metodologia-e-prova]] B.2 para o que um teste adversarial dessa camada exigiria. |
| "stealth" | Reivindique remoção de **sinais específicos** (ex.: `navigator.webdriver`, `src/browser_mcp/browser_manager.py:52-54`). "Indetectável" é **PROIBIDO** — é infalsificável e envelhece mal. | Listar cada sinal removido com file:line. |
| Comparações com concorrentes | Sempre datadas e marcadas como voláteis. | Re-verificar fonte primária (repo/release notes) no dia da publicação. |

Barra de evidência completa: `browser-mcp-metodologia-e-prova`. Estilo e
processo de publicação: `browser-mcp-controle-de-mudancas`.

---

## Parte C — Fronteira: 2 problemas abertos

> **TUDO nesta parte é ABERTO/CANDIDATO.** Nada aqui é capacidade entregue.
> Não cite nenhum item da Parte C como feature em material público.

### Problema aberto #1 — Confiabilidade mensurável em sites legados [ABERTO/CANDIDATO]

Apenas o posicionamento aqui; o plano executável (COMO) está em
`browser-mcp-campanha-confiabilidade-do-agente`.

- **Por que o SOTA falha**: Odysseys (87.4%, 200 tarefas — 07/2026) mede
  tarefas genéricas na web moderna. Ninguém publica números em sistemas
  legados (jQuery/Prototype, dropdowns em cascata AJAX, sessões frágeis) —
  que é onde boa parte da automação corporativa vive.
- **Nosso ativo**: o modo extensão (sessão real do usuário) + network/HAR de
  1ª classe são exatamente as capacidades que sites legados exigem (login
  manual reaproveitado, mapeamento de endpoints AJAX não documentados).
- **Marco falsificável**: taxa de sucesso ≥ X% numa **suíte publicada de N
  tarefas contra um site legado reproduzível, em 3 runs**, com comando +
  versão + data. Sem suíte publicada, nenhum claim de confiabilidade.

### Problema aberto #2 — Agente que gera playbooks reutilizáveis [ABERTO/CANDIDATO]

- **A ideia**: o agente explora o site UMA vez e emite um mapa executável
  (endpoints AJAX, seletores/@e refs, ordem de preenchimento) que roda
  depois **sem LLM**.
- **Por que o SOTA falha**: em browser-use e afins, cada execução re-paga o
  custo de LLM e re-comete os mesmos erros — não há destilação da exploração
  em artefato determinístico.
- **Nosso ativo**: a matéria-prima já é capturada — network monitoring
  (`src/browser_mcp/tools.py:753`, `:807`, HAR `:898`) + accessibility tree
  com @e refs (`:511`). Um fluxo explorado uma vez tem tudo que um executor
  determinístico precisaria: endpoints AJAX, refs de elementos e ordem de
  preenchimento.
- **3 primeiros passos neste repo**:
  1. Definir o esquema do playbook (JSON/YAML: passos, @e refs ou seletores,
     requests esperadas, asserts).
  2. Escrever um executor determinístico (sem LLM) que consome o playbook
     usando as tools existentes (`browser_navigate`, `browser_click`,
     `browser_type`, `browser_network_list`).
  3. Instrumentar `browser_agent_task` (`src/browser_mcp/tools.py:1072`)
     para registrar trajetória (ação + @e ref + requests disparadas) e
     emitir o playbook ao final de uma exploração bem-sucedida.
- **Marco falsificável**: você tem um resultado quando **um playbook gerado
  automaticamente re-executa o fluxo sem LLM com sucesso em 3 runs**.

### Priorização candidata

| # | Problema | Esforço até o marco | Diferenciação vs SOTA |
|---|---|---|---|
| 1 | Confiabilidade legado | Médio (construir suíte) | Média — nicho defensável |
| 2 | Playbooks sem LLM | Alto (novo subsistema) | Alta — ataca o custo estrutural do SOTA |

---

## Proveniência e manutenção

- **Escrito em**: 2026-07-18.
- **Verificado no código em 2026-07-18**: contagem de tools
  (`grep -c '^@app.tool' src/browser_mcp/tools.py` → **39**; sem âncora dá 41
  por 2 docstrings) e todos os `file:line` da tabela A.4 e da Parte C.
- **Fonte histórica**: `git show cbc8e28:aprendizado_webbridge.md` (benchmark
  WebBridge, origem das @e refs e do modo extensão).
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
  referência de automação, campanha de confiabilidade
  (#2), metodologia e prova (barra de evidência).
