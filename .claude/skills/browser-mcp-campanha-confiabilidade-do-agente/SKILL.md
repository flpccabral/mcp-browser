---
name: browser-mcp-campanha-confiabilidade-do-agente
description: >-
  Campanha SISTEMÁTICA (medir→endurecer→promover) para melhorar a CONFIABILIDADE do
  agente LLM do MCP Browser (loop OBSERVE→THINK→CHECK→ACT→RECORD em
  src/browser_mcp/agent.py). Use quando: "melhorar confiabilidade do agente",
  "aumentar taxa de sucesso", "benchmark do agente", "medir sucesso do agente",
  "erros de parse do LLM", "browser_agent_task não completa de forma sistêmica",
  ou quando alguém propõe endurecer parsing/retry/observação do agente. Fornece:
  Fase 0 (harness de benchmark — primeiro entregável, pois HOJE não medimos nada),
  Fase 1 (endurecer _parse_response), Fase 2 (resiliência em camadas: retry/backoff/
  fallback), Fase 3 (observação melhor), Fase 4 (promoção via controle de mudanças),
  menu de soluções ranqueado e caminhos comprovadamente errados cercados. NÃO use para
  triagem pontual de um bug em runtime — um agente que "entra em loop" / "estoura
  iterações" pontualmente é sintoma de runtime → browser-mcp-playbook-de-depuracao.
---

# Campanha: confiabilidade do agente LLM

Este é o problema mais difícil em aberto do repositório. O dono declarou: a
CONFIABILIDADE do agente (`src/browser_mcp/agent.py`, classe `BrowserAgent`, loop
`execute_task` OBSERVE→THINK→CHECK→ACT→RECORD) é o alvo. O SOTA público
(browser-use, 104k stars) reporta 87.4% em 200 tarefas do benchmark Odysseys
(dado externo, 2026-07-13). **Nós não medimos nada.** Toda esta campanha existe
para trocar "acho que melhorou" por um número.

## Regra de ouro (leia antes de qualquer coisa)

> **Nenhuma mudança no agente é promovida sem número de benchmark ANTES e DEPOIS.**
> Sucesso é MENSURÁVEL, nunca a olho. Prompt-tweaking sem benchmark é caminho
> cercado (ver seção "Caminhos cercados").

Toda promoção passa pelo gate de `[[browser-mcp-controle-de-mudancas]]` e não pode
introduzir NOVAS regressões. Contagem verificada 2026-07-17:
`.venv/bin/python -m pytest tests/ --collect-only -q` lista os testes coletados;
algumas suítes de smoke são flaky por timeout de rede (httpbin/networkidle). O
critério é: **sem novas regressões além dessa flakiness conhecida de rede**, não
"tudo verde cegamente".

## Quando NÃO usar esta skill

- **Um bug pontual quebrou em runtime** (click não funciona, extensão não conecta,
  timeout esperando elemento) → `[[browser-mcp-playbook-de-depuracao]]` (triagem
  sintoma→causa). Esta skill é campanha sistemática, não triagem.
- **Você quer entender POR QUE o agente é assim** (isTrusted, @e refs, histórico
  i-Educar) → `[[browser-mcp-arqueologia-de-falhas]]` e `[[browser-automacao-referencia]]`.
- **Você vai só rodar o servidor / conectar extensão** → `[[browser-mcp-executar-e-operar]]`.
- **Você quer comparar com concorrentes ou escrever claim público** →
  `[[browser-mcp-fronteira-e-posicionamento]]`.
- **A mudança não toca o agente** (nova tool, config) → outras skills.

---

## Mapa do código-alvo (verificado 2026-07-13 — RE-VERIFIQUE antes de editar)

`agent.py` tem 596 linhas. Pontos que a campanha toca:

| Símbolo | Linha | Papel na confiabilidade |
|---|---|---|
| `AGENT_SYSTEM_PROMPT` | `agent.py:15` | Prompt do loop; regra 9 (`:38`) proíbe JS-click |
| `BrowserAgent.__init__` | `agent.py:83` | `max_iterations=30` (default), `max_consecutive_errors=3` |
| `execute_task` | `agent.py:107` | Loop principal OBSERVE→THINK→CHECK→ACT→RECORD |
| `_observe` | `agent.py:222` | Monta a observação (accessibility tree + texto) |
| `_format_observation` | `agent.py:338` | O que entra no contexto do LLM (Fase 3) |
| `_parse_response` | `agent.py:355` | Extrai JSON de markdown (Fase 1) |
| `_execute_tool` | `agent.py:373` | Mapeia tool→BrowserManager, com fallbacks |
| `_prune_messages` | `agent.py:559` | Corta histórico p/ não estourar contexto |
| `_build_final_result` | `agent.py:580` | Monta o dict de resultado (fonte das categorias) |

`llm_client.py` (101 linhas): `LLMClient.chat` (`:46`) e `_chat_anthropic` (`:69`).
**NÃO há retry/backoff hoje** — só `response.raise_for_status()` em `:65` e `:95`.
Insumo direto da Fase 2.

**Defeito de arquitetura relevante (não é seu escopo consertar, mas afeta o
benchmark):** `LLMClient` NÃO é singleton. Há 2 instâncias: a de módulo em
`llm_client.py:101` (importada por `server.py:11` e inicializada em `server.py:71`)
e uma separada criada em `tools.py:16`, que é a de fato usada por `browser_agent_task`.
A que o server inicializa não é a que as tools usam. Documentado em
`[[browser-mcp-contrato-de-arquitetura]]`. **Consequência para você:** o benchmark
instancia seu próprio `LLMClient()` diretamente (igual ao caminho real das tools),
então não depende do server. Não "conserte" isso dentro da campanha de confiabilidade.

---

## Caminhos cercados (NÃO reabrir — cada um já custou tempo)

1. **"Consertar" clicks via `browser_execute_javascript`.** Eventos JS sintéticos
   têm `isTrusted=false` e são bloqueados por Google News e muitas SPAs. Já é regra
   no system prompt: `agent.py:38` (regra 9) e reforçado em `agent.py:64` (descrição
   da tool). Fundamento em `[[browser-automacao-referencia]]` e batalha em
   `[[browser-mcp-arqueologia-de-falhas]]`. **Se a sua ideia de "confiabilidade"
   envolve JS-click, pare.**

2. **Aumentar `max_iterations` como solução.** Isso MASCARA loop, não corrige.
   Um agente que precisa de mais iterações para a MESMA tarefa está patinando —
   o benchmark vai revelar iterações médias subindo sem taxa de sucesso subir.
   **Divergência real a documentar (não silenciar):** `agent.py:87` usa default
   `max_iterations=30`, mas `browser_agent_task` em `tools.py:1050` (schema) e
   `tools.py:1074` (assinatura) passa `50`. O benchmark usa `15` de propósito
   (`DEFAULT_MAX_ITERATIONS`, `benchmark_agent.py:57`) como ORÇAMENTO do experimento —
   não como cura. Se uma tarefa só passa com >15 iterações, isso é sinal de
   ineficiência a investigar, não de teto baixo.

3. **Prompt-tweaking sem benchmark.** Mexer em `AGENT_SYSTEM_PROMPT` "porque parece
   melhor" é irreproduzível. Qualquer edição de prompt é uma CANDIDATA que precisa
   passar pelo protocolo de promoção (Fase 4). Metodologia em
   `[[browser-mcp-metodologia-e-prova]]`: preveja o número ANTES de rodar.

---

## FASE 0 — Linha de base (PRIMEIRO ENTREGÁVEL)

Hoje não existe benchmark de taxa de sucesso. O primeiro entregável é o harness.
**Ele já existe nesta skill:** `scripts/benchmark_agent.py`
(decisão de manutenção documentada no fim). Nada da campanha prossegue sem uma
linha de base estável.

### O que o harness mede

- **taxa de sucesso** = tarefas completas / N (o `check` programático de cada
  tarefa passou, não só `is_complete=true` do agente).
- **iterações médias** = média de `action_count` (de `_build_final_result`,
  `agent.py:588`).
- **causa de falha categorizada** — extraída das strings REAIS de `agent.py`
  (`benchmark_agent.py::categorize`, linha ~178):
  - `parse_error` → report contém "consecutive parse errors" (`agent.py:174`)
  - `llm_error` → report contém "consecutive errors" sem "parse" (`agent.py:159`)
  - `max_iterations` → report contém "max iterations" (`agent.py:219`)
  - `false_complete` → agente disse `is_complete=true` mas o `check` da tarefa falhou
  - `harness_timeout` → `asyncio.wait_for` estourou o teto por tarefa
  - `crash` → exceção fora do agente
- **incidentes de parse por run** = `count_parse_incidents` conta
  "Could not parse LLM response" em `result["errors"]`, INCLUSIVE em tarefas que
  terminaram com sucesso. **Este é o insumo obrigatório da Fase 1** — mede quantas
  vezes o parse falhou e o loop teve que reprovocar o LLM, mesmo sem falhar a tarefa.

### As tarefas (N=8; 7 locais + 1 rede real)

Servidas por `http.server` embutido (`benchmark_agent.py::start_fixture_server`)
a partir de `scripts/fixtures/` (HTML local). Cobrem os modos de falha que importam,
incluindo cascata AJAX (o modo de falha histórico do i-Educar — selects populados
por AJAX em sequência, cada um só carrega depois do anterior):

- `extract_code`, `extract_table` — extração estática (texto e célula de tabela).
- `login_ok` — preencher 2 campos + submit + verificar.
- `search_filter`, `multi_step_price` — digitar + clicar + ler resultado dinâmico.
- `cascade_fast` (`?delay=300`), `cascade_slow` (`?delay=2500`) — **cascata AJAX**,
  estressam `browser_wait`/`network_idle`. Reproduzem o i-Educar em laboratório.
- `example_com` — única tarefa com rede real (site externo estável). Omitível com
  `--offline` para uma linha de base 100% local e determinística.

### Comandos — execução

```bash
# 0.1 — Sanidade do harness SEM LLM/browser (deve listar 8 tarefas):
.venv/bin/python .claude/skills/browser-mcp-campanha-confiabilidade-do-agente/scripts/benchmark_agent.py --list

# 0.2 — Confirme que compila:
.venv/bin/python -m py_compile .claude/skills/browser-mcp-campanha-confiabilidade-do-agente/scripts/benchmark_agent.py

# 0.3 — Run completo. Requer LLM configurado (ver [[browser-mcp-config-e-flags]]):
export LLM_PROVIDER=deepseek        # ou openai / anthropic / ollama
export LLM_API_KEY=...              # não necessário se ollama
export LLM_MODEL=deepseek-chat
PYTHONPATH=src .venv/bin/python \
  .claude/skills/browser-mcp-campanha-confiabilidade-do-agente/scripts/benchmark_agent.py \
  --out /tmp/agent_benchmark

# 0.4 — Linha de base 100% local (sem rede real; 7 tarefas):
PYTHONPATH=src .venv/bin/python \
  .claude/skills/browser-mcp-campanha-confiabilidade-do-agente/scripts/benchmark_agent.py \
  --offline --out /tmp/agent_benchmark
```

### Checkpoint 0 — números ESPERADOS

- **`--list` imprime exatamente 8 linhas** (`extract_code` … `example_com`), ou 7
  com `--offline`. **Se imprimir 0 ou erro de import** → o Python está errado; use
  o `.venv` do repo (`[[browser-mcp-build-e-ambiente]]`).
- **Cada run imprime um bloco `=== RESUMO ===`** com `sucesso: X/8`,
  `iterações médias`, `incidentes de parse (total)`, `categorias`, e o caminho do JSON.
- **Grave DOIS runs.** A linha de base EXISTE quando os dois runs diferem em no
  máximo **±1 tarefa** no total de sucessos.
  - **Se a diferença for >1 tarefa entre runs** → a linha de base é INSTÁVEL; não
    prossiga. Desvie para: (a) fixar `temperature` mais baixa no `LLMClient`
    (`llm_client.py:23`, hoje `0.1` — CANDIDATA, não commite ainda); (b) subir
    `--task-timeout` se houver `harness_timeout` intermitente; (c) checar se
    `example_com` (rede) é a fonte da variância — rode `--offline` e compare.
  - **Se `categorias` for dominado por `llm_error`** → seu LLM não está respondendo
    (chave/quota/rede). Não é problema do agente. Resolva o LLM antes.
  - **Se `categorias` for dominado por `crash`** → problema de ambiente (browser não
    sobe). Veja `[[browser-mcp-build-e-ambiente]]` (`playwright install chromium`).

### Saída obrigatória da Fase 0 (registre no controle de mudanças)

Um número de baseline com estas 4 grandezas, dos DOIS runs:
`sucesso X/8`, `iterações médias`, `total de incidentes de parse`, `distribuição de
categorias`. **Sem isto, as Fases 1–4 não têm régua.**

---

## FASE 1 — Endurecer parsing

`_parse_response` (`agent.py:355`) extrai JSON de markdown com uma cascata de regex
(`agent.py:360`→`:366`) e faz `json.loads`. Os casos de teste já existem em
`tests/test_agent.py` (`test_parse_response_markdown_json` `:145`, `raw_json` `:160`,
`invalid_text` `:173`, `empty` `:181`, `nested_markdown` `:188`).

**Obrigação (não pule):** meça `total_parse_incidents` na LINHA DE BASE (Fase 0)
ANTES de mexer em qualquer coisa. Só ataque a Fase 1 se o número justificar.

- **Se `total_parse_incidents` da baseline ≈ 0** → parsing NÃO é o gargalo. Pule
  para Fase 2 ou 3. Endurecer parsing aqui seria gold-plating sem retorno.
- **Se `total_parse_incidents` for alto** (ex.: ≥ N/2, várias reprovocações por run)
  → siga a solução #1 do menu.

**Solução #1 (CANDIDATA): saída estruturada / validação de schema.** Provedores
OpenAI-compatíveis suportam `response_format={"type":"json_object"}` no corpo de
`chat` (`llm_client.py:58`). Equivalente mínimo: exigir JSON e validar o dict
resultante contra um schema (chaves `thought`/`tool`/`params`/`is_complete`) antes
de aceitar. Anthropic (`_chat_anthropic`, `:69`) não tem o mesmo flag — trate por
provedor. **Prova de melhoria:** rode benchmark, `total_parse_incidents` deve CAIR
sem queda na taxa de sucesso. Adote via Fase 4.

---

## FASE 2 — Resiliência em camadas

Referência externa (browser-use, 2026-07): retry 5x com backoff, `fallback_llm`,
`max_failures=3` por passo, `final_response_after_failure`. Mapeie cada mecanismo
para o NOSSO código e especifique o equivalente MÍNIMO. Não copie a arquitetura
deles — copie a ideia e prove com número.

| Mecanismo browser-use | Estado no nosso código (verificado 2026-07-13) | Equivalente mínimo (CANDIDATA) |
|---|---|---|
| retry 5x + backoff no LLM | **NÃO EXISTE.** `chat` (`llm_client.py:46`) faz 1 chamada; `raise_for_status` (`:65`,`:95`) propaga direto | Envolver o POST em retry com backoff exponencial (ex.: 3–5 tentativas) para 429/5xx/timeout, DENTRO de `chat`. Não retry em 4xx de auth |
| `fallback_llm` | não existe | Segundo `LLMClient` como fallback quando o primário falha após retries. Custo: 2ª chave. Só se a baseline mostrar `llm_error` relevante |
| `max_failures=3` por passo | JÁ EXISTE parcialmente: `max_consecutive_errors=3` (`agent.py:88`), incrementado em `agent.py:155`/`:170`/`:491`, aborta em `:156`/`:171` | Manter. Avaliar se deve ser por-passo (reset em sucesso — já faz em `agent.py:151`) vs global |
| `final_response_after_failure` | JÁ EXISTE: `_build_final_result(success=False, report=...)` sempre devolve um dict com report e histórico (`agent.py:157`,`:172`,`:217`) | Manter. Talvez enriquecer o report com a última observação |

**Ordem recomendada:** ataque **retry/backoff no `chat` primeiro** (é a lacuna real
e barata). `fallback_llm` só se a baseline provar `llm_error` recorrente por
instabilidade de um provedor. **Prova:** categoria `llm_error` deve cair; taxa de
sucesso não pode regredir.

---

## FASE 3 — Observação melhor

Avalie o que entra no contexto do LLM: `_observe` (`agent.py:222`) monta URL, título,
texto visível e elementos interativos do accessibility tree (com `@e` refs), truncando
em 30 elementos (`agent.py:265`,`:273`); `_format_observation` (`agent.py:338`) é o
que de fato vira mensagem `user`. Candidatos, em ordem de custo:

1. **Resultado de rede recente na observação** (baixo custo). Hoje a observação só
   traz `network_count` (`agent.py:132`,`:343`). Para tarefas de cascata AJAX
   (`cascade_slow`), expor as últimas requisições concluídas (via
   `browser_get_network_log`) pode reduzir esperas cegas. **CANDIDATA.**
2. **Screenshots / vision** (ALTO custo — tokens + latência). **Exige justificativa
   NA LINHA DE BASE:** só considere se as falhas categorizadas mostrarem que o agente
   erra por não "ver" a página (ex.: `false_complete` alto em tarefas visuais). Sem
   essa evidência, é caminho caro sem retorno provado. Preveja o ganho ANTES
   (`[[browser-mcp-metodologia-e-prova]]`).

Regra: cada mudança de observação sobe o custo por iteração. Só vale se a taxa de
sucesso subir MAIS do que o custo — meça as duas coisas (sucesso E iterações médias).

---

## FASE 4 — Promoção (gate)

Uma mudança CANDIDATA vira ADOTADA somente se:

1. **Critério numérico:** ganho de **≥ +1 tarefa (de 8) de sucesso** sustentado em
   **3 runs consecutivos**, sem que nenhum run regrida abaixo da baseline. (Ajuste o
   limiar conforme o N de tarefas; o princípio é: melhora reprodutível, não sorte de
   1 run.) Para Fase 1, o critério alternativo é `total_parse_incidents` caindo sem
   queda de sucesso.
2. **Sem NOVAS regressões nos 85 testes:** `.venv/bin/python -m pytest tests/ -q`.
   Atenção: hoje 2 testes já falham por WIP intencional (allowlists do perfil
   restrito) e alguns são flaky por timeout de rede — o critério é não introduzir
   falha ALÉM dessa dívida declarada, não "85 verdes".
3. **Lint/format:** `ruff check` e `ruff format --check` conforme
   `[[browser-mcp-controle-de-mudancas]]` (atenção à dívida de lint pré-existente
   documentada lá — não introduza NOVOS erros).
4. **Gate de mudança:** classifique como "agent change" e siga
   `[[browser-mcp-controle-de-mudancas]]`. Registre baseline e pós-mudança no PR.

**Nada contorna o controle de mudanças.** Uma melhora "óbvia" sem os 3 runs e sem os
testes verdes NÃO é promovida.

---

## Menu de soluções ranqueado

Ordenado por (retorno provável ÷ custo), com pré-requisito de análise. Nenhum item
é adotável sem baseline (Fase 0).

| # | Solução | Custo | Risco | Pré-requisito de análise (OBRIGATÓRIO) |
|---|---|---|---|---|
| 1 | Retry/backoff em `LLMClient.chat` (Fase 2) | Baixo | Baixo | Baseline mostra `llm_error` > 0, ou incidentes de rede intermitentes |
| 2 | Validação de schema / `json_object` em `_parse_response` (Fase 1) | Baixo | Baixo | `total_parse_incidents` alto na baseline |
| 3 | Rede recente na observação (Fase 3.1) | Médio | Médio | Falhas concentradas em cascata AJAX (`cascade_*`) |
| 4 | `fallback_llm` (Fase 2) | Alto (2ª chave) | Médio | `llm_error` recorrente atribuível a UM provedor |
| 5 | Screenshots/vision na observação (Fase 3.2) | Alto (tokens/latência) | Alto | Evidência de que o agente erra por não "ver" (justificar na baseline) |
| — | Aumentar `max_iterations` | — | — | **CERCADO** — mascara loop |
| — | JS-click | — | — | **CERCADO** — isTrusted=false |
| — | Prompt-tweak sem benchmark | — | — | **CERCADO** — irreproduzível |

---

## O harness — decisão de manutenção (2026-07-13)

`scripts/benchmark_agent.py` foi deixado por uma tentativa anterior interrompida.

**Decisão: MANTER, com uma pequena melhoria de robustez.** Justificativa verificada:

- **Compila:** `python -m py_compile` passa.
- **`--list` roda sem LLM/browser** (imports adiados dentro de `run_benchmark`,
  `benchmark_agent.py:229`) e lista as 8 tarefas.
- **Categorização casa com o código real:** `categorize` (`~:178`) usa exatamente as
  strings de `_build_final_result`/`execute_task` — "consecutive parse errors"
  (`agent.py:174`), "consecutive errors" (`:159`), "max iterations" (`:219`).
- **Métricas corretas:** taxa de sucesso, `mean_iterations` (de `action_count`,
  `agent.py:588`) e `total_parse_incidents` (insumo da Fase 1) — cobrem o que a
  campanha exige.
- **Fixtures batem com os `check`:** os valores esperados existem no HTML —
  `FX-7731-KappaBravo` e `87.310` (extract_fact.html), `LOGIN_OK` (form_login.html),
  `22,90` (search_list.html), `MATRICULA_OK` (cascade_ajax.html). Todas as
  `?delay=` da cascata são reais.
- **Só usa API existente de `BrowserManager`:** `start`/`stop`/`navigate`/
  `get_content`/`get_pending_network_count` (verificados em `browser_manager.py`).
- **Instancia `LLMClient()` diretamente** — mesmo caminho de `browser_agent_task`
  (`tools.py:16`), evitando o defeito do singleton duplicado.

**Melhoria aplicada:** adicionada a flag `--offline` (omite `example_com`, a única
tarefa com rede real) para permitir uma linha de base 100% local e determinística.
Nenhuma outra alteração no comportamento.

---

## Proveniência e manutenção

- **Fatos do repo verificados em 2026-07-13 e RE-VERIFICADOS em 2026-07-17**
  (leitura direta de `agent.py`, `llm_client.py`, `tools.py`, `tests/test_agent.py`,
  `browser_manager.py` e do próprio harness). Números voláteis a re-checar quando o
  código mudar:
  - `agent.py` = 596 linhas; `_parse_response` em `:355`; `_build_final_result` em
    `:580`; default `max_iterations=30` em `:87`.
  - `browser_agent_task` passa `max_iterations=50` (`tools.py:1050` schema, `:1074`
    assinatura) — divergência com o default do agente (documentar, não silenciar).
  - `llm_client.py` = 101 linhas, SEM retry/backoff (só `raise_for_status` em `:65`,`:95`).
  - `LLMClient` duplicado: `llm_client.py:101` (usado por `server.py:71`) vs
    `tools.py:16` (usado pelas tools).
  - 85 testes coletados; SOTA externo browser-use 87.4%/200 tarefas.
- **Como re-verificar rápido:** `grep -n "max_iterations" src/browser_mcp/agent.py
  src/browser_mcp/tools.py`; `grep -n "retry\|backoff" src/browser_mcp/llm_client.py`;
  `.venv/bin/python -m pytest tests/ --collect-only -q | tail -1`.
- **Skills irmãs citadas:** `[[browser-mcp-controle-de-mudancas]]` (gate),
  `[[browser-mcp-contrato-de-arquitetura]]` (singleton duplicado),
  `[[browser-mcp-metodologia-e-prova]]` (preveja números antes),
  `[[browser-mcp-playbook-de-depuracao]]` (triagem pontual),
  `[[browser-mcp-arqueologia-de-falhas]]` (isTrusted, i-Educar),
  `[[browser-automacao-referencia]]` (teoria isTrusted/a11y),
  `[[browser-mcp-config-e-flags]]` (LLM_*), `[[browser-mcp-build-e-ambiente]]` (venv),
  `[[browser-mcp-fronteira-e-posicionamento]]` (SOTA/claims).
