"""Testes da lógica de proteção: slope, diferencial e restrição harmônica."""

import numpy as np
import pandas as pd
import pytest

from configs_analise import Config
from configs_analise.protection import (
    obter_limiar_operacao,
    aplicar_restricao_harmonica,
    calcular_diferencial,
)


# ── Característica de slope (dois declives) ──────────────────────────────────

def test_limiar_operacao_nas_tres_regioes():
    cfg = Config(is1=0.2, is2=2.0, k1=0.3, k2=1.5)
    ibias = np.array([0.1, 1.0, 3.0])
    limiar = obter_limiar_operacao(ibias, cfg)
    esperado = np.array([
        0.2,                                       # <= is1: região plana
        0.2 + 0.3 * (1.0 - 0.2),                   # is1 < ibias <= is2: slope 1
        0.2 + 0.3 * (2.0 - 0.2) + 1.5 * (3.0 - 2.0),  # > is2: slope 2
    ])
    np.testing.assert_allclose(limiar, esperado)


# ── Restrição harmônica (bloqueio por H2/H1) ─────────────────────────────────

def _df_fasores_restricao(cfg: Config, razoes: dict, h1: float = 10.0):
    n = 4
    dados = {"tempo": np.linspace(0, 1, n)}
    for fase in cfg.fases:
        r = razoes[fase]
        for lado in ("p", "s"):
            dados[f"Mag_I{fase}_{lado}_H1"] = np.full(n, h1)
            dados[f"Mag_I{fase}_{lado}_H2"] = np.full(n, h1 * r)
            dados[f"Ang_I{fase}_{lado}_H1"] = np.zeros(n)
            dados[f"Ang_I{fase}_{lado}_H2"] = np.zeros(n)
    return pd.DataFrame(dados)


def _df_diff_com_trip(cfg: Config, n: int = 4):
    dados = {"tempo": np.linspace(0, 1, n)}
    for fase in cfg.fases:
        dados[f"Idiff_{fase}"] = np.full(n, 5.0)
        dados[f"Trip_Caracteristica_{fase}"] = np.full(n, True)
    return pd.DataFrame(dados)


def test_restricao_bloqueia_apenas_fase_com_inrush():
    cfg = Config(limite_bloqueio_h2=0.15, cross_blocking=False)
    razoes = {"a": 0.30, "b": 0.05, "c": 0.05}  # só A acima do limite
    out = aplicar_restricao_harmonica(
        _df_fasores_restricao(cfg, razoes), _df_diff_com_trip(cfg), cfg
    )
    assert out["Bloqueio_a"].all()
    assert not out["Bloqueio_b"].any()
    # Fase bloqueada zera a corrente de operação; fase livre a preserva.
    assert (out["Idiff_Operacao_a"] == 0).all()
    assert (out["Idiff_Operacao_b"] == 5.0).all()
    # Trip efetivo = quer disparar por slope E não está bloqueado.
    assert not out["Trip_Efetivo_a"].any()
    assert out["Trip_Efetivo_b"].all()


def test_cross_blocking_propaga_para_todas_as_fases():
    cfg = Config(limite_bloqueio_h2=0.15, cross_blocking=True)
    razoes = {"a": 0.30, "b": 0.05, "c": 0.05}
    out = aplicar_restricao_harmonica(
        _df_fasores_restricao(cfg, razoes), _df_diff_com_trip(cfg), cfg
    )
    for fase in cfg.fases:
        assert out[f"Bloqueio_{fase}"].all()
    # O bloqueio individual (registro real, sem cross) continua isolado.
    assert not out["Bloqueio_individual_b"].any()


def test_lado_h2h1_invalido_levanta_erro():
    cfg = Config(lado_h2h1="errado")
    vazio = pd.DataFrame({"tempo": [0.0]})
    with pytest.raises(ValueError):
        aplicar_restricao_harmonica(vazio, vazio, cfg)


# ── Corrente diferencial ─────────────────────────────────────────────────────

def _df_fasores_calc(cfg: Config, mag_p: float, mag_s: float, n: int = 4):
    dados = {"tempo": np.linspace(0, 1, n)}
    for fase in cfg.fases:
        dados[f"Mag_I{fase}_p_H1"] = np.full(n, mag_p)
        dados[f"Ang_I{fase}_p_H1"] = np.zeros(n)
        dados[f"Mag_I{fase}_s_H1"] = np.full(n, mag_s)
        dados[f"Ang_I{fase}_s_H1"] = np.zeros(n)
    return pd.DataFrame(dados)


def test_diferencial_nulo_sem_corrente():
    cfg = Config()
    out = calcular_diferencial(_df_fasores_calc(cfg, 0.0, 0.0), cfg)
    for fase in cfg.fases:
        assert (out[f"Idiff_{fase}"] == 0).all()
        assert not out[f"Trip_Caracteristica_{fase}"].any()


def test_diferencial_nao_nulo_com_corrente_so_no_primario():
    # Secundário aberto (falta interna) -> diferencial deve ser não nula.
    cfg = Config()  # M_p = I, M_s = Yd
    out = calcular_diferencial(_df_fasores_calc(cfg, mag_p=10.0, mag_s=0.0), cfg)
    for fase in cfg.fases:
        assert (out[f"Idiff_{fase}"] > 0).all()
    assert {"Idiff_pu_a", "Ibias_pu_a", "Idiff_Limiar_pu_a"}.issubset(out.columns)
