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
afetado → o que a pessoa quer → qual o valor → quais critérios). Explicitar essa
cadeia força o modelo a decidir a persona e o valor **antes** de escrever, em vez
de improvisá-los no meio da frase.
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

Os defeitos abaixo são verificáveis lendo o próprio YAML do v1 — a coluna de risco
descreve o que cada defeito **deixa em aberto**, não uma medição.

| # | Defeito no prompt | Risco que introduz | Correção na v2 |
|---|---|---|---|
| 1 | `{bug_report}` duplicado no system **e** no user prompt | o relato chega duas vezes ao modelo; mistura instrução permanente com dado variável | variável só no user prompt |
| 2 | Persona genérica ("um assistente") | nada ancora vocabulário nem nível de detalhe | Role Prompting sênior |
| 3 | Zero exemplos | o formato fica a cargo do modelo e varia entre execuções | Few-shot com 3 exemplos |
| 4 | Nenhum formato de saída definido | nada garante "Como um... eu quero..." nem Dado/Quando/Então | contrato de saída explícito |
| 5 | Nenhuma regra de comportamento | nada impede preâmbulo, comentário final ou dado inventado | 10 regras obrigatórias |
| 6 | Nenhum tratamento de edge case | relato com 4 problemas pode virar uma story genérica só do primeiro | 6 edge cases + esqueleto adaptativo |
| 7 | Instrução vaga ("crie uma user story a partir dele") | critérios de aceitação não são sequer pedidos | critérios verificáveis obrigatórios |

Na prática, a medição mostrou que os modelos Gemini atuais compensam boa parte
desses defeitos por conta própria — ver [Resultados Finais](#resultados-finais).

---

## Processo de Iteração

| # | Etapa | O que gerou a decisão |
|---|---|---|
| 1 | Diagnóstico do v1 | leitura do YAML: os 7 problemas da tabela acima |
| 2 | **Análise das respostas de referência do dataset** | leitura dos 15 pares `inputs`/`outputs` do `.jsonl` — foi aqui que apareceu a descoberta central: o formato esperado **muda com a complexidade** (5 critérios secos nos simples; seções `=== ... ===` com tasks técnicas nos complexos) |
| 3 | Escrita do v2 | as 5 técnicas aplicadas de uma vez, com o contrato de saída já adaptativo por causa do passo 2 |
| 4 | Inspeção manual de 2 saídas (bug simples nº 1 e bug de segurança nº 8) | duas correções: (a) o prompt escrevia "erro de permissão" em vez de **HTTP 403**, porque a regra anti-alucinação era rígida demais → liberadas convenções consagradas; (b) a User Story ficava presa ao caso pontual ("adicionar o produto ID 1234") enquanto as referências generalizam → regra 5.1 |
| 5 | Avaliação completa (`src/evaluate.py`, 15 exemplos) | **aprovado na primeira rodada completa**: todas as 5 métricas ≥ 0.8 |

**Transparência sobre o processo.** O enunciado antecipa 3-5 iterações de
push→avaliar→refatorar. Não foi o que aconteceu aqui: o esforço se concentrou no
passo 2 (analisar as respostas esperadas **antes** de escrever o prompt), e a
avaliação completa passou de primeira. As duas correções do passo 4 vieram de
inspeção manual das saídas, não de uma rodada de métricas reprovada.

Um fator prático pesou nessa escolha: a cota do free tier do Gemini é **por modelo
e por dia**, e uma rodada completa custa 60 chamadas (15 gerações + 45 de juiz).
Iterar às cegas contra a métrica sairia caro; ler as referências primeiro foi mais
barato e mais informativo.

---

## Resultados Finais

### Saída do `python src/evaluate.py`

```
==================================================
Prompt: sgoncalvesabrina/bug_to_user_story_v2
==================================================

Métricas Derivadas:
  - Helpfulness: 0.90 ✓
  - Correctness: 0.89 ✓

Métricas Base:
  - F1-Score: 0.90 ✓
  - Clarity: 0.91 ✓
  - Precision: 0.88 ✓

--------------------------------------------------
📊 MÉDIA GERAL: 0.8975
--------------------------------------------------

✅ STATUS: APROVADO - Todas as métricas >= 0.8
```

### Comparativo v1 vs v2

O v1 também foi executado contra o mesmo dataset e as mesmas métricas. **A cota
diária do free tier do Gemini impediu completar os 15 exemplos do v1** — 7 exemplos
retornaram erro de cota, e `src/metrics.py` devolve `0.0` quando o juiz falha.
Incluir esses zeros produziria um baseline artificialmente baixo (~0.45), então a
tabela abaixo compara **apenas os 8 exemplos em que ambas as versões foram
efetivamente avaliadas** (1, 2, 3, 4, 5, 13, 14, 15):

| Métrica | v1 (8 exemplos) | v2 (mesmos 8) | Δ |
|---|---|---|---|
| Helpfulness | 0.8706 | **0.9050** | +0.034 |
| Correctness | 0.8850 | **0.9012** | +0.016 |
| F1-Score | **0.9350** | 0.9050 | −0.030 |
| Clarity | 0.9062 | **0.9125** | +0.006 |
| Precision | 0.8350 | **0.8975** | +0.063 |
| **Média** | 0.8864 | **0.9042** | +0.018 |

**Leitura honesta deste resultado.** O enunciado sugere um baseline em torno de
0.45 para o v1, mas isso não se confirmou na medição: com os modelos Gemini atuais,
o prompt ruim já produz User Stories razoáveis, porque o modelo compensa boa parte
da falta de instrução. O ganho real do v2 está concentrado onde a engenharia de
prompt de fato atua:

- **Precision (+0.063), o maior ganho.** É a métrica que penaliza alucinação e
  conteúdo fora de escopo. O v1 teve casos de 0.73 e 0.77; **o pior caso do v2 foi
  0.83**. As regras anti-preâmbulo e anti-invenção são o que produz isso.
- **Consistência.** A dispersão do v2 é menor: nenhuma métrica individual caiu
  abaixo de 0.77 em nenhum dos 15 exemplos.
- **F1 ligeiramente menor (−0.030).** O v1 tende a produzir respostas mais longas,
  e uma resposta mais longa naturalmente cobre mais tokens da referência, o que
  favorece o componente de recall do F1. O v2 troca um pouco desse recall por
  precisão e concisão — que é exatamente o trade-off que o contrato de saída
  adaptativo busca.

Ou seja: o v2 vence em 4 das 5 métricas e na média, mas o ganho é de **qualidade e
previsibilidade**, não o salto dramático que o enunciado antecipa. Reportar
"0.45 → 0.90" aqui seria reportar o artefato da cota estourada, não a medição.

> Para reproduzir o baseline completo do v1, é preciso cota suficiente para 60
> chamadas (15 gerações + 45 chamadas de juiz) em um único modelo.

### Resultado por exemplo (v2)

| # | Complexidade | F1 | Clarity | Precision |
|---|---|---|---|---|
| 1 | simples | 0.92 | 0.85 | 0.83 |
| 2 | simples | 0.92 | 0.95 | 0.93 |
| 3 | simples | 0.92 | 0.90 | 0.93 |
| 4 | simples | 0.90 | 0.95 | 0.93 |
| 5 | simples | 0.82 | 0.90 | 0.83 |
| 6 | médio | 0.92 | 0.90 | 0.87 |
| 7 | médio | 1.00 | 0.95 | 0.93 |
| 8 | médio | 0.92 | 0.95 | 0.93 |
| 9 | médio | 0.87 | 0.85 | 0.87 |
| 10 | médio | 0.77 | 0.85 | 0.83 |
| 11 | médio | 0.90 | 0.95 | 0.83 |
| 12 | médio | 0.87 | 0.90 | 0.83 |
| 13 | complexo | 0.97 | 0.90 | 0.93 |
| 14 | complexo | 0.92 | 0.95 | 0.93 |
| 15 | complexo | 0.87 | 0.90 | 0.87 |

Nenhum exemplo ficou abaixo de 0.77, e os três relatos complexos — os mais
difíceis — ficaram entre 0.87 e 0.97, o que confirma o efeito do esqueleto de
saída adaptativo.

**Modelos utilizados nesta execução:** geração com `gemini-3-flash-preview`,
avaliação com `gemini-3.5-flash-lite`. A cota do free tier do Gemini é **por
modelo e por dia**, então separar geração e avaliação em modelos diferentes evita
esgotar a cota no meio de uma rodada.

### Evidências no LangSmith

- **Prompt público v2:** https://smith.langchain.com/hub/sgoncalvesabrina/bug_to_user_story_v2
- **Dashboard do projeto:** Projeto `prompt-optimization-challenge` em https://smith.langchain.com/
- **Dataset de avaliação:** `prompt-optimization-challenge-eval`, com os 15 exemplos do `.jsonl` ✅ criado
- **Screenshots:** adicionar em `screenshots/` as capturas da avaliação com as
  notas ≥ 0.8 e o tracing detalhado de pelo menos 3 exemplos.

O tracing de todas as 15 execuções ficou registrado no projeto
`prompt-optimization-challenge`, já que `LANGSMITH_TRACING=true`.

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
