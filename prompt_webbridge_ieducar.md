# Prompt para Ferramenta de Browser Automation - Investigação i-Educar

## Instrução para o Agente de Browser

Você é um especialista em automação de browsers e engenharia reversa de aplicações web. Sua missão é investigar o sistema i-Educar e documentar TODO o processo de navegação, interação e tráfego de rede.

---

## 🎯 Objetivo da Tarefa

Navegar no site de demonstração do i-Educar, fazer login, acessar a tela de **Lançamentos > Faltas e notas**, preencher os filtros disponíveis e capturar o tráfego AJAX que popula os campos dinâmicos e carrega os dados do diário.

---

## 📋 Passo a Passo Obrigatório

### Etapa 1: Login
1. Navegue para `https://comunidade.ieducar.com.br/login`
2. Localize o campo **Matrícula** e digite: `comunidade`
3. Localize o campo **Senha** e digite: `Comunidade@1`
4. Clique no botão **Entrar** (verde)
5. Aguarde o carregamento completo da página principal
6. Tire um **screenshot** da tela após login
7. Documente a **URL** e o **título da página**

### Etapa 2: Navegação até "Faltas e notas"
1. No menu lateral esquerdo, clique em **Escola**
2. Aguarde o submenu expandir
3. Clique em **Lançamentos** (dentro do submenu Escola)
4. Aguarde o submenu de Lançamentos expandir
5. Clique em **Faltas e notas**
6. Aguarde a tela carregar completamente
7. Tire um **screenshot** da tela de "Lançamento de faltas e notas"
8. Documente a **URL** e o **título**

### Etapa 3: Preenchimento dos Filtros (IMPORTANTE para capturar AJAX)
1. Observe os campos de filtro disponíveis:
   - Ano (já deve vir preenchido)
   - Instituição (dropdown)
   - Escola (dropdown)
   - Curso (dropdown)
   - Série (dropdown)
   - Turma (dropdown)
   - Etapa (dropdown)
   - Componente Curricular (dropdown)
   - Matrícula (dropdown)
   - Navegação do cursor (dropdown)

2. Preencha os filtros SEQUENCIALMENTE (cada um dispara AJAX):
   - Selecione uma **Instituição** no dropdown
   - Aguarde o carregamento dos dados (observe o spinner/network)
   - Selecione uma **Escola** no dropdown
   - Aguarde o carregamento
   - Selecione um **Curso**
   - Aguarde
   - Selecione uma **Série**
   - Aguarde
   - Selecione uma **Turma**
   - Aguarde
   - Selecione uma **Etapa**
   - Aguarde
   - Se possível, selecione um **Componente Curricular**
   - Tire **screenshot** após cada seleção de filtro

3. Clique no botão **Buscar** (ou similar)
4. Aguarde o carregamento da lista de alunos
5. Tire um **screenshot** da tela com os dados carregados

### Etapa 4: Interação com o Diário (se possível)
1. Se a lista de alunos aparecer, clique em uma célula de nota/falta de um aluno
2. Observe se abre um modal ou campo inline para edição
3. Tire um **screenshot** dessa interação
4. Documente o comportamento

---

## 🔍 Captura de Tráfego de Rede

Durante TODO o processo, capture o tráfego de rede (HAR ou log de requests). Documente especificamente:

### Requisições AJAX que populam os dropdowns dinâmicos:
- Quando você seleciona "Instituição", que URL é chamada para buscar as "Escolas"?
- Quando seleciona "Escola", que URL busca os "Cursos"?
- Quando seleciona "Curso", que URL busca as "Séries"?
- Quando seleciona "Série", que URL busca as "Turmas"?
- Quando seleciona "Turma", que URL busca as "Etapas"?
- Quando seleciona "Etapa", que URL busca os "Componentes Curriculares"?

### Formato das requisições:
- **Método HTTP** (GET, POST, etc.)
- **URL completa** (incluindo query parameters)
- **Headers** (Content-Type, Accept, X-Requested-With, etc.)
- **Request Body** (para POSTs - parâmetros enviados)
- **Response** (JSON retornado com os dados)

### Endpoint do Diário:
- Quando clica em **Buscar**, qual URL retorna a lista de alunos?
- Quando edita uma nota/falta, qual URL salva a alteração?
- Qual o formato dos dados enviados (JSON, form-data, etc.)?

---

## 📝 Documentação Obrigatória

Para CADA passo, documente:
1. **Ação realizada** (ex: "Cliquei no dropdown 'Escola'")
2. **Elemento identificado** (seletor CSS, ID, ou texto visível)
3. **Resultado observado** (o que aconteceu na tela)
4. **Chamadas de rede** (URLs, métodos, status codes)
5. **Screenshot** (caminho do arquivo salvo)

---

## 📁 Artefatos a Gerar

Ao final, salve um arquivo de relatório em formato Markdown (`.md`) com:

1. **Sumário executivo** — o que foi alcançado
2. **Fluxo de navegação** — passo a passo com screenshots
3. **Mapeamento de endpoints AJAX** — tabela com todas as URLs descobertas
4. **Formato das requisições** — exemplos de request/response
5. **Análise da arquitetura** — como o frontend se comunica com o backend
6. **Screenshots** — referências a todas as imagens capturadas
7. **Dificuldades encontradas** — o que não funcionou ou foi desafiador
8. **Recomendações** — como automatizar esse fluxo no futuro

---

## ⚠️ Observações Importantes

- O i-Educar usa **menus expansíveis** no menu lateral — passe o mouse (hover) sobre "Escola" para ver o submenu
- Os dropdowns são populados **dinamicamente via AJAX** — aguarde o carregamento antes de selecionar o próximo
- O site usa **jQuery** e **Prototype.js** — os AJAX calls provavelmente usam `$.ajax` ou `new Ajax.Request`
- O endpoint de API pode ser algo como `/module/Api/diario` ou `/module/Avaliacao/diarioApi`
- Se encontrar um menu que não expande, tente **clicar diretamente** na URL: `https://comunidade.ieducar.com.br/module/Avaliacao/diario`
- Tire screenshots **frequentes** — é melhor ter muitas imagens do que perder evidências

---

## ✅ Critérios de Sucesso

O relatório será considerado completo quando:
- [x] Login realizado com sucesso
- [x] Tela de "Faltas e notas" acessada
- [x] Pelo menos 3 filtros preenchidos sequencialmente
- [x] Tráfego AJAX dos dropdowns capturado e documentado
- [x] Endpoint de busca do diário identificado
- [x] Pelo menos 10 screenshots capturados
- [x] Relatório .md gerado e salvo

---

> **Inicie a tarefa agora e documente tudo em tempo real.**
