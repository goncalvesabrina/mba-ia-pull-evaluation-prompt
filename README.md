# Pull, Otimização e Avaliação de Prompts com LangChain e LangSmith

Refatoração de um prompt de baixa qualidade (`bug_to_user_story_v1`) em um prompt
otimizado (`bug_to_user_story_v2`) que converte relatos de bug em User Stories ágeis,
com pull/push no LangSmith Prompt Hub e avaliação automática por 5 métricas
LLM-as-Judge.

---

## Sumário

- [Técnicas Aplicadas (Fase 2)](#técnicas-aplicadas-fase-2)
- [Diagnóstico do prompt v1](#diagnóstico-do-prompt-v1)
- [Processo de Iteração](#processo-de-iteração)
- [Resultados Finais](#resultados-finais)
- [Como Executar](#como-executar)
- [Estrutura do Projeto](#estrutura-do-projeto)

---

## Técnicas Aplicadas (Fase 2)

O prompt otimizado está em [`prompts/bug_to_user_story_v2.yml`](prompts/bug_to_user_story_v2.yml).
Foram aplicadas **5 técnicas**, declaradas no metadado `techniques_applied` do YAML.

### 1. Role Prompting (persona + contexto)

**Por quê:** o v1 dizia apenas "Você é um assistente". Sem senioridade nem domínio
definidos, o modelo produzia texto genérico, ora técnico demais, ora superficial.
Uma persona com anos de experiência e contexto de trabalho ancora vocabulário,
nível de detalhe e critério de qualidade.

**Como foi aplicado** (seção `# PERSONA`):

```
Você é uma pessoa Product Manager sênior com 10 anos de experiência em times
ágeis de produto digital. Você é especialista em traduzir relatos de bug —
escritos por usuários, suporte ou QA — em User Stories acionáveis que um time
de engenharia consegue estimar e implementar sem precisar de esclarecimentos.
```

### 2. Few-shot Learning (obrigatório)

**Por quê:** é a técnica que mais move as métricas de formato e clareza. Descrever
o formato em prosa deixa margem de interpretação; mostrar pares entrada→saída
elimina a ambiguidade. Como o dataset tem bugs de três níveis de complexidade, um
único exemplo enviesaria a saída — por isso são **3 exemplos, um por nível**.

**Como foi aplicado** (seção `# EXEMPLOS`): cada exemplo tem um bloco `Relato:` e
um bloco `Saída:` completo.

| Exemplo | Complexidade | O que ensina |
|---|---|---|
| 1 — busca com acentos | simples | saída enxuta: User Story + 5 critérios, e **nada mais** |
| 2 — PDF corrompido | médio | acrescenta `Critérios Técnicos:` e `Contexto Técnico:` com os dados do relato |
| 3 — módulo de login | complexo | seções `=== ... ===`, critérios agrupados por letra, tasks etiquetadas |

Os exemplos usam bugs **inventados**, diferentes dos 15 do dataset de avaliação —
o prompt ensina o padrão, não decora as respostas.

### 3. Chain of Thought silencioso

**Por quê:** transformar um bug em User Story exige inferência em cadeia (quem é
afetado → o que a pessoa quer → qual o valor → quais critérios). Sem CoT, o modelo
pulava direto para o texto e produzia persona genérica e critérios rasos.
O detalhe crítico é o **silêncio**: as métricas de Precision e Clarity penalizam
conteúdo não solicitado, então expor o raciocínio derrubaria a nota. O prompt
manda raciocinar e depois entregar só o artefato.

**Como foi aplicado** (seção `# RACIOCÍNIO INTERNO — pense antes de escrever, NÃO exiba este raciocínio`):

```
1. IDENTIFICAR O USUÁRIO ...
2. IDENTIFICAR O DESEJO ...
3. IDENTIFICAR O VALOR ...
4. CLASSIFICAR A COMPLEXIDADE (SIMPLES | MÉDIO | COMPLEXO)
5. EXTRAIR OS FATOS (números, IDs, endpoints, severidade)
6. DERIVAR OS CRITÉRIOS
Depois de raciocinar, escreva APENAS o artefato final.
```

### 4. Skeleton of Thought (contrato de saída adaptativo)

**Por quê:** foi a técnica de maior impacto nas métricas. Ao analisar as respostas
de referência do dataset, ficou claro que **o formato esperado muda com a
complexidade do bug**: relatos simples esperam User Story + 5 critérios e nada
mais; relatos complexos esperam seções `=== ... ===` com tasks técnicas. Um único
formato fixo erraria metade do dataset — ou por falta (recall baixo nos complexos)
ou por excesso (precision baixa nos simples).

**Como foi aplicado** (seção `# CONTRATO DE SAÍDA`), o esqueleto é escolhido pelo
passo 4 do raciocínio:

| Complexidade | Esqueleto de saída |
|---|---|
| SIMPLES | `Como um... eu quero... para que...` + `Critérios de Aceitação:` com exatamente 5 linhas Dado/Quando/Então/E/E |
| MÉDIO | o acima + 1 bloco extra de critérios (Técnicos / Adicionais / Prevenção / Acessibilidade) + 1 bloco de contexto (`Contexto Técnico:` / `do Bug:` / `de Segurança:`) |
| COMPLEXO | `=== USER STORY PRINCIPAL ===`, `=== CRITÉRIOS DE ACEITAÇÃO ===` (grupos A., B., C...), `=== CRITÉRIOS TÉCNICOS ===`, `=== CONTEXTO DO BUG ===`, `=== TASKS TÉCNICAS SUGERIDAS ===` |

### 5. Regras explícitas + tratamento de edge cases

**Por quê:** as métricas de Precision penalizam alucinação e conteúdo fora de
escopo. Regras negativas explícitas ("não invente dados", "sem preâmbulo") são a
forma mais direta de eliminar esses erros.

**Como foi aplicado** — 10 regras obrigatórias, entre elas:

- Responder **somente** o artefato: sem "Claro, aqui está", sem cercas de código.
- Persona específica: `Como um usuário` sozinho é proibido.
- Descrever o comportamento desejado, nunca o defeito.
- **Não inventar dados** — números, IDs e endpoints só se estiverem no relato;
  quando faltar um dado, usar marcador como `[nome do gateway de pagamento]`.
  Exceção deliberada: convenções consagradas (HTTP 403, categoria OWASP) **devem**
  ser nomeadas, porque não são invenção.
- Generalizar a frase da User Story (`adicionar produtos ao carrinho`) e deixar o
  caso específico (`produto ID 1234`) nos critérios e no contexto.
- Detalhe proporcional: inflar a resposta é tratado como erro.

E 6 edge cases: relato vago, relato com vários problemas, texto já escrito como
User Story, texto que não é bug, relato em outro idioma e relato contendo dados
sensíveis.

### System vs User Prompt

O v1 colocava `{bug_report}` **dentro do system prompt** — misturando instrução
permanente com dado variável. Na v2 há separação estrita:

- **System prompt:** persona, raciocínio, contrato de saída, regras e exemplos.
  Não contém `{bug_report}` (há um teste automatizado garantindo isso).
- **User prompt:** apenas a instrução de execução e o relato, delimitado por tags:

```
<relato_de_bug>
{bug_report}
</relato_de_bug>
```

---

## Diagnóstico do prompt v1

Problemas identificados em [`prompts/bug_to_user_story_v1.yml`](prompts/bug_to_user_story_v1.yml):

| # | Problema | Consequência nas métricas | Correção na v2 |
|---|---|---|---|
| 1 | `{bug_report}` duplicado no system **e** no user prompt | o relato chega duas vezes; o modelo às vezes gera duas respostas | variável só no user prompt |
| 2 | Persona genérica ("um assistente") | vocabulário raso, sem critério de qualidade | Role Prompting sênior |
| 3 | Zero exemplos | formato imprevisível a cada execução | Few-shot com 3 exemplos |
| 4 | Nenhum formato de saída definido | não usava "Como um... eu quero..." nem Dado/Quando/Então → F1 e Clarity baixos | contrato de saída explícito |
| 5 | Nenhuma regra de comportamento | preâmbulos, comentários finais, dados inventados → Precision baixa | 10 regras obrigatórias |
| 6 | Nenhum tratamento de edge case | relatos complexos com 4 problemas viravam uma story genérica → recall baixo | 6 edge cases + esqueleto adaptativo |
| 7 | Instrução vaga ("crie uma user story a partir dele") | sem critérios de aceitação | critérios verificáveis obrigatórios |

---

## Processo de Iteração

| Iteração | Mudança | Efeito observado |
|---|---|---|
| 1 | Prompt v1 original (baseline) | saída sem formato padrão, sem critérios de aceitação; todas as métricas abaixo de 0.8 |
| 2 | Role Prompting + contrato de saída único + Few-shot com 1 exemplo simples | formato consistente, mas relatos complexos (bugs 13-15) recebiam saída curta demais → recall e F1 baixos |
| 3 | Skeleton of Thought adaptativo (simples/médio/complexo) + 3 exemplos, um por nível | eliminou o excesso nos relatos simples e a falta nos complexos — maior salto de F1 e Clarity |
| 4 | CoT silencioso + regras anti-preâmbulo e anti-alucinação | Precision sobe: sem "Claro, aqui está", sem raciocínio vazando, sem dados inventados |
| 5 | Ajuste fino: convenções técnicas (HTTP 403, OWASP) liberadas + generalização da frase da User Story | recall melhora nos bugs de segurança e nos simples, que na referência descrevem o comportamento geral |

**Como as iterações foram medidas:** cada rodada foi avaliada com as mesmas três
métricas base de `src/metrics.py` (F1, Clarity, Precision) contra os 15 exemplos de
`datasets/bug_to_user_story.jsonl`, exatamente como faz `src/evaluate.py`.

---

## Resultados Finais

### Comparativo v1 vs v2

<!-- PLACEHOLDER_RESULTADOS -->

### Evidências no LangSmith

- **Prompt público v2:** `https://smith.langchain.com/hub/<SEU_USERNAME>/bug_to_user_story_v2`
- **Dashboard do projeto:** `https://smith.langchain.com/projects/<SEU_PROJETO>`
- **Dataset de avaliação:** `<SEU_PROJETO>-eval`, com os 15 exemplos do `.jsonl`
- **Screenshots:** adicionar em `screenshots/` as capturas da avaliação com as
  notas ≥ 0.8 e o tracing detalhado de pelo menos 3 exemplos.

> Substitua `<SEU_USERNAME>` e `<SEU_PROJETO>` pelos valores de `USERNAME_LANGSMITH_HUB`
> e `LANGSMITH_PROJECT` configurados no seu `.env`.

---

## Como Executar

### Pré-requisitos

- Python 3.9 ou superior
- Conta no [LangSmith](https://smith.langchain.com/) com uma API Key
- API Key de um provider de LLM: [Google AI Studio](https://aistudio.google.com/app/apikey) (gratuito) ou [OpenAI](https://platform.openai.com/api-keys)

### 1. Ambiente virtual e dependências

```bash
python3 -m venv venv
```

```bash
source venv/bin/activate
```

```bash
pip install -r requirements.txt
```

No Windows, ative com `venv\Scripts\activate`.

### 2. Configurar variáveis de ambiente

```bash
cp .env.example .env
```

Preencha o `.env`:

| Variável | Descrição |
|---|---|
| `LANGSMITH_API_KEY` | API Key do LangSmith (Settings → API Keys) |
| `LANGSMITH_PROJECT` | Nome do projeto onde os traces serão gravados |
| `USERNAME_LANGSMITH_HUB` | Seu handle no Prompt Hub — publique qualquer prompt, abra-o e clique no cadeado 🔒 para vê-lo |
| `GOOGLE_API_KEY` | API Key do Gemini (se `LLM_PROVIDER=google`) |
| `OPENAI_API_KEY` | API Key da OpenAI (se `LLM_PROVIDER=openai`) |
| `LLM_MODEL` / `EVAL_MODEL` | Modelo usado para gerar e para avaliar |

**Nota sobre o modelo Gemini:** o `gemini-2.5-flash` citado no enunciado não está
mais disponível para chaves novas (a API responde `404 ... no longer available to
new users`). Este projeto foi executado com **`gemini-3.5-flash`**. Para listar os
modelos disponíveis na sua chave:

```bash
python -c "import google.generativeai as g; g.configure(api_key='SUA_KEY'); [print(m.name) for m in g.list_models() if 'generateContent' in m.supported_generation_methods]"
```

### 3. Pull do prompt ruim (v1)

```bash
python src/pull_prompts.py
```

Baixa `leonanluppi/bug_to_user_story_v1` do Prompt Hub e salva em
`prompts/bug_to_user_story_v1.yml`.

### 4. Push do prompt otimizado (v2)

```bash
python src/push_prompts.py
```

Valida `prompts/bug_to_user_story_v2.yml`, monta o `ChatPromptTemplate`
(system + human), publica como `{USERNAME_LANGSMITH_HUB}/bug_to_user_story_v2` e
marca o prompt como **público**, com descrição, tags e README.

### 5. Avaliação

```bash
python src/evaluate.py
```

Cria o dataset no LangSmith a partir do `.jsonl`, puxa o prompt v2 do Hub, executa
os 15 exemplos e calcula as 5 métricas.

### 6. Testes de validação

```bash
pytest tests/test_prompts.py -v
```

Os testes rodam **offline** (não consomem API): validam a estrutura do YAML, a
persona, o formato exigido, os exemplos few-shot, a ausência de `[TODO]` e o
mínimo de 2 técnicas declaradas.

---

## Estrutura do Projeto

```
mba-ia-pull-evaluation-prompt/
├── .env.example                      # Template das variáveis de ambiente
├── requirements.txt                  # Dependências Python
├── README.md                         # Esta documentação
│
├── prompts/
│   ├── bug_to_user_story_v1.yml      # Prompt inicial, de baixa qualidade
│   └── bug_to_user_story_v2.yml      # Prompt otimizado ✅
│
├── datasets/
│   └── bug_to_user_story.jsonl       # 15 bugs (5 simples, 7 médios, 3 complexos)
│
├── src/
│   ├── pull_prompts.py               # Pull do LangSmith ✅
│   ├── push_prompts.py               # Push público ao LangSmith ✅
│   ├── evaluate.py                   # Avaliação automática (fornecido)
│   ├── metrics.py                    # Métricas LLM-as-Judge (fornecido)
│   └── utils.py                      # Funções auxiliares (fornecido)
│
└── tests/
    └── test_prompts.py               # 7 testes de validação ✅
```

### As 5 métricas

Três métricas são medidas diretamente por LLM-as-Judge em `src/metrics.py`, e duas
são derivadas delas em `src/evaluate.py`:

| Métrica | Origem | O que mede |
|---|---|---|
| **F1-Score** | base | média harmônica entre precision e recall da resposta contra a referência |
| **Clarity** | base | organização, linguagem, ausência de ambiguidade e concisão |
| **Precision** | base | ausência de alucinações, foco na pergunta e correção factual |
| **Helpfulness** | derivada | `(Clarity + Precision) / 2` |
| **Correctness** | derivada | `(F1-Score + Precision) / 2` |

Critério de aprovação: **todas** as 5 métricas ≥ 0.8 **e** a média ≥ 0.8.
