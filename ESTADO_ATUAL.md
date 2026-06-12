# Estado Atual da Investigação — Diagnóstico de Cross-blocking

> **Aviso de confidencialidade.** Este documento registra apenas o **raciocínio
> técnico e metodológico** da investigação. Nenhum dado de oscilografia, nome de
> instalação/ativo, data, identificador de equipamento ou trecho de documento
> operativo é reproduzido aqui. Os únicos números citados são **ajustes de
> proteção genéricos** (ex.: pickup, limite de 2ª harmônica) e **valores de
> reconstrução do algoritmo**, que não identificam nenhuma instalação.

---

## 1. Objetivo

Entender por que a ferramenta de diagnóstico
(`plotar_diagnostico_cross_blocking`) classificou um caso real de energização
como **"cross-blocking NÃO NECESSÁRIO"**, sendo que, na realidade, houve atuação
indevida da proteção diferencial (87) durante a energização e o cross-blocking
foi adotado como medida corretiva.

A suspeita inicial — levantada na revisão — era de **erro de precisão**: uma
incoerência entre o que o algoritmo conclui e o que o evento real demonstrou.

---

## 2. Como a decisão é tomada (dois portões em série)

A função 87 só dispara quando uma fase passa pelos **dois** critérios:

1. **Pickup (magnitude):** a corrente diferencial precisa ultrapassar o ajuste
   de pickup (no caso analisado, **0,2 pu**). Abaixo disso, o elemento nem
   desperta — independentemente do conteúdo harmônico. *O TAP influencia este
   portão* (ele é quem escala a corrente para pu).
2. **Restrição de 2ª harmônica (inrush):** se a razão **H2/H1 > 15%**, a fase é
   **bloqueada** (interpreta-se como energização, não defeito). *O TAP NÃO
   influencia este portão*, porque H2/H1 é uma razão (a escala se cancela).

**O cross-blocking atua exclusivamente sobre o portão 2:** ele estende o
bloqueio de uma fase às demais. Logo, o discriminador do cross-blocking é o
**harmônico (DFT)**, não o pickup. O pickup apenas define **quais fases são
candidatas** a disparar.

---

## 3. Apurações (o que já foi verificado)

### 3.1. A incoerência é real e é um falso negativo
- No registro analisado, a fase que efetivamente atuou apresenta, na **nossa
  reconstrução via DFT**, um mínimo de **H2/H1 ≈ 19%** no instante crítico —
  ou seja, **acima** do limite de 15%. Como o algoritmo nunca vê essa fase
  "desprotegida" (H2/H1 < 15% enquanto quer disparar), ele conclui que o
  cross-blocking seria dispensável.
- Na operação real, a mesma fase teve o harmônico medido **abaixo de 15%**,
  liberou o bloqueio e atuou. A diferença é de **~4 pontos percentuais**,
  exatamente em cima da linha de decisão.

### 3.2. Mudar o TAP não altera o veredito
- Testado com TAP manual e com TAP estimado: o resultado permanece
  "NÃO NECESSÁRIO".
- Causa: o que trava a decisão é o portão harmônico (item 2), e **H2/H1
  independe do TAP**. Nenhum valor de TAP move essa conta.

### 3.3. O filtro do relé é da mesma família do nosso DFT
- A plataforma do relé (família MiCOM Px40) usa, conforme documentação pública,
  um **algoritmo de Fourier de um ciclo com 24 amostras/ciclo, com rastreamento
  de frequência**.
- O registro analisado está na **mesma taxa (24 amostras/ciclo)**.
- Conclusão: o "filtro cosseno do relé" é, na prática, **o mesmo DFT de um ciclo
  que já implementamos** (`configs_analise/dft.py`). O ramo cosseno é apenas a
  parte real desse Fourier.

### 3.4. Testar o filtro cosseno não reproduz o evento
- Implementamos e validamos um **filtro cosseno** (quadratura por cosseno
  atrasado de ¼ de ciclo, com melhor rejeição de DC) e comparamos com o DFT
  padrão, nas **três fases**.
- Resultado: **nenhum** dos dois filtros reproduz o comportamento real
  ("somente uma fase libera o bloqueio"):
  - DFT padrão → nenhuma fase fura os 15% (modelo diria "nenhum trip").
  - Cosseno → quem fura é **outra** fase, não a que atuou (modelo acusaria a
    fase errada).
- Ou seja, trocar de filtro **não corrige; apenas desloca o erro de fase**.

### 3.5. Não há embaralhamento de fases
- Verificado por correlação cruzada entre o nosso diferencial e os canais
  diferenciais gravados pelo relé, e por casamento de pico: a fase que atuou na
  nossa reconstrução **corresponde** à mesma fase do relé (pico praticamente
  idêntico; correlação ≈ 0,98).
- As correlações cruzadas altas entre fases distintas decorrem apenas de o
  **envelope do inrush** subir e descer junto nas três — não é troca de rótulo.

### 3.6. Desalinhamento temporal de ~1 ciclo
- A nossa reconstrução fasorial está **adiantada em ~1 ciclo** em relação às
  grandezas gravadas pelo relé (o DFT deslizante rotula o fasor no **início** da
  janela). Isso desalinha o instante do nosso "evento" frente ao instante real
  de atuação e contamina qualquer comparação feita amostra a amostra.

### 3.7. Magnitude por fase não casa perfeitamente
- Sob a compensação adotada, a fase que atuou casa bem em magnitude com o canal
  do relé, mas as **outras duas fases divergem** (uma superestimada, outra
  subestimada). Indício de que um **TAP/compensação único** não reproduz as três
  fases simultaneamente — questão de *magnitude*, não de rótulo.

---

## 4. Questionamentos em aberto

Cada item abaixo está no formato **pergunta → o que a investigação sugere até
agora → o que ainda falta decidir/fazer**.

### Q1. O discriminador é o pickup ou a restrição harmônica?
- **Sugere:** é a **restrição harmônica (H2/H1, 15%)**. O pickup apenas habilita
  as fases candidatas; no caso, todas as fases ultrapassaram o pickup, e o que
  separou "dispara" de "não dispara" foi o harmônico de uma única fase.
- **Falta:** consolidar isso como premissa de projeto do diagnóstico.

### Q2. Se usássemos o filtro real do relé, o H2/H1 furaria os 15%?
- **Sugere:** **não de forma confiável.** O filtro é da mesma família do nosso
  DFT (item 3.3) e o teste com cosseno (item 3.4) não reproduziu o evento.
- **Falta:** decidir se vale (ou não) investir em uma versão "relé-fiel"
  (frequência rastreada + alinhamento causal da janela) só para confirmar a
  expectativa de que ainda assim não cruzaria.

### Q3. Por que o nosso algoritmo não reproduz a liberação real?
- **Sugere:** soma de fatores pequenos — (a) **desalinhamento de ~1 ciclo**
  (item 3.6), (b) **ausência de rastreamento de frequência** (assumimos
  frequência fixa), (c) **forte componente DC** da energização afetando a
  estimativa, e (d) o registro ser uma **reconstrução posterior e decimada**.
  Nenhum domina; juntos dão alguns pontos percentuais — o suficiente, dado que
  o valor verdadeiro estava colado nos 15%.
- **Falta:** quantificar a contribuição de cada fator (principalmente
  alinhamento de janela e frequência) — se decidirmos seguir por aí.

### Q4. A convenção de janela do DFT (`dft.py`) é um bug?
- **Sugere:** o rótulo do fasor no **início** da janela gera adiantamento de ~1
  ciclo. O usual em proteção é rotular no **fim** da janela (causal). É uma
  correção legítima de código, independente do resto.
- **Falta:** decidir se corrigimos a convenção (afeta o **timing** de todas as
  grandezas; não muda a **profundidade** do vale de H2/H1, então não resolve
  sozinho o falso negativo).

### Q5. TAP único vs TAP por fase / compensação.
- **Sugere:** um TAP/compensação único não reproduz a magnitude das três fases
  (item 3.7). Afeta apenas o **portão de magnitude (pickup)**, não o harmônico.
- **Falta:** decidir se vale TAP por enrolamento/fase apenas para a fidelidade
  de magnitude (não muda a decisão do caso, que é harmônica).

### Q6. Como o diagnóstico deveria tratar o "knife-edge"?
- **Sugere:** uma decisão binária (verde/vermelho) sobre um valor que ficou a
  ~4 pontos do limite é frágil. Uma **banda de guarda** ("marginal /
  recomendado" quando H2/H1 fica a poucos pontos do limite no instante de
  risco) reflete melhor a incerteza do estimador. Tudo continua medido pelo DFT;
  só a *interpretação* ganha tolerância.
- **Falta:** decidir se adotamos a banda de guarda e qual largura (a própria
  discrepância observada — ~4 pontos — é uma referência empírica).

### Q7. Qual deve ser a fonte da verdade do veredito?
- **Sugere:** o dado **gravado pelo relé** (flags de trip por fase e canais
  diferenciais) é a verdade-terreno do *fato*; o **DFT** é a melhor ferramenta
  para *explicar* o fenômeno (inrush, queda do 2º harmônico).
- **Falta:** **decisão do usuário** — ainda não foi escolhido o caminho.

---

## 5. Caminhos possíveis (NENHUM decidido ainda)

> O usuário pediu para **não** seguir por um caminho de implementação por
> enquanto. Esta seção apenas cataloga as opções já levantadas, sem comprometer
> escolha.

- **(A) Versão "relé-fiel" do DFT:** adicionar rastreamento de frequência e
  alinhamento causal da janela, mantendo Fourier. Expectativa: não deve cruzar
  os 15%, mas confirmaria a hipótese.
- **(B) Veredito ancorado no dado gravado + DFT explicativo:** usar flags/canais
  do relé para o veredito e o DFT para a narrativa do fenômeno.
- **(C) Banda de guarda no diagnóstico:** sinalizar "marginal/recomendado"
  quando o H2/H1 (DFT) ficar a poucos pontos do limite no instante de risco.
- **(D) Correção da convenção de janela do DFT** (Q4) — independente das demais.
- **(E) TAP por fase** (Q5) — apenas fidelidade de magnitude.

---

## 6. Resumo de uma linha

O "NÃO NECESSÁRIO" é um **falso negativo**: o discriminador é o **harmônico
(DFT)**, o valor real ficou **em cima da linha dos 15%**, e a nossa reconstrução
(mesmo com o filtro do relé) parou ~4 pontos acima — sem conseguir cravar de que
lado da linha o evento caiu. O cross-blocking **é necessário**; a confirmação
sólida vem do registro do próprio relé.

---

*Documento de estado da investigação. Próximo passo aguarda decisão sobre qual
dos caminhos da Seção 5 seguir.*
