"""Rotinas de plotagem (Matplotlib) para sinais, diferencial e restrição."""

from __future__ import annotations

import logging

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from configs_analise.config import Config
from configs_analise.protection import (
    estimar_corrente_base,
    _canais_diff_disponiveis,
    obter_limiar_operacao,
)

logger = logging.getLogger(__name__)

_ROTULOS_LADO = {"p": "Primário (W1)", "s": "Secundário (W2)"}


def _resolver_tap(
    df_fasores: pd.DataFrame, df_raw: pd.DataFrame, cfg: Config
) -> tuple[float | None, str]:
    """Prioridade: tap_s_a_por_pu → tap_p_a_por_pu → estimativa empírica."""
    if cfg.tap_s_a_por_pu is not None:
        return cfg.tap_s_a_por_pu, "manual (tap_s_a_por_pu)"
    if cfg.tap_p_a_por_pu is not None:
        return cfg.tap_p_a_por_pu, "manual (tap_p_a_por_pu)"
    return estimar_corrente_base(df_fasores, df_raw, cfg), "estimado via pico DIFF"


def _escala_para_pu(
    tap: float | None, origem: str
) -> tuple[float, str, str, str]:
    """Devolve (escala, unidade, rótulo_calc, info_tap) para o eixo Y."""
    if tap is not None and tap > 0:
        return (
            1.0 / tap,
            "pu",
            "Idiff calculada (pu)",
            f"TAP: {tap:.1f} A_sec/pu ({origem})",
        )
    return (
        1.0,
        "A",
        "Idiff calculada (A)",
        "TAP indisponível — curvas em escalas distintas",
    )


def _mostrar_se_interativo() -> None:
    """Exibe a figura apenas em backends interativos (no-op sob 'Agg')."""
    if plt.get_backend().lower() != "agg":
        plt.show()


def _estilizar_eixo(ax, ylabel: str) -> None:
    ax.set_ylabel(ylabel)
    ax.grid(True, linestyle=":", alpha=0.7)
    ax.legend(loc="upper right", fontsize=8)


def _pico_lado(df_sinais: pd.DataFrame, cfg: Config, lado: str) -> float:
    """Pico absoluto entre as três fases do lado indicado."""
    return float(max(df_sinais[f"I{f}_{lado}"].abs().max() for f in cfg.fases))


def plotar_sinais_e_fasores(
    df_sinais: pd.DataFrame, df_fasores: pd.DataFrame, cfg: Config
) -> None:
    """Sinal instantâneo + magnitude fasorial H1, lado-a-lado (grid 3×2).

    Eixos Y independentes por lado: o enrolamento em vazio e o energizado
    ficam ambos visíveis na mesma figura sem que um esmague o outro.
    """
    picos = {lado: _pico_lado(df_sinais, cfg, lado) for lado in ("p", "s")}

    fig, axs = plt.subplots(len(cfg.fases), 2, figsize=(12, 8), sharex=True)
    for linha, fase in enumerate(cfg.fases):
        for col, lado in enumerate(("p", "s")):
            ax = axs[linha, col]
            ax.plot(
                df_sinais["tempo"],
                df_sinais[f"I{fase}_{lado}"],
                color=cfg.cores[fase],
                alpha=0.7,
                label=f"Sinal I{fase.upper()}_{lado.upper()}",
            )
            ax.plot(
                df_fasores["tempo"],
                df_fasores[f"Mag_I{fase}_{lado}_H1"],
                color="red",
                linestyle="--",
                linewidth=2,
                label=f"|I{fase.upper()}_{lado.upper()}| H1",
            )
            _estilizar_eixo(ax, "Corrente (A)" if col == 0 else "")
            if linha == 0:
                ax.set_title(
                    f"{_ROTULOS_LADO[lado]} — pico {picos[lado]:.2f} A",
                    fontsize=11,
                    fontweight="bold",
                )

    for ax in axs[-1, :]:
        ax.set_xlabel("Tempo (s)")
    plt.suptitle(
        "Correntes de entrada e estimação fasorial H1 (60 Hz) — "
        "ambos os enrolamentos",
        fontsize=14,
        fontweight="bold",
    )
    plt.tight_layout()
    _mostrar_se_interativo()


def plotar_diferencial(df_diff: pd.DataFrame, cfg: Config) -> None:
    """Correntes diferenciais (H1) por fase."""
    plt.figure(figsize=(10, 4))
    for fase in cfg.fases:
        plt.plot(
            df_diff["tempo"],
            df_diff[f"Idiff_{fase}"],
            color=cfg.cores[fase],
            label=f"Idiff fase {fase.upper()}",
        )
    plt.axhline(0, color="black", linestyle="--", linewidth=1)
    plt.xlabel("Tempo (s)")
    plt.ylabel("Corrente diferencial (A)")
    plt.grid(True, linestyle=":", alpha=0.7)
    plt.legend()
    plt.suptitle(
        "Correntes diferenciais H1 — inrush causa falso diferencial alto",
        fontsize=14,
        fontweight="bold",
    )
    plt.tight_layout()
    _mostrar_se_interativo()


def plotar_restricao_harmonica(df_restricao: pd.DataFrame, cfg: Config) -> None:
    """Razão H2/H1 e Idiff de operação após bloqueio harmônico."""
    fig, (ax_razao, ax_idiff) = plt.subplots(2, 1, figsize=(10, 6), sharex=True)

    for fase in cfg.fases:
        cor = cfg.cores[fase]
        ax_razao.plot(
            df_restricao["tempo"],
            df_restricao[f"Razao_H2_H1_{fase}"],
            color=cor,
            label=f"H2/H1 fase {fase.upper()}",
        )
        ax_idiff.plot(
            df_restricao["tempo"],
            df_restricao[f"Idiff_Operacao_{fase}"],
            color=cor,
            linestyle="--",
            label=f"Idiff Operação {fase.upper()}",
        )

    ax_razao.axhline(
        cfg.limite_bloqueio_h2,
        color="red",
        linestyle=":",
        linewidth=1.5,
        label=f"Limite {cfg.limite_bloqueio_h2*100:.0f}%",
    )
    ax_razao.set_ylabel("Razão H2 / H1")
    ax_razao.legend(loc="upper right")
    ax_razao.grid(True, linestyle=":", alpha=0.7)
    ax_razao.set_title(
        "Razão H2/H1 — acima da linha vermelha = inrush detectado, "
        "trip bloqueado"
    )

    ax_idiff.axhline(0, color="black", linestyle="--", linewidth=1)
    ax_idiff.set_ylabel("Idiff após bloqueio (A)")
    ax_idiff.set_xlabel("Tempo (s)")
    ax_idiff.legend(loc="upper right")
    ax_idiff.grid(True, linestyle=":", alpha=0.7)
    ax_idiff.set_title(
        "Corrente diferencial após restrição harmônica — "
        "falso trip eliminado"
    )

    plt.suptitle(
        "Lógica de Restrição Harmônica (Harmonic Restraint)",
        fontsize=14,
        fontweight="bold",
    )
    plt.tight_layout()
    _mostrar_se_interativo()


def plotar_validacao_rele(
    df_diff: pd.DataFrame,
    df_fasores: pd.DataFrame,
    df_raw: pd.DataFrame,
    cfg: Config,
) -> None:
    """Sobrepõe Idiff calculada (em pu, via TAP) vs Idiff registrada pelo relé."""
    canais_diff = _canais_diff_disponiveis(df_raw, cfg)
    if len(canais_diff) != 3:
        logger.info(
            "ℹ️  Canais de Idiff do relé não disponíveis no .CFG — pulando validação."
        )
        return

    tap, origem = _resolver_tap(df_fasores, df_raw, cfg)
    escala, unidade, rotulo_calc, info_tap = _escala_para_pu(tap, origem)
    logger.info(f"📐 {info_tap}")

    fig, axs = plt.subplots(3, 1, figsize=(10, 8), sharex=True)
    for ax, fase, canal in zip(axs, cfg.fases, canais_diff):
        ax.plot(
            df_diff["tempo"],
            df_diff[f"Idiff_{fase}"] * escala,
            color=cfg.cores[fase],
            linewidth=2,
            label=f"{rotulo_calc} — fase {fase.upper()}",
        )
        ax.plot(
            df_raw["tempo"],
            df_raw[canal],
            color="black",
            linestyle="--",
            linewidth=1,
            alpha=0.8,
            label=f"{canal} (relé, pu)",
        )
        ax.set_ylabel(f"Corrente ({unidade})")
        ax.grid(True, linestyle=":", alpha=0.7)
        ax.legend(loc="upper right")
    axs[-1].set_xlabel("Tempo (s)")
    plt.suptitle(
        f"Validação: pipeline vs registro do relé — {info_tap}",
        fontsize=13,
        fontweight="bold",
    )
    plt.tight_layout()
    _mostrar_se_interativo()


def plotar_diagnostico_cross_blocking(
    df_restricao: pd.DataFrame, cfg: Config
) -> None:
    """Visualiza se o cross-blocking é necessário ou não para o caso.
    
    Usa um formato de analisador lógico com 3 subplots (um para cada fase)
    mostrando claramente os estados binários de bloqueio, trip de característica
    e trip desprotegido.
    """
    if not any(
        f"Bloqueio_individual_{f}" in df_restricao.columns for f in cfg.fases
    ):
        return

    # 1. Calcula os estados globais de inrush e risco
    tempo = df_restricao["tempo"].to_numpy()
    
    # Inrush ativo em qualquer fase
    colunas_bloq_indiv = [f"Bloqueio_individual_{f}" for f in cfg.fases]
    inrush_ativo = df_restricao[colunas_bloq_indiv].any(axis=1).to_numpy()
    
    # Trip desprotegido em qualquer fase (fase quer operar, mas seu próprio H2/H1 caiu)
    trip_desprotegido = np.zeros(len(df_restricao), dtype=bool)
    for fase in cfg.fases:
        if f"Trip_Caracteristica_{fase}" in df_restricao.columns:
            trip_caract = df_restricao[f"Trip_Caracteristica_{fase}"].to_numpy()
            bloq_indiv = df_restricao[f"Bloqueio_individual_{fase}"].to_numpy()
            trip_desprotegido |= (trip_caract & ~bloq_indiv)
            
    # Risco de atuação indevida sem Cross-blocking:
    risco_sem_cross = inrush_ativo & trip_desprotegido
    cross_necessario = risco_sem_cross.any()
    
    # Criamos 3 subplots verticais com compartilhamento do eixo X
    fig, axs = plt.subplots(3, 1, figsize=(10.5, 6.0), sharex=True)
    
    # 2. Desenha os estados por fase em subplots dedicados
    for i, (fase, ax) in enumerate(zip(cfg.fases, axs)):
        cor_fase = cfg.cores[fase]
        
        # Sombreado de risco sem cross-blocking no fundo do subplot
        if cross_necessario:
            ax.fill_between(
                tempo,
                -0.1,
                1.2,
                where=risco_sem_cross,
                color="red",
                alpha=0.08,
                hatch="//",
                step="post",
            )
            
        # Bloqueio individual por H2 (preenchimento suave + linha cheia)
        bloq = df_restricao[f"Bloqueio_individual_{fase}"].astype(int).to_numpy()
        ax.fill_between(
            tempo,
            0,
            bloq,
            color=cor_fase,
            alpha=0.15,
            step="post",
        )
        ax.step(
            tempo,
            bloq,
            color=cor_fase,
            alpha=0.8,
            where="post",
            linewidth=1.5,
        )
        
        # Trip por característica (BIAS ultrapassado - linha tracejada cinza)
        if f"Trip_Caracteristica_{fase}" in df_restricao.columns:
            trip_caract = df_restricao[f"Trip_Caracteristica_{fase}"].astype(int).to_numpy()
            ax.step(
                tempo,
                trip_caract,
                color="dimgray",
                linestyle="--",
                where="post",
                linewidth=1.2,
            )
            
            # Trip desprotegido (linha vermelha espessa)
            trip_desp = (df_restricao[f"Trip_Caracteristica_{fase}"] & ~df_restricao[f"Bloqueio_individual_{fase}"]).astype(int).to_numpy()
            ax.step(
                tempo,
                trip_desp,
                color="red",
                where="post",
                linewidth=2.2,
            )

        ax.set_ylim(-0.08, 1.08)
        ax.set_yticks([0, 1])
        ax.set_yticklabels(["OFF", "ON"], fontsize=8)
        ax.grid(True, linestyle=":", alpha=0.4)
        ax.set_ylabel(f"Fase {fase.upper()}", fontweight="bold", fontsize=10)

    axs[-1].set_xlabel("Tempo (s)")

    # 3. Criação de legenda limpa e unificada fora da área de plotagem
    import matplotlib.patches as mpatches
    from matplotlib.lines import Line2D
    
    legend_handles = [
        mpatches.Patch(color="gray", alpha=0.2, label="Bloqueio por H2"),
        Line2D([0], [0], color="dimgray", linestyle="--", linewidth=1.2, label="Trip por BIAS"),
        Line2D([0], [0], color="red", linewidth=2.2, label="Trip Desprotegido (Sem H2)"),
    ]
    if cross_necessario:
        legend_handles.append(
            mpatches.Patch(facecolor="red", alpha=0.08, hatch="//", label="Risco sem Cross-blocking")
        )
    
    # Posiciona a legenda à direita da figura
    fig.legend(handles=legend_handles, bbox_to_anchor=(0.83, 0.5), loc="center left", fontsize=8.5, borderaxespad=0.)
    
    # Título dinâmico indicando necessidade do Cross-blocking
    status_cross = "NECESSÁRIO (Evitou Trip Incorreto!)" if cross_necessario else "NÃO NECESSÁRIO"
    cor_titulo = "red" if cross_necessario else "green"
    
    # Ajusta o título principal e o subtítulo no topo da figura
    plt.suptitle(
        f"Necessidade de Cross-blocking: {status_cross}",
        fontsize=13,
        fontweight="bold",
        color=cor_titulo,
        y=0.98
    )
    fig.text(
        0.41, 0.92,
        "Diagnóstico de Bloqueio Cruzado vs Bloqueio Individual por 2ª Harmônica",
        fontsize=9.5,
        style="italic",
        ha="center"
    )
    
    # Ajusta layout deixando espaço para a legenda externa à direita
    fig.tight_layout(rect=[0, 0, 0.82, 0.90])
    _mostrar_se_interativo()


def plotar_caracteristica_restricao(df_diff: pd.DataFrame, cfg: Config) -> None:
    """Plota a curva de restrição diferencial (Idiff x Ibias) e a trajetória real das fases."""
    plt.figure(figsize=(8, 6))

    # Plota a característica teórica do relé
    max_bias = max(
        3.0,
        float(max(df_diff[f"Ibias_pu_{f}"].max() for f in cfg.fases)) * 1.1,
    )
    bias_line = np.linspace(0, max_bias, 500)
    oper_line = obter_limiar_operacao(bias_line, cfg)

    plt.plot(
        bias_line,
        oper_line,
        color="red",
        linestyle="-",
        linewidth=2.5,
        label="Característica de Operação (IED)",
    )
    plt.fill_between(
        bias_line,
        0,
        oper_line,
        color="red",
        alpha=0.05,
        label="Região de Restrição (Sem Trip)",
    )
    plt.fill_between(
        bias_line,
        oper_line,
        max(max_bias * 2, 10.0),
        color="green",
        alpha=0.03,
        label="Região de Operação (Trip)",
    )

    # Plota a trajetória de cada fase
    for fase in cfg.fases:
        ibias = df_diff[f"Ibias_pu_{fase}"].to_numpy()
        idiff = df_diff[f"Idiff_pu_{fase}"].to_numpy()
        cor = cfg.cores[fase]

        # Trajetória contínua tracejada
        plt.plot(ibias, idiff, color=cor, alpha=0.4, linestyle=":", linewidth=1)
        # Pontos de amostragem
        plt.scatter(
            ibias,
            idiff,
            color=cor,
            s=12,
            alpha=0.7,
            label=f"Trajetória Fase {fase.upper()}",
        )

        # Destaca ponto de início (círculo) e fim (X) para ver o sentido do evento
        plt.scatter(
            ibias[0],
            idiff[0],
            color="black",
            edgecolors="black",
            marker="o",
            s=35,
            zorder=5,
        )
        plt.scatter(
            ibias[-1],
            idiff[-1],
            color="black",
            marker="x",
            s=45,
            zorder=5,
        )

    plt.xlim(0, max_bias)
    max_y = max(
        1.5,
        float(max(df_diff[f"Idiff_pu_{f}"].max() for f in cfg.fases)) * 1.1,
    )
    plt.ylim(0, max_y)
    plt.xlabel("Corrente de Restrição - Ibias (pu)")
    plt.ylabel("Corrente Diferencial - Idiff (pu)")
    plt.grid(True, linestyle=":", alpha=0.7)
    plt.legend(loc="upper left")
    plt.title(
        "Característica Diferencial no Plano Operação x Restrição",
        fontsize=12,
        fontweight="bold",
    )
    plt.tight_layout()
    _mostrar_se_interativo()
