"""Testes da Config: derivação de matrizes Y-Δ e propriedades de amostragem."""

import numpy as np
import pytest

from configs_analise import Config
from configs_analise.config import _matriz_yd


def test_default_deriva_estrela_no_secundario():
    # Padrão: lado_estrela="secundario", vector_group=1 -> M_p = I, M_s = Yd1.
    cfg = Config()
    np.testing.assert_allclose(cfg.M_p, np.eye(3))
    np.testing.assert_allclose(cfg.M_s, _matriz_yd(1))


def test_estrela_no_primario_inverte_matrizes():
    cfg = Config(lado_estrela="primario")
    np.testing.assert_allclose(cfg.M_p, _matriz_yd(1))
    np.testing.assert_allclose(cfg.M_s, np.eye(3))


def test_vector_group_11_usa_matriz_yd11():
    cfg = Config(vector_group=11)
    np.testing.assert_allclose(cfg.M_s, _matriz_yd(11))


def test_matrizes_explicitas_nao_sao_sobrescritas():
    m = np.full((3, 3), 7.0)
    cfg = Config(M_p=m, M_s=m)
    np.testing.assert_allclose(cfg.M_p, m)
    np.testing.assert_allclose(cfg.M_s, m)


def test_vector_group_invalido_levanta_erro():
    with pytest.raises(ValueError):
        Config(vector_group=5)


def test_lado_estrela_invalido_levanta_erro():
    with pytest.raises(ValueError):
        Config(lado_estrela="terciario")


def test_propriedades_de_amostragem():
    cfg = Config(frequencia=60.0, amostras_por_ciclo=64, ciclos=8)
    assert cfg.N == 64
    assert cfg.dt == pytest.approx(1 / (60.0 * 64))
    assert cfg.tempo[0] == 0.0
    assert cfg.tempo[1] - cfg.tempo[0] == pytest.approx(cfg.dt)


def test_matriz_yd_retorna_copia_independente():
    a = _matriz_yd(1)
    a[0, 0] = 999.0
    assert _matriz_yd(1)[0, 0] != 999.0
