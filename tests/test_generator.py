"""Testes da geração analítica de sinais (carga + inrush)."""

import numpy as np
import pytest

from configs_analise import Config
from configs_analise.generator import gerar_trifasico, gerar_sinais


def test_gerar_trifasico_shape_e_amplitude():
    t = np.linspace(0, 1 / 60, 1000)
    x = gerar_trifasico(t, amplitude=5.0, f=60.0)
    assert x.shape == (3, 1000)
    assert np.max(np.abs(x)) == pytest.approx(5.0, rel=1e-2)


def test_gerar_trifasico_defasagem_de_120_graus():
    t = np.array([0.0])
    x = gerar_trifasico(t, amplitude=1.0, f=60.0)
    esperado = [np.sin(0.0), np.sin(-2 * np.pi / 3), np.sin(2 * np.pi / 3)]
    np.testing.assert_allclose(x[:, 0], esperado, atol=1e-12)


def test_gerar_sinais_colunas_e_tamanho():
    cfg = Config()
    df = gerar_sinais(cfg)
    esperadas = {"tempo", "Ia_p", "Ib_p", "Ic_p", "Ia_s", "Ib_s", "Ic_s"}
    assert esperadas.issubset(df.columns)
    assert len(df) == len(cfg.tempo)


def test_secundario_so_tem_carga_e_primario_tem_inrush():
    # O inrush é injetado apenas no primário; o pico do primário deve superar
    # com folga o do secundário (que enxerga só a carga passante).
    cfg = Config()
    df = gerar_sinais(cfg)
    pico_p = df[["Ia_p", "Ib_p", "Ic_p"]].abs().to_numpy().max()
    pico_s = df[["Ia_s", "Ib_s", "Ic_s"]].abs().to_numpy().max()
    assert pico_p > pico_s
