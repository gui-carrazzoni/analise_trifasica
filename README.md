---
title: Analisador 87T
emoji: ⚡
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Análise de Sinais Trifásicos — Proteção Diferencial (87T)

Pipeline completo e modularizado em Python para análise de correntes trifásicas e
**Proteção Diferencial de Transformadores (Função ANSI 87T)**, com **interface web
interativa** (FastAPI) além do processamento em lote por linha de comando. O projeto
trata cenários de **Cold Load Pickup** (energização com carga conectada) e elimina
falsos disparos causados pela corrente de magnetização *inrush* através da
**Restrição de 2ª Harmônica**.

O leitor de COMTRADE é compatível com os formatos de oscilografia **ASCII** e
**BINARY** (IEEE C37.111-1999), com **detecção automática dos canais de corrente**
por fase (via Regex), dispensando reconfiguração manual a cada arquivo.

---

## ⚡ O Cenário e a Lógica de Proteção

Quando um transformador é energizado, a saturação temporária do núcleo de ferro
produz uma alta corrente de magnetização unilateral conhecida como **Inrush**.
Embora atinja valores várias vezes superiores à corrente nominal (simulando um
curto-circuito interno para o relé), a corrente de inrush possui uma assinatura
espectral característica: alto teor de **2ª harmônica (H2)** e uma componente de
decaimento contínuo (DC).

O pipeline implementa os seguintes passos:

1. **Geração/Carregamento dos Sinais:** simulação analítica de inrush + carga
   passante, ou leitura direta de oscilografia real em **COMTRADE** (ASCII/BINARY).
2. **Estimação Fasorial:** **DFT deslizante de ciclo completo** vetorizada em NumPy
   para extração contínua dos fasores de fundamental (H1 – 60 Hz) e 2ª harmônica
   (H2 – 120 Hz).
3. **Compensação Y-Δ de Grupo Vetorial:** alinhamento angular e de magnitude das
   correntes dos enrolamentos conforme a placa do transformador (grupos **Yd1** e
   **Yd11**).
4. **Corrente Diferencial ($I_{diff}$) e Característica de Restrição:** soma fasorial
   compensada por enrolamento, normalizada em pu pela **corrente de base (TAP)** de
   cada enrolamento, e comparada com a característica de **duplo declive (slope)**.
5. **Restrição Harmônica:** bloqueio do trip quando a razão H2/H1 excede o limiar
   configurado (tipicamente $15\%$), com lógica opcional de **Cross-blocking**
   (bloqueia todas as fases se qualquer uma acusar inrush).

### Estimação da corrente de base (TAP)
Quando o TAP não é informado manualmente, ele é **estimado a partir do próprio
registro**, ancorando o diferencial calculado nos canais `*-DIFF`/`*-BIAS` que o
relé gravou. A estimativa é feita **por enrolamento**, atribuindo o TAP ao lado que
de fato conduziu corrente e sinalizando como *indeterminado* o enrolamento que não
conduziu (lado em vazio ou falta alimentada por um lado só).

---

## 🌐 Interface Web (Analisador Interativo)

Uma aplicação **FastAPI** permite analisar um registro pelo navegador, sem código:

- Upload do par **`.CFG` + `.DAT`** (arraste-e-solte).
- Configuração do **grupo vetorial**, **lado em estrela** e **TAP** (estimado pelo
  registro ou informado manualmente, em base primária).
- **Veredito** automático: `TRIP` / `BLOQUEIO por 2ª Harmônica` / `ESTÁVEL`.
- **Tabela de métricas por fase** (Idiff, Ibias, razão H2/H1) e a origem do TAP.
- Galeria de **diagramas** (sinais/fasores, diferencial, característica de
  restrição, restrição harmônica, cross-blocking, validação contra o relé) com
  *lightbox* para ampliar.

```bash
python api.py
# abre em http://127.0.0.1:8000
```

---

## 📂 Estrutura do Projeto

```
analise_trifasica/
├── configs_analise/                # Módulos principais de análise (núcleo)
│   ├── __init__.py                 # Ponto de entrada do pacote e exportações
│   ├── config.py                   # Classe Config e matrizes de compensação Y-Δ
│   ├── generator.py                # Simulação e geração de sinais (Inrush e Carga)
│   ├── comtrade.py                 # Leitor de oscilografia COMTRADE (.cfg/.dat)
│   ├── dft.py                      # Algoritmo de DFT deslizante vetorizado
│   ├── protection.py               # Compensação Y-Δ, Idiff, slope, restrição H2 e TAP
│   ├── visualization.py            # Rotinas de plotagem (Matplotlib)
│   └── pipeline.py                 # Orquestrador geral do fluxo de dados
├── static/                         # Frontend da interface web
│   ├── index.html                  # Página do analisador
│   ├── style.css                   # Estilo (tema técnico escuro)
│   └── main.js                     # Lógica do formulário, veredito e lightbox
├── tests/                          # Testes automatizados (pytest)
├── casos_reais/                    # Entrada: seus arquivos .cfg/.dat (ignorada pelo Git)
├── resultados_lote/                # Saída: relatórios e gráficos do modo em lote
├── api.py                          # Servidor web FastAPI (interface interativa)
├── analisar_dados.py               # Script de análise em lote (linha de comando)
├── Dockerfile                      # Imagem para deploy (HF Spaces / Render)
├── .dockerignore                   # Mantém dados reais e caches fora da imagem
├── DEPLOY.md                       # Guia de publicação (link para WhatsApp)
├── requirements.txt                # Dependências do projeto
├── requirements-dev.txt            # Dependências de desenvolvimento (pytest)
├── .gitignore                      # Arquivos ignorados pelo Git
└── README.md                       # Este arquivo
```

---

## ⚙️ Instalação

### Pré-requisitos
* Python 3.8 ou superior

### Passos
```bash
# 1. Clone o repositório
git clone https://github.com/seu-usuario/analise_trifasica.git
cd analise_trifasica

# 2. Crie e ative o ambiente virtual
python3 -m venv .venv
source .venv/bin/activate  # No Linux/macOS
.venv\Scripts\activate     # No Windows

# 3. Instale as dependências
pip install -r requirements.txt
```

---

## 🚀 Como Executar

### 1. Interface Web — análise interativa de um registro (`api.py`)
```bash
python api.py
```
Abra **http://127.0.0.1:8000** no navegador, suba o par `.CFG` + `.DAT`, ajuste os
parâmetros e clique em **Executar análise**.

### 2. Processamento em Lote — vários registros de uma vez (`analisar_dados.py`)
1. Coloque os arquivos `.cfg` e `.dat` (ASCII ou BINARY) na pasta `./casos_reais/`
   (criada na primeira execução, se não existir).
2. Execute:
   ```bash
   python analisar_dados.py
   ```
3. Cada oscilografia é lida com **detecção automática dos canais de corrente** por
   fase; os resultados tabulares (`.csv`) e os gráficos (`.png`) são salvos em
   subpastas individuais dentro de `./resultados_lote/`.

---

## ☁️ Deploy (compartilhar por link)

Como a interface é uma página web, dá para hospedá-la em um serviço gratuito
(**Hugging Face Spaces** ou **Render**) e compartilhar apenas um **link** — sem
instalação para quem recebe, funcionando em qualquer sistema operacional. Os
arquivos `Dockerfile` e `.dockerignore` já estão prontos.

➡️ Passo a passo completo em **[`DEPLOY.md`](DEPLOY.md)**.

> Os **dados reais** (`casos_reais/`) ficam fora da imagem e do versionamento, por
> confidencialidade.

---

## 🧪 Testes

A lógica de proteção (DFT fasorial, corrente diferencial, característica de slope e
restrição harmônica) é coberta por testes automatizados com `pytest`.

```bash
# Instale as dependências de desenvolvimento
pip install -r requirements-dev.txt

# Rode a suíte de testes
python -m pytest
```
