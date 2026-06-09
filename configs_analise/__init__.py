import logging

from configs_analise.config import Config
from configs_analise.generator import gerar_sinais, gerar_trifasico
from configs_analise.comtrade import ler_comtrade, carregar_sinais_comtrade
from configs_analise.dft import estimar_fasores
from configs_analise.protection import (
    calcular_diferencial,
    aplicar_restricao_harmonica,
    estimar_corrente_base,
)
from configs_analise.pipeline import (
    executar_simulacao_protecao,
    exportar_resultados,
    apresentar_resultados,
)

# Boa prática de biblioteca: anexa um NullHandler para que nada seja emitido
# até a aplicação configurar o logging (ver analisar_dados.py).
logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = [
    "Config",
    "gerar_sinais",
    "gerar_trifasico",
    "ler_comtrade",
    "carregar_sinais_comtrade",
    "estimar_fasores",
    "calcular_diferencial",
    "aplicar_restricao_harmonica",
    "estimar_corrente_base",
    "executar_simulacao_protecao",
    "exportar_resultados",
    "apresentar_resultados",
]
