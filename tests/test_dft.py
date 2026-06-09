"""Testes da DFT deslizante de ciclo completo (estimação fasorial H1/H2)."""

import numpy as np
import pandas as pd

from configs_analise import Config
from configs_analise.dft import estimar_fasores

_CANAIS = ["Ia_p", "Ib_p", "Ic_p", "Ia_s", "Ib_s", "Ic_s"]


def _df_tom(cfg: Config, canal: str, amplitude: float, harmonica: int = 1):
    """DataFrame com um único canal contendo um tom puro na harmônica dada."""
    t = cfg.tempo
    sinal = amplitude * np.sin(2 * np.pi * cfg.frequencia * harmonica * t)
    dados = {"tempo": t}
    for c in _CANAIS:
        dados[c] = sinal if c == canal else np.zeros_like(t)
    return pd.DataFrame(dados)


def _regiao_valida(cfg: Config) -> slice:
    """Índices com janela de ciclo completo (antes do preenchimento com zero)."""
    return slice(0, len(cfg.tempo) - cfg.N + 1)


def test_dft_recupera_amplitude_da_fundamental():
    cfg = Config()
    A = 7.0
    fas = estimar_fasores(_df_tom(cfg, "Ia_p", A, harmonica=1), cfg)
    mag = fas["Mag_Ia_p_H1"].to_numpy()[_regiao_valida(cfg)]
    np.testing.assert_allclose(mag, A, atol=1e-3)


def test_dft_h2_quase_nulo_para_tom_de_h1():
    cfg = Config()
    fas = estimar_fasores(_df_tom(cfg, "Ia_p", 7.0, harmonica=1), cfg)
    mag_h2 = fas["Mag_Ia_p_H2"].to_numpy()[_regiao_valida(cfg)]
    assert np.max(np.abs(mag_h2)) < 1e-3


def test_dft_isola_segunda_harmonica():
    cfg = Config()
    A = 4.0
    fas = estimar_fasores(_df_tom(cfg, "Ib_s", A, harmonica=2), cfg)
    mag_h2 = fas["Mag_Ib_s_H2"].to_numpy()[_regiao_valida(cfg)]
    np.testing.assert_allclose(mag_h2, A, atol=1e-3)


def test_dft_preenche_borda_final_com_zero():
    cfg = Config()
    fas = estimar_fasores(_df_tom(cfg, "Ia_p", 7.0, harmonica=1), cfg)
    # As últimas N-1 amostras não têm janela completa -> magnitude zerada.
    cauda = fas["Mag_Ia_p_H1"].to_numpy()[len(cfg.tempo) - cfg.N + 1:]
    np.testing.assert_allclose(cauda, 0.0)
