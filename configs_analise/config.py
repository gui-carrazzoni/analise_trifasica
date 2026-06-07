"""Configuração do pipeline e matrizes de compensação Y-Δ (grupos Yd1/Yd11)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

# ── Matrizes de compensação Yd ────────────────────────────────────────────────
# Aplicadas ao lado em estrela (Y) para realinhá-lo com o lado em delta (Δ).
# A escolha entre Yd1 e Yd11 depende do grupo vetorial do transformador (placa).
_M_YD1 = np.array([
    [ 1, -1,  0],
    [ 0,  1, -1],
    [-1,  0,  1],
]) / np.sqrt(3)

_M_YD11 = np.array([
    [ 1,  0, -1],
    [-1,  1,  0],
    [ 0, -1,  1],
]) / np.sqrt(3)

_MATRIZES_YD = {1: _M_YD1, 11: _M_YD11}


def _matriz_yd(vector_group: int) -> np.ndarray:
    """Retorna a matriz Yd para o grupo vetorial informado (1 ou 11)."""
    if vector_group not in _MATRIZES_YD:
        raise ValueError(f"vector_group {vector_group} não suportado (use 1 ou 11).")
    return _MATRIZES_YD[vector_group].copy()


@dataclass(frozen=True)
class Config:
    """Parâmetros do pipeline de análise trifásica."""

    # ── Fonte dos dados ──────────────────────────────────────
    fonte: str = "simulada"                       # "simulada" | "comtrade"
    caminho_comtrade: Path | None = None
    canais_p:         tuple[str, str, str] = ("IA-1", "IB-1", "IC-1")
    canais_s:         tuple[str, str, str] = ("IA-2", "IB-2", "IC-2")
    canais_diff_rele: tuple[str, str, str] = ("IA-DIFF", "IB-DIFF", "IC-DIFF")

    # ── Sinal (modo simulado) ───────────────────────────────
    frequencia:         float = 60.0
    amostras_por_ciclo: int   = 64
    ciclos:             int   = 8
    amplitude_carga:    float = 1.0

    # ── Parâmetros de Inrush (modo simulado) ─────────────────
    amplitude_inrush: float = 8.0
    tau_dc:           float = 0.05
    h2_percent:       float = 0.20

    # ── Defasagem física do secundário (modo simulado) ──────
    defasagem_secundario: float = -np.pi / 6 + np.pi

    # ── Configuração do transformador ───────────────────────
    vector_group: int = 1                          # 1 ou 11
    lado_estrela: str = "secundario"               # "primario" | "secundario"

    # ── Compensação Y-Δ (derivada de vector_group/lado_estrela) ─────────────
    # Quando ambos forem None, __post_init__ deriva automaticamente.
    M_p: np.ndarray | None = None
    M_s: np.ndarray | None = None

    # ── Correntes de base (TAP por enrolamento) ──────────────
    # Em A no secundário do TC, conforme ajuste do relé. Se ambos None,
    tap_p_a_por_pu: float | None = None
    tap_s_a_por_pu: float | None = None

    # ── Proteção (Relé) ──────────────────────────────────────
    limite_bloqueio_h2: float = 0.15
    cross_blocking:     bool  = False
    lado_h2h1:          str   = "max"              # "primario" | "secundario" | "max"

    # ── Característica de Restrição (BIAS / Slope) ───────────
    is1:                float = 0.2                # Limiar mínimo de operação Idmin (pu)
    is2:                float = 2.0                # Limiar de transição de slope (pu)
    k1:                 float = 0.3                # Inclinação / Slope 1 (30%)
    k2:                 float = 1.5                # Inclinação / Slope 2 (150%)

    # ── UI ───────────────────────────────────────────────────
    fases: list[str] = field(default_factory=lambda: ["a", "b", "c"])
    cores: dict[str, str] = field(default_factory=lambda: {
        "a": "blue", "b": "green", "c": "orange",
    })

    # ── I/O ──────────────────────────────────────────────────
    pasta:         Path = Path(".")
    arq_sinais:    str  = "sinais_corrente.csv"
    arq_fasores:   str  = "fasores.csv"
    arq_diff:      str  = "correntes_diferenciais.csv"
    arq_restricao: str  = "logica_restricao.csv"

    def __post_init__(self) -> None:
        if self.M_p is not None and self.M_s is not None:
            return

        matriz_yd = _matriz_yd(self.vector_group)
        identidade = np.eye(3)
        mapa_estrela = {
            "primario":   (matriz_yd, identidade),
            "secundario": (identidade, matriz_yd),
        }
        if self.lado_estrela not in mapa_estrela:
            raise ValueError(
                f"lado_estrela inválido: {self.lado_estrela!r} "
                "(use 'primario' ou 'secundario')")
        m_p, m_s = mapa_estrela[self.lado_estrela]
        if self.M_p is None:
            object.__setattr__(self, "M_p", m_p)
        if self.M_s is None:
            object.__setattr__(self, "M_s", m_s)

    @staticmethod
    def M_YD(vector_group: int = 1) -> np.ndarray:
        """Matriz de compensação Y→Δ-equivalente (Yd1 por padrão)."""
        return _matriz_yd(vector_group)

    @property
    def N(self) -> int:
        return self.amostras_por_ciclo

    @property
    def dt(self) -> float:
        return 1 / (self.frequencia * self.amostras_por_ciclo)

    @property
    def tempo(self) -> np.ndarray:
        return np.arange(0, self.ciclos / self.frequencia, self.dt)
