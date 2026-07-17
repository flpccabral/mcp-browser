---
name: browser-mcp-metodologia-e-prova
description: >-
  Kit de metodologia e prova do repo do browser MCP server: como provar uma
  alegação antes de entregá-la ("como provar", "evidência", "experimento",
  "hipótese", "é seguro afirmar", "metodologia"). Barra de evidência (um
  mecanismo deve explicar TODAS as observações e sobreviver a uma refutação
  designada; prever números ANTES de rodar), ciclo de vida da ideia (candidata
  -> flag -> medição -> adoção ou aposentadoria documentada) e seis receitas de
  prova com exemplos resolvidos da história deste repo: experimento
  discriminatório (regra do click com isTrusted), teste adversarial
  (test_restricted_profile.py, domínios look-alike), medição de linha de base,
  observação de rede (mapeamento i-Educar /module/DynamicInput/*), verificação
  de alegação documental (README "37 tools" vs contagem real via grep ancorado)
  e refutação designada. Use ao decidir se a evidência é suficiente, ao desenhar
  um experimento, ou ao revisar uma alegação como "melhorou" ou "é seguro".
---

# Metodologia e Prova — como transformar intuição em resultado aceito NESTE repo

Esta skill define a barra de evidência do projeto e fornece seis receitas de
prova, cada uma com um exemplo resolvido extraído da história real deste
repositório. A regra da casa em uma frase: **prove, não apenas instale.**

Público: engenheiro sem contexto prévio. Todos os comandos de verificação
rodam a partir da raiz do repo. Comandos `git show` referem-se ao commit
histórico `cbc8e28` ("feat: 4 P0 fixes", 2026-07-10), que contém os relatórios
de investigação removidos do working tree atual.

## Quando NÃO usar esta skill

- **Triagem rápida de um bug em produção** — use `browser-mcp-playbook-de-depuracao`
  (esta skill é o rigor por trás da triagem, não a triagem em si).
- **Passar pelo gate formal de merge** (testes obrigatórios, lint, README) —
  use `browser-mcp-controle-de-mudancas`.
- **Escolher o instrumento de medição** (network log, HAR, screenshot,
  accessibility tree) — use `browser-mcp-diagnosticos-e-ferramentas`.
- **Consultar uma ideia já aposentada** — o registro vive em
  `browser-mcp-arqueologia-de-falhas`.
- **Rodar a suíte de testes formal / evidência de QA** — use
  `browser-mcp-validacao-e-qa`.

---

# Parte A — Barra de evidência

## A.1 Um mecanismo deve explicar TODAS as observações

Um mecanismo proposto só é aceito se explicar **todas** as observações,
inclusive as negativas (o que NÃO aconteceu), e sobreviver a uma refutação
adversarial designada (receita B.6).

Regras práticas:

1. Liste as observações numeradas ANTES de propor o mecanismo — positivas e
   negativas ("o click falha em X" E "o click funciona em Y").
2. Para cada observação, escreva como o mecanismo a explica. Uma observação
   sem explicação = mecanismo incompleto ou errado.
3. Um mecanismo que explica só as observações convenientes é uma
   racionalização, não uma explicação.

Exemplo do padrão neste repo: os testes do perfil restrito verificam tanto o
comportamento positivo (bloqueia em modo restrito) quanto o negativo (NÃO
bloqueia em modo padrão — `tests/test_restricted_profile.py:409-440`,
classe `TestDefaultMode`). Um mecanismo de validação que só fosse testado no
caminho de bloqueio poderia estar bloqueando tudo, sempre.

## A.2 Hipótese → prever números ANTES de rodar → rodar → comparar

Sem previsão prévia registrada, qualquer número obtido depois é
pós-racionalização. Formato obrigatório:

| Campo | Conteúdo |
|---|---|
| Hipótese | Enunciado falseável ("X causa Y via mecanismo Z") |
| Previsão | Número ou resultado concreto ANTES de rodar ("espero 43/43 pass"; "espero isTrusted=false no evento sintético") |
| Comando | O comando exato que produz o número |
| Resultado | O número obtido |
| Veredito | Previsão confirmada / refutada / parcial |

Precedente da casa: o commit `cbc8e28` fecha com medição explícita —
"Verified: 43/43 pytest passing. Tested: Perplexity, GitHub, example.com"
(verifique: `git show cbc8e28 --no-patch`). Toda mudança relevante deve
fechar assim: com o número, não com "funcionou".

## A.3 Ciclo de vida da ideia — nada morre em silêncio

```
candidata → flag/experimento isolado → medição → adoção documentada
                                            └──→ aposentadoria documentada
```

| Estágio | O que exige | Onde registrar |
|---|---|---|
| Candidata | Enunciado + observações que motivam | Issue/nota da campanha |
| Flag/experimento isolado | Atrás de flag ou env var (ver `browser-mcp-config-e-flags`); nunca no caminho padrão | Código + doc da flag |
| Medição | Previsão prévia (A.2) + comando reproduzível | Relatório datado |
| Adoção | Doc com comando de verificação (receita B.5) + gate de `browser-mcp-controle-de-mudancas` | README / docs |
| Aposentadoria | Motivo + evidência que a matou | `browser-mcp-arqueologia-de-falhas` |

**Regra dura:** ideia rejeitada sem registro é ideia que alguém vai propor de
novo daqui a três meses. Registre a aposentadoria com a mesma disciplina da
adoção.

Precedente de isolamento por flag neste repo: o perfil restrito inteiro é
opt-in via `IFOOD_RESTRICTED_MODE` — desligado por padrão, com testes que
provam os dois estados (`tests/test_restricted_profile.py:409-440`).

## A.4 De onde boas ideias vieram historicamente AQUI

Três fontes comprovadas, cada uma com o documento histórico verificável:

| Fonte de ideia | Caso real | Resultado no produto | Verifique com |
|---|---|---|---|
| **Benchmarking de concorrente** | Estudo do Kimi WebBridge: accessibility tree com refs `@e`, sessão do browser REAL do usuário, network monitoring nativo | Refs `@e` no agente (regra 1 do system prompt, `src/browser_mcp/agent.py:30`), modo extensão/browser do usuário | `git show cbc8e28:aprendizado_webbridge.md` |
| **Investigação estruturada multi-vetor** | Indicadores visuais (2026-07-01): três vetores — pesquisa web + análise prática com WebBridge + análise de arquiteturas — cobrindo cinco agentes/distribuições (Kimi WebBridge, Claude Desktop, Gemini CLI, cdpilot, OpenClaw, Browser-Use) | Decisão fundamentada com tabela comparativa: CDP `Runtime.evaluate` + CSS injection (não requer extensão, qualquer Chromium, `pointer-events: none`) | `git show cbc8e28:investigacao_indicadores_visuais.md` |
| **Investigação empírica de site real** | i-Educar: login, navegação, preenchimento de filtros em cascata com observação de rede | Mapa completo dos endpoints `/module/DynamicInput/*` (receita B.4); recomendações de robustez (navegação direta por URL, interceptors HTTP) | `git show cbc8e28:relatorio_ieducar.md` |

Padrão comum às três: nenhuma partiu de opinião. Todas produziram um
**documento com evidência** antes de qualquer código.

---

# Parte B — Receitas de prova

Cada receita: quando usar / passos / exemplo resolvido deste repo.

## B.1 Prova por experimento discriminatório

**Quando usar:** duas hipóteses (A e B) explicam a mesma observação e você
precisa decidir qual é verdadeira.

**Passos:**

1. Enuncie A e B de forma que façam previsões DIFERENTES para algum teste.
2. Desenhe o teste mínimo em que A e B divergem — variando UMA coisa só,
   mantendo todo o resto idêntico (mesmo elemento, mesma página, mesma sessão).
3. Escreva as duas previsões antes de rodar (A.2).
4. Rode. O resultado elimina uma hipótese.
5. Confirme que a hipótese sobrevivente explica também as observações
   antigas (A.1).

**Exemplo resolvido — "por que o click falha?":**

- Observação: cliques via JavaScript falham em Google News e várias SPAs;
  em outros sites funcionam.
- Hipótese A: o elemento não existe / seletor errado.
- Hipótese B: o elemento existe, mas o evento é sintético e o site o rejeita.
- Experimento discriminatório: no MESMO elemento da MESMA página, comparar
  `browser_click` (evento real via CDP) com
  `browser_execute_javascript` + `element.click()`/`dispatchEvent` (evento
  sintético). Se A fosse verdadeira, AMBOS falhariam (elemento inexistente
  falha para os dois). Se B fosse verdadeira, só o sintético falharia.
- Resultado: `browser_click` passa, o dispatch via JS falha. Mecanismo (em
  1 frase): eventos sintéticos carregam `isTrusted=false` e sites como Google
  News os bloqueiam. B explica tudo, inclusive a observação negativa (por que
  funciona em sites que não checam `isTrusted`). Teoria completa do `isTrusted`:
  [[browser-automacao-referencia]] §3 — aqui interessa só o exemplo de
  experimento discriminatório resolvido.
- Regra resultante, codificada no system prompt do agente:
  - `src/browser_mcp/agent.py:38` (regra 9): "NEVER use
    browser_execute_javascript to click links or navigate. JS click events
    (element.click()) have isTrusted=false and are blocked by Google News
    and many SPAs."
  - `src/browser_mcp/agent.py:64` (descrição da ferramenta):
    `browser_execute_javascript ... for DATA EXTRACTION only. ⚠️ NEVER use
    for clicking/navigation — events have isTrusted=false.`

## B.2 Prova por teste adversarial

**Quando usar:** alegações de segurança. "É seguro" não se prova mostrando o
caminho feliz — prova-se **pelo ataque que falha**, escrito como teste
nomeado e permanente.

**Passos:**

1. Enumere os vetores de ataque como um adversário faria (typosquatting,
   downgrade de esquema, escopo lateral, URLs privilegiadas, inputs vazios).
2. Escreva um teste por vetor, com o payload malicioso literal no teste.
3. O teste passa quando o ataque FALHA (assert `is False` / rejeição).
4. Cubra também o caminho legítimo, para provar que a defesa não bloqueia
   tudo (senão o teste adversarial é trivialmente satisfeito).

**Exemplo resolvido REAL — `tests/test_restricted_profile.py`:**

| Vetor de ataque | Payload literal | Teste (linha) |
|---|---|---|
| Look-alike / typosquatting | `https://portal.ifood.com.br.hacker.net` e `https://partners-auth.ifood.com.br.evil.com` | `test_similar_domain_rejected`, linhas 61-65 |
| Subdomínio não autorizado (match exato apenas) | `https://api.portal.ifood.com.br`, `https://staging.developer.ifood.com.br` | `test_unauthorized_subdomain_rejected`, linhas 67-72 |
| Downgrade para HTTP | `http://portal.ifood.com.br/` mesmo sendo host permitido | `test_http_rejected`, linhas 51-54 |
| URL privilegiada do browser | `chrome://settings`, `chrome://version` | `test_chrome_url_rejected`, linhas 56-59 |
| Domínio totalmente estranho | `https://google.com`, `https://evil.com` | `test_unauthorized_domain_rejected`, linhas 74-78 |
| Host removido da allowlist | `https://gestordepedidos.ifood.com.br/` (permitido até 2026-07-17, depois removido do escopo) | `test_removed_host_rejected`, linhas 80-83 |
| URL malformada / vazia | `not-a-url`, `""` | `test_malformed_url_rejected`, linhas 78-81 |
| Script JS não registrado (hash) | qualquer código fora de `ALLOWED_SCRIPT_HASHES`; allowlist vazia rejeita TUDO (secure-by-default) | `test_script_rejected_when_allowlist_empty`, linhas 141-145 |
| Token com permissões inseguras | arquivo `0644` (world-readable) | `test_insecure_permissions`, linhas 290-306 |

E o caminho legítimo, provando que a defesa não é um bloqueio cego:
`test_allowed_https_domain` (linhas 46-49) e
`test_navigate_allowed_domain_passes` (linhas 207-214).

## B.3 Prova por medição de linha de base

**Quando usar:** qualquer alegação de melhoria ("ficou mais confiável",
"melhorou o agente", "reduziu falhas"). Nunca aceite "melhorou" sem o número
ANTERIOR.

**Passos:**

1. Antes de mudar qualquer coisa, meça o estado atual com um protocolo
   reproduzível (tarefa fixa, N runs, critério de sucesso binário escrito).
2. Registre: comando, data, número (ex.: "12/20 runs completam a tarefa X").
3. Aplique a mudança isolada (uma variável por vez).
4. Repita a MESMA medição. Compare.
5. Para sistemas não-determinísticos (o agente LLM), N ≥ 3 runs por
   condição — ver anti-padrão C.3.

**Contra-exemplo honesto do repo (verificado em 2026-07-13):** hoje NÃO
existe linha de base do agente. Não há benchmark de taxa de sucesso do
`BrowserAgent` no repositório — `tests/` contém apenas testes unitários
(`test_agent.py`, `test_tools.py`, `test_smoke.py`,
`test_restricted_profile.py`), nenhum mede sucesso de tarefa fim-a-fim.
Consequência prática: **qualquer** alegação atual de "o agente melhorou" é
inverificável por construção. Essa lacuna é exatamente o que a campanha de
confiabilidade ataca — ver
`browser-mcp-campanha-confiabilidade-do-agente`. Enquanto a linha de base
não existir, trate afirmações de melhoria do agente como não provadas.

## B.4 Prova por observação de rede

**Quando usar:** o comportamento do site alvo é a incógnita (que endpoint é
chamado? com quais parâmetros? o que retorna?). Meça o tráfego em vez de
supor a partir do HTML.

**Passos:**

1. Ative a captura de rede antes da interação
   (`browser_get_network_log` / export HAR — instrumentos em
   `browser-mcp-diagnosticos-e-ferramentas`).
2. Execute UMA interação por vez (um filtro, um clique) e associe cada
   interação às requisições que ela disparou.
3. Monte a tabela endpoint → método → parâmetros → formato de resposta.
4. Valide o mapa reproduzindo uma chamada fora da UI (ou prevendo a próxima
   chamada antes de interagir — A.2).

**Exemplo resolvido — mapeamento do i-Educar
(`git show cbc8e28:relatorio_ieducar.md`, seção 3):**

Preenchendo os filtros em cascata do Diário de Classe com monitoramento de
rede ativo, o agente mapeou o padrão completo `/module/DynamicInput/*`:

| Etapa do filtro | Endpoint | Parâmetros principais |
|---|---|---|
| Curso | `GET /module/DynamicInput/Curso` | `resource=cursos`, `escola_id` |
| Série | `GET /module/DynamicInput/serie` | `resource=series`, `curso_id`, `escola_id` |
| Turma | `GET /module/DynamicInput/turma` | `resource=turmas`, `serie_id`, `curso_id` |
| Etapa | `GET /module/DynamicInput/Etapa` | `resource=etapas`, `turma_id`, `curso_id` |
| Componente Curricular | `GET /module/DynamicInput/componenteCurricular` | `resource=componentesCurricularesForDiario`, `etapa`, `turma_id` |
| Diário (alunos) | `GET /module/Avaliacao/diarioApi` | `resource=matriculas`, `componente_curricular_id`, `turma_id`, `etapa` |

Nenhuma dessas rotas está documentada publicamente — o mapa saiu inteiro da
observação de tráfego. O relatório também registrou a observação negativa
(A.1): combinações de filtros da base demo retornavam `matriculas: []`,
o que explicou por que a tabela de edição não aparecia — sem essa observação,
a conclusão errada seria "o click no botão Carregar falhou".

## B.5 Prova de alegação documental

**Quando usar:** sempre que escrever uma afirmação factual em doc (contagem,
comportamento, default). Estilo da casa: toda afirmação vem com comando de
verificação ou citação `file:line` (é o padrão do README — veja
`README.md:8`, `README.md:44`).

**Passos:**

1. Para cada afirmação factual, escreva o comando que a verifica.
2. Rode o comando ANTES de publicar. Cole o resultado.
3. Date afirmações voláteis (contagens, versões, estado de CI).
4. Em revisão de doc antigo, re-rode os comandos — afirmações não
   re-verificadas envelhecem mal.

**Exemplo resolvido às avessas (verificado em 2026-07-17):**

- Alegação: `README.md:4` e `README.md:8` afirmam "37 ferramentas MCP";
  `README.md:116` reforça "A contagem verificada é 37".
- Comando de verificação **ancorado**: `grep -c '^@app.tool' src/browser_mcp/tools.py`
- Resultado hoje: **39**. (Divergência aberta: 37 no README vs 39 real —
  a RELATAR, não corrigir aqui.)
- **A armadilha do grep ingênuo (parte da lição desta receita):** um
  `grep -c '@app.tool'` SEM a âncora `^` retorna **41** — 2 a mais, porque
  duas ocorrências de `@app.tool` aparecem em docstrings, não como decorador
  real. Contagem correta exige ancorar no início de linha (`^`). Medir mal é
  tão perigoso quanto não medir: o número 41 é factualmente falso.
- Diagnóstico: a alegação "37" era verdadeira quando escrita (o README foi
  auditado no commit `bb2fd1c`, "docs: rewrite README based on code audit"),
  mas o commit `efa0df5` adicionou `browser_scroll` + `browser_download`
  sem re-rodar a verificação do README. A alegação envelheceu mal — e a
  ironia é que o próprio README continha o antídoto: o comando de
  verificação estava lá, só não foi re-executado (e, se re-executado sem
  âncora, daria o número errado de novo).
- Lição: comando de verificação no doc só protege se for (a) re-rodado a cada
  mudança que pode invalidá-lo e (b) correto — âncora `^` inclusa. Amarre isso
  ao gate de [[browser-mcp-controle-de-mudancas]] (atualização de README é
  obrigatória quando ferramentas mudam).

## B.6 Refutação designada

**Quando usar:** antes de promover qualquer mudança grande (arquitetura,
segurança, mudança de default, conclusão de investigação). Alguém — pessoa
ou subagente — recebe explicitamente a tarefa de DERRUBAR a alegação.

**Passos:**

1. O autor empacota: (a) a alegação exata, (b) todos os dados/evidências,
   (c) os comandos para reproduzir.
2. Formato do encargo ao refutador designado, literalmente:
   **"aqui está a alegação, aqui estão os dados, encontre o furo."**
   O refutador NÃO é convidado a concordar — o sucesso dele é achar o furo.
3. O refutador ataca: observações não explicadas (A.1), hipóteses
   alternativas não eliminadas (B.1), vetores adversariais não testados
   (B.2), números sem previsão prévia (A.2).
4. Resultado registrado por escrito: "não encontrei furo em X, Y, Z" (com o
   que foi tentado) OU a lista de furos. Refutação silenciosa não conta.
5. Só depois disso a mudança segue para o gate formal de
   `browser-mcp-controle-de-mudancas`.

Precedente da casa: o commit `cbc8e28` nasceu de um code review adversarial
externo — "Code review by Claude Fable 5, implemented via Codex GPT-5.5"
(`git show cbc8e28 --no-patch`) — que derrubou quatro alegações implícitas
do código ("o WebSocket é seguro sem auth", "eval funciona em qualquer
página", "navigate reusa a aba", "futures são limpos"), todas P0. Um par
autor/refutador com modelos diferentes é uma forma barata de refutação
designada.

---

# Parte C — Anti-padrões cercados

| # | Anti-padrão | Por que é proibido | O que fazer em vez disso |
|---|---|---|---|
| C.1 | **Prompt-tweaking sem benchmark** — editar `AGENT_SYSTEM_PROMPT` (`src/browser_mcp/agent.py:15`) porque "parece que ajuda" | O agente é não-determinístico; sem número antes/depois, o efeito do tweak é indistinguível de ruído. Hoje nem linha de base existe (B.3) | Linha de base primeiro (B.3), depois o tweak como experimento isolado com previsão prévia (A.2) |
| C.2 | **"Funcionou na minha máquina" sem teste nomeado** | Evidência anedótica não reproduzível não entra no gate. O precedente da casa é fechar com número: "43/43 pytest passing" (`git show cbc8e28 --no-patch`) | Converta a evidência em teste nomeado em `tests/` (como cada vetor de ataque virou um teste em B.2) ou em comando de verificação documentado (B.5) |
| C.3 | **Conclusão a partir de 1 run de agente não-determinístico** | Um run de LLM prova apenas que o resultado é POSSÍVEL, não provável. Sucesso e falha isolados são igualmente inconclusivos | **Exigir 3 runs no mínimo** por condição, com critério de sucesso binário escrito antes do primeiro run. Reporte "N/3", nunca "funcionou" |
| C.4 | **Copiar solução do browser-use (ou de qualquer concorrente) sem verificar que o mecanismo se aplica ao NOSSO substrato** | Substratos diferem: browser-use dirige Playwright/CDP direto; nosso modo extensão passa por service worker MV3 + WebSocket, com restrições próprias (CSP, `isTrusted`, permissões de manifest). Uma solução pode depender de capacidade que nosso caminho não tem | Benchmarking correto extrai o MECANISMO e re-deriva a implementação para o nosso substrato — é exatamente o que `aprendizado_webbridge.md` fez com refs `@e` (A.4): entendeu POR QUE accessibility refs são mais estáveis que CSS, e só então propôs implementação própria. Note que a própria investigação de indicadores visuais constatou que o browser-use NÃO tinha indicador nativo (`git show cbc8e28:investigacao_indicadores_visuais.md`, seção 3.6) — copiar dele seria copiar uma lacuna |

---

# Skills irmãs

| Skill | Relação com esta |
|---|---|
| `browser-mcp-playbook-de-depuracao` | Triagem rápida; esta skill é o rigor por trás quando a triagem vira investigação |
| `browser-mcp-controle-de-mudancas` | O gate formal que a evidência daqui alimenta; nada adota sem passar por lá |
| `browser-mcp-arqueologia-de-falhas` | Onde ideias aposentadas (A.3) são registradas — nada morre em silêncio |
| `browser-mcp-diagnosticos-e-ferramentas` | Os instrumentos de medição usados pelas receitas (network log, HAR, screenshots) |
| `browser-mcp-validacao-e-qa` | Evidência de teste formal; as receitas B.2/B.3 produzem testes que vivem lá |
| `browser-mcp-campanha-confiabilidade-do-agente` | Aplicação desta metodologia ao problema #1 (a lacuna de linha de base de B.3) |
| `browser-mcp-contrato-de-arquitetura` | Invariantes que hipóteses e mecanismos não podem violar |
| `browser-mcp-config-e-flags` | Como isolar experimentos atrás de flags (estágio 2 do ciclo A.3) |
| `browser-mcp-build-e-ambiente` / `browser-mcp-executar-e-operar` | Reproduzir o ambiente onde as medições rodam |
| `browser-mcp-perfil-restrito` | O objeto do exemplo B.2 (allowlists, modo iFood) |
| `browser-automacao-referencia` | Referência das ferramentas citadas nos exemplos |
| `browser-mcp-fronteira-e-posicionamento` | Contexto competitivo por trás do benchmarking (A.4, C.4) |

---

# Proveniência e manutenção

**Fontes primárias verificadas (re-verificado em 2026-07-17):**

- `tests/test_restricted_profile.py` — lido integralmente; linhas citadas em
  B.2 conferidas no working tree.
- `src/browser_mcp/agent.py` — regra `isTrusted` na linha 38 (regra 9 do
  system prompt) e na linha 64 (descrição de `browser_execute_javascript`).
- `git show cbc8e28:aprendizado_webbridge.md` — benchmarking WebBridge
  (refs `@e`, sessão real do usuário, network nativo).
- `git show cbc8e28:investigacao_indicadores_visuais.md` — investigação
  multi-vetor de 2026-07-01, decisão CDP + CSS injection.
- `git show cbc8e28:relatorio_ieducar.md` — tabela de endpoints
  `/module/DynamicInput/*`.
- `git show cbc8e28 --no-patch` — mensagem do commit ("43/43 pytest
  passing"; "Code review by Claude Fable 5").
- `grep -c '^@app.tool' src/browser_mcp/tools.py` → **39** em 2026-07-17,
  contra "37" em `README.md:4/8/116/211`. (Sem a âncora `^`, o grep dá 41 por
  contar 2 docstrings — armadilha documentada em B.5.)

**Fatos voláteis (re-verificar antes de citar):**

- Contagem de ferramentas (39 via grep ancorado em 2026-07-17; 41 sem âncora)
  e a divergência com o README — qualquer um dos dois pode ter mudado.
- Ausência de linha de base do agente (B.3) — a campanha de confiabilidade
  deve eliminá-la; quando existir, atualize B.3 com o exemplo positivo.
- Números de linha de `agent.py` e `test_restricted_profile.py`.

**Manutenção:** ao adotar ou aposentar uma ideia (A.3), esta skill não é o
registro — o registro é `browser-mcp-arqueologia-de-falhas` (aposentadorias)
e os docs do repo (adoções). Atualize esta skill apenas quando a barra de
evidência ou as receitas mudarem, ou quando um exemplo resolvido melhor
aparecer na história do repo.
