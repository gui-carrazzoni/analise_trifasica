import numpy as np
import pandas as pd
from configs_analise.config import Config

def gerar_trifasico(
    t: np.ndarray, amplitude: float, f: float, defasagem: float = 0.0
) -> np.ndarray:
    """Gera 3 sinais senoidais defasados em 120° → shape (3, len(t))."""
    omega = 2 * np.pi * f
    fases_120 = np.array([0.0, -2 * np.pi / 3, +2 * np.pi / 3])[:, None]
    return amplitude * np.sin(omega * t + defasagem + fases_120)


def _componente_inrush(t: np.ndarray, cfg: Config) -> np.ndarray:
    """Composição completa do inrush: fundamental + H2 + DC decadente."""
    fundamental = gerar_trifasico(t, cfg.amplitude_inrush, cfg.frequencia, 0.0)
    h2          = gerar_trifasico(t, cfg.amplitude_inrush * cfg.h2_percent,
                                  cfg.frequencia * 2, 0.0)
    dc          = cfg.amplitude_inrush * np.tile(np.exp(-t / cfg.tau_dc), (3, 1))
    return fundamental + h2 + dc


def gerar_sinais(cfg: Config) -> pd.DataFrame:
    """Simula Cold Load Pickup: carga passante + inrush no primário.

    A corrente de carga cancela-se no diferencial (através-corrente), de modo
    que o relé enxerga apenas as componentes de magnetização do núcleo.
    """
    t = cfg.tempo
    I_carga_p = gerar_trifasico(t, cfg.amplitude_carga, cfg.frequencia, 0.0)
    I_carga_s = gerar_trifasico(t, cfg.amplitude_carga, cfg.frequencia,
                                cfg.defasagem_secundario)

    correntes_por_lado = {
        "p": I_carga_p + _componente_inrush(t, cfg),
        "s": I_carga_s,  # secundário não enxerga a magnetização
    }

    colunas = {"tempo": t}
    colunas.update({
        f"I{fase}_{lado}": matriz[i]
        for lado, matriz in correntes_por_lado.items()
        for i, fase in enumerate(cfg.fases)
    })
    return pd.DataFrame(colunas).round(5)
