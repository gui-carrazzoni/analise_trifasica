import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from configs_analise.config import Config
from configs_analise.protection import (
    _resolver_tap,
    _escala_para_pu,
    _canais_diff_disponiveis,
    obter_limiar_operacao,
)

_ROTULOS_LADO = {"p": "Primário (W1)", "s": "Secundário (W2)"}


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
    if plt.get_backend().lower() != "agg":
        plt.show()


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
    if plt.get_backend().lower() != "agg":
        plt.show()


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
    if plt.get_backend().lower() != "agg":
        plt.show()


def plotar_validacao_rele(
    df_diff: pd.DataFrame,
    df_fasores: pd.DataFrame,
    df_raw: pd.DataFrame,
    cfg: Config,
) -> None:
    """Sobrepõe Idiff calculada (em pu, via TAP) vs Idiff registrada pelo relé."""
    canais_diff = _canais_diff_disponiveis(df_raw, cfg)
    if len(canais_diff) != 3:
        print(
            "ℹ️  Canais de Idiff do relé não disponíveis no .CFG — pulando validação."
        )
        return

    tap, origem = _resolver_tap(df_fasores, df_raw, cfg)
    escala, unidade, rotulo_calc, info_tap = _escala_para_pu(tap, origem)
    print(f"📐 {info_tap}")

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
    if plt.get_backend().lower() != "agg":
        plt.show()


def plotar_diagnostico_cross_blocking(
    df_restricao: pd.DataFrame, cfg: Config
) -> None:
    """Visualiza intervalos em que cada fase está bloqueada individualmente.

    Cenário do caso real: fase A libera antes das outras → motivação do
    cross-blocking.
    """
    if not any(
        f"Bloqueio_individual_{f}" in df_restricao.columns for f in cfg.fases
    ):
        return
    fig, ax = plt.subplots(figsize=(10, 3))
    for i, fase in enumerate(cfg.fases):
        bloq = (
            df_restricao[f"Bloqueio_individual_{fase}"]
            .astype(int)
            .to_numpy()
        )
        ax.fill_between(
            df_restricao["tempo"],
            i,
            i + bloq * 0.8,
            color=cfg.cores[fase],
            alpha=0.6,
            step="post",
            label=f"Bloqueio fase {fase.upper()}",
        )
    ax.set_yticks([0.4, 1.4, 2.4])
    ax.set_yticklabels(["A", "B", "C"])
    ax.set_xlabel("Tempo (s)")
    ax.grid(True, linestyle=":", alpha=0.5)
    ax.legend(loc="upper right")
    ax.set_title(
        "Bloqueio por H2/H1 por fase — janelas onde uma fase libera "
        "antes das outras motivam o cross-blocking",
        fontsize=12,
        fontweight="bold",
    )
    plt.tight_layout()
    if plt.get_backend().lower() != "agg":
        plt.show()


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
    if plt.get_backend().lower() != "agg":
        plt.show()
