"""Estimação fasorial via DFT deslizante de ciclo completo (H1 e H2)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from configs_analise.config import Config

_HARMONICAS = (1, 2)


def _pesos_dft(N: int, harmonica: int) -> tuple[np.ndarray, np.ndarray]:
    """Pesos cosseno/seno para extrair uma harmônica via DFT de um ciclo."""
    fase = harmonica * 2 * np.pi * np.arange(N) / N
    return (2 / N) * np.cos(fase), (2 / N) * np.sin(fase)


def _canais_dft(fases: list[str]) -> list[str]:
    """Nomes canônicos dos canais (primário e secundário) na ordem da DFT."""
    return [f"I{f}_{lado}" for lado in ("p", "s") for f in fases]


def estimar_fasores(df_sinais: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """DFT deslizante vetorizada para H1 (60 Hz) e H2 (120 Hz).

    O fasor de cada janela é carimbado no **fim da janela** (instante causal):
    a janela que cobre as amostras [k, k+N-1] tem seu resultado gravado em
    k+N-1. É a referência que o relé usa para datar suas decisões — assim a
    reconstrução fica alinhada no tempo com as flags/eventos do registro
    (trip, partida de 2ª harmônica). As bordas **iniciais** sem janela
    completa (primeiras N-1 amostras) ficam preenchidas com zero.

    Colunas de saída: Mag/Ang_{canal}_H{1,2}.
    """
    N = cfg.N
    canais  = _canais_dft(cfg.fases)
    sinais  = df_sinais[canais].to_numpy().T              # (n_canais, K)
    K       = sinais.shape[1]
    janelas = np.lib.stride_tricks.sliding_window_view(sinais, N, axis=1)

    def _fasores_harmonica(h: int) -> np.ndarray:
        cos_k, sin_k = _pesos_dft(N, h)
        fas_val = janelas @ cos_k + 1j * (janelas @ sin_k)  # (n_canais, K-N+1)
        fas = np.zeros((len(canais), K), dtype=complex)
        fas[:, N - 1:] = fas_val   # carimbo no FIM da janela (causal)
        return fas

    fasores = {h: _fasores_harmonica(h) for h in _HARMONICAS}

    saida = {"tempo": df_sinais["tempo"].to_numpy()}
    for i, canal in enumerate(canais):
        for h in _HARMONICAS:
            saida[f"Mag_{canal}_H{h}"] = np.abs(fasores[h][i])
            saida[f"Ang_{canal}_H{h}"] = np.angle(fasores[h][i])
    return pd.DataFrame(saida).round(5)
