"""Compensação Y-Δ, corrente diferencial, característica de slope e restrição H2."""

from __future__ import annotations

import numpy as np
import pandas as pd

from configs_analise.config import Config


def _reconstruir_fasores(
    df: pd.DataFrame, lado: str, cfg: Config, harmonica: int = 1
) -> np.ndarray:
    """Reconstrói fasores complexos (3, K) a partir de magnitude e ângulo."""
    sfx = f"H{harmonica}"
    return np.array([
        df[f"Mag_I{f}_{lado}_{sfx}"].to_numpy()
        * np.exp(1j * df[f"Ang_I{f}_{lado}_{sfx}"].to_numpy())
        for f in cfg.fases
    ])


def obter_taps_efetivos(
    df_fasores: pd.DataFrame | None, df_raw: pd.DataFrame | None, cfg: Config
) -> tuple[float, float]:
    """Retorna os TAPs em Ampères para o primário e secundário (resolvendo fallback)."""
    tap_p = cfg.tap_p_a_por_pu
    tap_s = cfg.tap_s_a_por_pu

    if tap_p is not None and tap_s is not None:
        return tap_p, tap_s

    if cfg.fonte == "comtrade" and df_fasores is not None and df_raw is not None:
        tap_est = estimar_corrente_base(df_fasores, df_raw, cfg)
        if tap_est is None or tap_est <= 0:
            tap_est = 1.0
        return tap_p or tap_est, tap_s or tap_est

    return tap_p or 1.0, tap_s or 1.0


def obter_limiar_operacao(ibias: np.ndarray, cfg: Config) -> np.ndarray:
    """Calcula o limiar de corrente diferencial (Idiff_limiar em pu) pela curva de dois declives (slopes)."""
    is1, is2, k1, k2 = cfg.is1, cfg.is2, cfg.k1, cfg.k2
    limiar = np.zeros_like(ibias)

    cond1 = ibias <= is1
    cond2 = (ibias > is1) & (ibias <= is2)
    cond3 = ibias > is2

    limiar[cond1] = is1
    limiar[cond2] = is1 + k1 * (ibias[cond2] - is1)
    limiar[cond3] = is1 + k1 * (is2 - is1) + k2 * (ibias[cond3] - is2)

    return limiar


def calcular_diferencial(
    df_fasores: pd.DataFrame, cfg: Config, df_raw: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Calcula Idiff (A), Idiff (pu), Ibias (pu), limiar operacional (pu) e flag de trip por slope."""
    I_p = _reconstruir_fasores(df_fasores, "p", cfg, harmonica=1)
    I_s = _reconstruir_fasores(df_fasores, "s", cfg, harmonica=1)

    I_p_comp = cfg.M_p @ I_p
    I_s_comp = cfg.M_s @ I_s
    I_diff = I_p_comp + I_s_comp

    tap_p, tap_s = obter_taps_efetivos(df_fasores, df_raw, cfg)

    # Normaliza em pu para cálculo da característica de restrição
    I_p_pu = I_p_comp / tap_p
    I_s_pu = I_s_comp / tap_s

    saida = {"tempo": df_fasores["tempo"]}
    for i, fase in enumerate(cfg.fases):
        idiff_A = np.abs(I_diff[i])
        ip_fase_pu = np.abs(I_p_pu[i])
        is_fase_pu = np.abs(I_s_pu[i])

        # Idiff_pu = |Ip_pu + Is_pu|
        idiff_pu = np.abs(I_p_pu[i] + I_s_pu[i])
        # Ibias_pu = (|Ip_pu| + |Is_pu|) / 2 (média aritmética típica do MiCOM P645)
        ibias_pu = (ip_fase_pu + is_fase_pu) / 2.0

        limiar_pu = obter_limiar_operacao(ibias_pu, cfg)
        trip_caract = idiff_pu > limiar_pu

        saida[f"Idiff_{fase}"] = idiff_A
        saida[f"Idiff_pu_{fase}"] = idiff_pu
        saida[f"Ibias_pu_{fase}"] = ibias_pu
        saida[f"Idiff_Limiar_pu_{fase}"] = limiar_pu
        saida[f"Trip_Caracteristica_{fase}"] = trip_caract

    return pd.DataFrame(saida).round(5)


# Limiar mínimo de H1 para considerar a razão H2/H1 válida: 5 % do pico,
# com piso fixo. Evita razões espúrias em regiões pré/pós-evento.
_FRACAO_PICO_H1_PARA_PICKUP = 0.05
_PICKUP_H1_MINIMO           = 0.05


def _limiar_h1_pickup(h1_p: np.ndarray, h1_s: np.ndarray) -> float:
    pico = max(float(h1_p.max()), float(h1_s.max()))
    return max(_PICKUP_H1_MINIMO, _FRACAO_PICO_H1_PARA_PICKUP * pico)


# Seletor da razão H2/H1: P645 usa "max" (qualquer lado bloqueia).
_SELETOR_H2H1 = {
    "primario":   lambda r_p, r_s: r_p,
    "secundario": lambda r_p, r_s: r_s,
    "max":        np.maximum,
}


def aplicar_restricao_harmonica(
    df_fasores: pd.DataFrame, df_diff: pd.DataFrame, cfg: Config
) -> pd.DataFrame:
    """Calcula razão H2/H1, sinal de bloqueio, corrente de operação e trip efetivo."""
    if cfg.lado_h2h1 not in _SELETOR_H2H1:
        raise ValueError(f"cfg.lado_h2h1 inválido: {cfg.lado_h2h1!r}")
    seletor = _SELETOR_H2H1[cfg.lado_h2h1]

    razoes:      dict[str, np.ndarray] = {}
    bloqueios:   dict[str, np.ndarray] = {}
    idiff_bruta: dict[str, np.ndarray] = {}

    for fase in cfg.fases:
        h1_p = df_fasores[f"Mag_I{fase}_p_H1"].to_numpy()
        h2_p = df_fasores[f"Mag_I{fase}_p_H2"].to_numpy()
        h1_s = df_fasores[f"Mag_I{fase}_s_H1"].to_numpy()
        h2_s = df_fasores[f"Mag_I{fase}_s_H2"].to_numpy()
        limiar = _limiar_h1_pickup(h1_p, h1_s)

        with np.errstate(invalid="ignore", divide="ignore"):
            r_p = np.where(h1_p > limiar, h2_p / h1_p, 0.0)
            r_s = np.where(h1_s > limiar, h2_s / h1_s, 0.0)

        razoes[fase]      = seletor(r_p, r_s)
        bloqueios[fase]   = razoes[fase] > cfg.limite_bloqueio_h2
        idiff_bruta[fase] = df_diff[f"Idiff_{fase}"].to_numpy()

    if cfg.cross_blocking:
        bloqueio_global = np.logical_or.reduce(list(bloqueios.values()))
        bloqueios_efetivos = {f: bloqueio_global for f in cfg.fases}
    else:
        bloqueios_efetivos = bloqueios

    saida: dict = {"tempo": df_fasores["tempo"]}
    for fase in cfg.fases:
        saida[f"Razao_H2_H1_{fase}"]         = razoes[fase]
        saida[f"Bloqueio_{fase}"]            = bloqueios_efetivos[fase]
        saida[f"Bloqueio_individual_{fase}"] = bloqueios[fase]
        saida[f"Idiff_Operacao_{fase}"]      = np.where(
            bloqueios_efetivos[fase], 0.0, idiff_bruta[fase]
        )

        # Trip Efetivo: quer disparar por slope E não está bloqueado por inrush
        if f"Trip_Caracteristica_{fase}" in df_diff.columns:
            trip_caract = df_diff[f"Trip_Caracteristica_{fase}"].to_numpy()
            saida[f"Trip_Caracteristica_{fase}"] = trip_caract
            saida[f"Trip_Efetivo_{fase}"] = trip_caract & (~bloqueios_efetivos[fase])

    return pd.DataFrame(saida).round(5)


def _canais_diff_disponiveis(df_raw: pd.DataFrame, cfg: Config) -> list[str]:
    return [c for c in cfg.canais_diff_rele if c in df_raw.columns]


def estimar_corrente_base(
    df_fasores: pd.DataFrame, df_raw: pd.DataFrame, cfg: Config
) -> float | None:
    """Estima TAP médio (A_secundário por pu) pela mediana das razões pico-a-pico."""
    canais_diff = _canais_diff_disponiveis(df_raw, cfg)
    if len(canais_diff) != 3:
        return None

    I_p = _reconstruir_fasores(df_fasores, "p", cfg, harmonica=1)
    I_s = _reconstruir_fasores(df_fasores, "s", cfg, harmonica=1)
    idiff_calc = np.abs(cfg.M_p @ I_p + cfg.M_s @ I_s)

    razoes = []
    for i, canal in enumerate(canais_diff):
        pico_rele = float(np.abs(df_raw[canal].to_numpy()).max())
        if pico_rele > 0:
            razoes.append(float(idiff_calc[i].max()) / pico_rele)
    return float(np.median(razoes)) if razoes else None
