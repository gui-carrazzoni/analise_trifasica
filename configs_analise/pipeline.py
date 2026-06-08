"""Orquestração do fluxo: sinais → fasores → diferencial → restrição → saída."""

from __future__ import annotations

import pandas as pd

from configs_analise.config import Config
from configs_analise.generator import gerar_sinais
from configs_analise.comtrade import carregar_sinais_comtrade
from configs_analise.dft import estimar_fasores
from configs_analise.protection import (
    calcular_diferencial,
    aplicar_restricao_harmonica,
)
from configs_analise.visualization import (
    plotar_sinais_e_fasores,
    plotar_diferencial,
    plotar_restricao_harmonica,
    plotar_diagnostico_cross_blocking,
    plotar_validacao_rele,
    plotar_caracteristica_restricao,
)

ResultadoPipeline = dict[str, pd.DataFrame]


def _carregar_sinais(
    cfg: Config,
) -> tuple[pd.DataFrame, Config, dict | None, pd.DataFrame | None]:
    """Roteia entre fonte simulada e COMTRADE — devolve sinais e cfg ajustado."""
    if cfg.fonte == "comtrade":
        print("▶️  1/4 Lendo registro COMTRADE...")
        df_sin, df_raw, meta, cfg = carregar_sinais_comtrade(cfg)
        return df_sin, cfg, meta, df_raw
    print("▶️  1/4 Gerando sinais trifásicos simulados (Cold Load Pickup)...")
    return gerar_sinais(cfg), cfg, None, None


def executar_simulacao_protecao(
    cfg: Config,
) -> tuple[ResultadoPipeline, Config, dict | None, pd.DataFrame | None]:
    """Pipeline puro: sinais → fasores → diferencial → restrição."""
    df_sin, cfg, meta, df_raw = _carregar_sinais(cfg)

    print("▶️  2/4 Estimando fasores H1 e H2 (DFT deslizante)...")
    df_fas = estimar_fasores(df_sin, cfg)

    print("▶️  3/4 Calculando correntes diferenciais (H1)...")
    df_diff = calcular_diferencial(df_fas, cfg, df_raw=df_raw)

    modo_bloqueio = (
        "com cross-blocking" if cfg.cross_blocking else "sem cross-blocking"
    )
    print(
        f"▶️  4/4 Aplicando restrição harmônica "
        f"({modo_bloqueio}, H2/H1 do lado: {cfg.lado_h2h1})..."
    )
    df_restricao = aplicar_restricao_harmonica(df_fas, df_diff, cfg)

    resultados: ResultadoPipeline = {
        "sinais": df_sin,
        "fasores": df_fas,
        "diferencial": df_diff,
        "restricao": df_restricao,
    }
    return resultados, cfg, meta, df_raw


def exportar_resultados(resultados: ResultadoPipeline, cfg: Config) -> None:
    """Persiste todos os DataFrames em CSV."""
    cfg.pasta.mkdir(parents=True, exist_ok=True)
    arquivos = {
        "sinais": cfg.arq_sinais,
        "fasores": cfg.arq_fasores,
        "diferencial": cfg.arq_diff,
        "restricao": cfg.arq_restricao,
    }
    for chave, nome in arquivos.items():
        resultados[chave].to_csv(cfg.pasta / nome, index=False)
    print("✅ Resultados exportados para CSV com sucesso.")


def apresentar_resultados(
    resultados: ResultadoPipeline,
    cfg: Config,
    df_raw: pd.DataFrame | None = None,
) -> None:
    """Renderiza todos os gráficos do pipeline."""
    plotar_sinais_e_fasores(
        resultados["sinais"], resultados["fasores"], cfg
    )
    plotar_diferencial(resultados["diferencial"], cfg)
    
    # Plota a característica do plano Idiff x Ibias
    plotar_caracteristica_restricao(resultados["diferencial"], cfg)
    
    plotar_restricao_harmonica(resultados["restricao"], cfg)
    plotar_diagnostico_cross_blocking(resultados["restricao"], cfg)
    if df_raw is not None:
        plotar_validacao_rele(
            resultados["diferencial"],
            resultados["fasores"],
            df_raw,
            cfg,
        )
