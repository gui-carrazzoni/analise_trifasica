"""Teste de integração do pipeline simulado (ponta a ponta)."""

from configs_analise import Config, executar_simulacao_protecao


def test_pipeline_simulado_retorna_todas_as_etapas():
    resultados, cfg_ef, meta, df_raw = executar_simulacao_protecao(Config())
    assert set(resultados) == {"sinais", "fasores", "diferencial", "restricao"}
    # Fonte simulada não tem registro bruto nem metadados de COMTRADE.
    assert meta is None
    assert df_raw is None


def test_pipeline_detecta_inrush_e_bloqueia_o_trip():
    # h2_percent (0.20) acima do limite de bloqueio (0.15): o inrush simulado
    # deve elevar a razão H2/H1 e acionar o bloqueio em algum instante.
    cfg = Config(h2_percent=0.20, limite_bloqueio_h2=0.15)
    resultados, *_ = executar_simulacao_protecao(cfg)
    restricao = resultados["restricao"]

    razao_max = max(restricao[f"Razao_H2_H1_{f}"].max() for f in cfg.fases)
    assert razao_max > cfg.limite_bloqueio_h2

    houve_bloqueio = any(restricao[f"Bloqueio_{f}"].any() for f in cfg.fases)
    assert houve_bloqueio
