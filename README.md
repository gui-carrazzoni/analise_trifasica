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

Este repositório contém um pipeline completo e modularizado em Python para análise de correntes trifásicas e simulação de **Proteção Diferencial de Transformadores (Função ANSI 87T)**. O projeto é focado no tratamento de cenários de **Cold Load Pickup** (energização com carga conectada) e na eliminação de falsos disparos causados pela corrente de magnetização inrush através da **Restrição de 2ª Harmônica**.

O leitor de COMTRADE é compatível com os formatos de oscilografia **ASCII** e **BINARY** (IEEE C37.111-1999). Ele possui rotinas de **detecção automática de canais de correntes** baseadas em Regex para facilitar a análise de múltiplos arquivos sem a necessidade de reconfiguração manual de canais.

---

## ⚡ O Cenário e a Lógica de Proteção

Quando um transformador é energizado, a saturação temporária do núcleo de ferro produz uma alta corrente de magnetização unilateral conhecida como **Inrush**. Embora atinja valores várias vezes superiores à corrente nominal (simulando um curto-circuito interno para o relé de proteção), a corrente de inrush possui uma assinatura espectral característica: um alto teor de **2ª harmônica (H2)** e uma componente de decaimento contínuo (DC).

Este pipeline implementa os seguintes passos de análise e proteção:
1. **Geração/Carregamento dos Sinais:** Simulação analítica do inrush + carga passante ou leitura direta de arquivos de oscilografia real em formato **COMTRADE** (ASCII ou BINARY).
2. **Estimação Fasorial:** Aplicação de uma **DFT deslizante de ciclo completo** otimizada com NumPy para extração contínua dos fasores de fundamental (H1 - 60 Hz) e segunda harmônica (H2 - 120 Hz).
3. **Compensação Y-Δ de Grupo Vetorial:** Alinhamento angular e de magnitude das correntes do primário e secundário de acordo com a placa do transformador (suporta grupos **Yd1** e **Yd11**).
4. **Cálculo da Corrente Diferencial ($I_{diff}$):** Soma fasorial compensada por enrolamento.
5. **Restrição Harmônica (Harmonic Restraint):** Bloqueio do trip do disjuntor quando a razão entre a magnitude de H2 e H1 excede o limiar configurado (tipicamente $15\%$). Suporta também a lógica de **Cross-blocking** (bloqueia todas as fases se qualquer uma acusar inrush).

---

## 📂 Estrutura do Projeto

```
analise_trifasica/
├── configs_analise/                # Pasta com os módulos principais de análise
│   ├── __init__.py                 # Ponto de entrada do pacote e exportações
│   ├── config.py                   # Classe Config e matrizes de compensação Y-Δ
│   ├── generator.py                # Simulação e geração de sinais (Inrush e Carga)
│   ├── comtrade.py                 # Leitor de arquivos de oscilografia COMTRADE (.cfg/.dat)
│   ├── dft.py                      # Algoritmo de DFT deslizante vetorizado
│   ├── protection.py               # Compensação Y-Δ, Idiff e restrição harmônica
│   ├── visualization.py            # Rotinas de plotagem gráfica (Matplotlib)
│   └── pipeline.py                 # Orquestrador geral do fluxo de dados
├── tests/                          # Testes automatizados (pytest)
├── casos_reais/                    # Pasta de entrada para colocar seus arquivos .cfg/.dat
├── resultados_lote/                # Pasta de saída com relatórios e gráficos gerados
├── analisar_dados.py               # Script principal para rodar a análise em lote
├── requirements.txt                # Dependências do projeto
├── requirements-dev.txt            # Dependências de desenvolvimento (pytest)
├── .gitignore                      # Arquivos ignorados pelo Git
└── README.md                       # Documentação principal (este arquivo)
```

---

## ⚙️ Instalação

### Pré-requisitos
* Python 3.8 ou superior

### Passos para Instalação
Recomenda-se o uso de um ambiente virtual para isolar as dependências do projeto:

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

### 1. Processamento em Lote de Casos Reais (`analisar_dados.py`)
Esta é a forma recomendada para analisar múltiplos arquivos de oscilografia reais de uma só vez:

1. Coloque seus arquivos `.cfg` e `.dat` (ASCII ou BINARY) dentro da pasta `./casos_reais/` (a pasta é criada na primeira execução caso não exista).
2. Execute o script:
   ```bash
   python analisar_dados.py
   ```
3. O script lerá cada oscilografia, fará a **detecção automática dos canais de corrente** por fase e salvará os resultados tabulares (.csv) e os gráficos salvos como imagem (.png) em subpastas individuais dentro de `./resultados_lote/`.

---

## 🧪 Testes

A lógica de proteção (DFT fasorial, corrente diferencial, característica de slope e restrição harmônica) é coberta por testes automatizados com `pytest`.

```bash
# Instale as dependências de desenvolvimento
pip install -r requirements-dev.txt

# Rode a suíte de testes
python -m pytest
```
