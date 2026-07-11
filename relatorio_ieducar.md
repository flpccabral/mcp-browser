# Relatório de Investigação i-Educar - Diário de Classe

## 1. Sumário executivo
A investigação do sistema i-Educar foi concluída com sucesso. O objetivo de navegar no sistema, realizar login, acessar o módulo de Lançamento de Faltas e Notas (Diário de Classe), preencher os filtros e analisar o tráfego de rede (AJAX) foi atingido. Foi possível mapear a comunicação dinâmica do frontend com o backend ao preencher os formulários em cascata.

## 2. Fluxo de navegação
O fluxo realizado pelo agente de automação de browser foi:
1. **Login**: Acesso à página inicial (`https://comunidade.ieducar.com.br/login`), preenchimento das credenciais de demonstração (`comunidade` / `Comunidade@1`) e acesso à plataforma.
2. **Navegação**: Navegação para a URL direta do módulo do diário (`https://comunidade.ieducar.com.br/module/Avaliacao/diario`).
3. **Preenchimento Dinâmico**: Interação com os filtros sequenciais (Escola, Curso, Série, Turma, Etapa e Componente Curricular), acionando chamadas de rede dinâmicas em cada etapa.
4. **Busca e Carregamento**: Acionamento do botão "Carregar" para buscar as matrículas (alunos).

## 3. Mapeamento de endpoints AJAX

| Etapa do Filtro | Método | Endpoint Chamado | Parâmetros Principais |
| --- | --- | --- | --- |
| **Curso** | GET | `/module/DynamicInput/Curso` | `resource=cursos`, `escola_id` |
| **Série** | GET | `/module/DynamicInput/serie` | `resource=series`, `curso_id`, `escola_id` |
| **Turma** | GET | `/module/DynamicInput/turma` | `resource=turmas`, `serie_id`, `curso_id` |
| **Etapa** | GET | `/module/DynamicInput/Etapa` | `resource=etapas`, `turma_id`, `curso_id` |
| **Componente Curricular** | GET | `/module/DynamicInput/componenteCurricular` | `resource=componentesCurricularesForDiario`, `etapa`, `turma_id` |
| **Diário (Alunos)** | GET | `/module/Avaliacao/diarioApi` | `resource=matriculas`, `componente_curricular_id`, `turma_id`, `etapa` |

## 4. Formato das requisições

Todas as chamadas para populamento dos *dropdowns* dinâmicos seguem um padrão de requisição GET com parâmetros de *query* semelhantes e retornam um JSON padronizado.

### Exemplo: Chamada para carregar Cursos
**URL:** `/module/DynamicInput/Curso?resource=cursos&oper=get&instituicao_id=1&escola_id=481777&ano_escolar=2026&ano=2026`
**Método:** GET
**Response (JSON):**
```json
{
  "options": {
    "__36": "Ensino Fundamental II (6º ao 9º ANO)"
  },
  "oper": "get",
  "resource": "cursos",
  "msgs": [],
  "any_error_msg": false
}
```

### Exemplo: Chamada para carregar Componentes Curriculares
**URL:** `/module/DynamicInput/componenteCurricular?resource=componentesCurricularesForDiario&oper=get&instituicao_id=1&escola_id=481777&curso_id=36&serie_id=13&turma_id=1640&ano_escolar=2026&etapa=1&ano=2026`
**Método:** GET
**Response (JSON):**
```json
{
  "options": {
    "__3": { "value": "LÍNGUA PORTUGUESA", "group": "ENSINO MÉDIO EJA - 1 ANO A 3°" },
    "__6": { "value": "MATEMÁTICA", "group": "ENSINO MÉDIO EJA - 1 ANO A 3°" }
  },
  "oper": "get",
  "resource": "componentesCurricularesForDiario",
  "msgs": [],
  "any_error_msg": false
}
```

### Exemplo: Chamada da Busca do Diário
**URL:** `/module/Avaliacao/diarioApi?resource=matriculas&oper=get&instituicao_id=1&escola_id=481777&curso_id=36&turma_id=1640&ano_escolar=2026&componente_curricular_id=3&etapa=1&busca=S...`
**Método:** GET
**Response (JSON - Exemplo sem alunos):**
```json
{
  "matricula_id": "",
  "matriculas": [],
  "navegacao_tab": "1",
  "can_change": true,
  "locked": false,
  "oper": "get",
  "resource": "matriculas",
  "msgs": [],
  "any_error_msg": false
}
```

## 5. Análise da arquitetura
O frontend do i-Educar se comunica com o backend utilizando chamadas AJAX baseadas no jQuery. As rotas responsáveis por preencher listas suspensas (dropdowns) em formulários parecem estar agrupadas sob o controlador `/module/DynamicInput/*`. Ele identifica qual recurso devolver (Cursos, Séries, Turmas) a partir da rota e/ou do parâmetro *query* `resource`.

Ao alterar o valor em um campo, o sistema dispara um evento *change* na UI, o que desencadeia a requisição para preencher o próximo campo dependente. Este mecanismo utiliza o padrão de retornar o estado (chaves e valores de HTML select options) na propriedade `options` do JSON de resposta. 

O módulo de diário de classe `/module/Avaliacao/diarioApi` é responsável por consolidar todos os parâmetros do filtro de uma só vez para recuperar as matrículas.

## 6. Screenshots
- **Após o login**: `![Login Screenshot](/Users/felipecc/.gemini/antigravity-ide/brain/041ee31b-899d-4816-af19-e11257f667a7/after_login_1782922633834.png)`
- **Página de Filtro do Diário**: `![Filtro Screenshot](/Users/felipecc/.gemini/antigravity-ide/brain/041ee31b-899d-4816-af19-e11257f667a7/diario_page_1782922658025.png)`
- **Diário Carregado (Filtros Preenchidos)**: `![Diário Screenshot](/Users/felipecc/.gemini/antigravity-ide/brain/041ee31b-899d-4816-af19-e11257f667a7/diario_loaded_1782922992522.png)`

## 7. Dificuldades encontradas
- A navegação pelo menu retrátil "Escola > Lançamentos > Faltas e notas" exigiria manipulação complexa do DOM via eventos de *hover* e *click* assíncronos. Optou-se por acessar a URL diretamente após o login: `/module/Avaliacao/diario`.
- Os filtros dinâmicos de turmas de demonstração nem sempre contêm dados consistentes. Em várias tentativas de combinação (ex: Escola 481777, Turma 1640 ou 1644), a requisição AJAX que busca alunos (matrículas) não retornava resultados (`matriculas: []`), impossibilitando a exibição da tabela de edição e, logo, da interação de alteração de faltas/notas.

## 8. Comportamento do Agente de Automação de Browser

O subagente de automação de browser (Browser Subagent) atua como um navegador autônomo com inteligência artificial, sendo capaz de interagir visualmente com a interface do usuário (DOM) da mesma forma que um humano faria. Aqui estão as principais características do seu comportamento durante esta investigação:

- **Compreensão Visual e Estrutural (DOM)**: O agente não depende apenas de seletores CSS estritos. Ele analisa o HTML (DOM) e interpreta a página "visualmente". Isso permite que ele "localize o campo Matrícula" ou "clique no botão Entrar (verde)" utilizando processamento de linguagem natural associado à estrutura da página, tornando as interações muito mais resilientes a mudanças no layout do que scripts tradicionais (como Selenium puro ou Cypress).
- **Espera Implícita e Tráfego de Rede**: Ao interagir com filtros dinâmicos, o agente monitora ativamente o tráfego de rede (Network) do navegador. Quando ele preenche o filtro "Instituição", ele pode perceber que uma chamada AJAX (`/module/DynamicInput/Curso`) foi despachada e analisar seu retorno (JSON). Essa capacidade de observar requisições de background enriquece muito as documentações de engenharia reversa.
- **Controle Total de Sessão**: O agente mantém cookies e sessões de forma persistente durante a sua execução. Ele executou o login, recebeu a resposta de sucesso e usou os cookies de sessão autenticada para acessar o módulo de diário (`/module/Avaliacao/diario`) na etapa seguinte, sem a necessidade de reautenticação a cada passo.
- **Resolução de Obstáculos (Heurística)**: Quando o agente percebeu a dificuldade em navegar pelos menus expansíveis em cascata (menus retráteis via hover) da barra lateral esquerda, ele imediatamente aplicou a instrução de "fallback" fornecida no prompt, preferindo navegar diretamente via URL (`/module/Avaliacao/diario`). Isso demonstra capacidade de tomada de decisão para contornar gargalos de UI e atingir o objetivo principal.

## 9. Recomendações
Para uma automação futura robusta desse fluxo, sugere-se:
1. **Navegação Direta**: Continuar preferindo o acesso via URL direta (`/module/Avaliacao/diario`) em vez de navegar pelos menus da barra lateral, para diminuir a fragilidade (flakiness) dos testes/scripts.
2. **Uso de Interceptors HTTP**: As requisições de preenchimento dinâmico usam chaves sequenciais e as listas de valores (IDs) frequentemente mudam. Uma automação precisa injetar scripts para interceptar as requisições AJAX (`XMLHttpRequest` e `fetch`) para descobrir automaticamente qual é o ID da Turma e da Etapa, em vez de manter IDs fixos (hardcoded) no script, já que no backend esses IDs (`turma_id`, `escola_id`) podem variar.
3. **Massa de Dados**: É fundamental garantir que a base de dados de demonstração possua alunos ativos vinculados a pelo menos uma turma. Sem isso, os cenários de interação final de lançar notas falharão por causa da matriz vazia.
