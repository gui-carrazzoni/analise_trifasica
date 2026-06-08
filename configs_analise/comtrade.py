"""Leitor de oscilografias COMTRADE (ASCII/BINARY) e detecção automática de canais."""

from __future__ import annotations

import logging
import re
import struct
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from configs_analise.config import Config

logger = logging.getLogger(__name__)

# Padrões (um por fase) para reconhecer a fase de um canal pelo seu nome.
_PADROES_FASE = {
    fase.upper(): re.compile(
        rf"\bi{fase}\b|\bi_{fase}\b|\bi\.{fase}\b|\bi\s+{fase}\b"
        rf"|\bcurrent\s+i{fase}\b|\bcurrent\s+i_{fase}\b|i{fase}\."
    )
    for fase in ("a", "b", "c")
}


def _fase_do_canal(nome: str) -> str | None:
    """Retorna 'A', 'B' ou 'C' se o nome indicar uma fase de corrente; senão None."""
    nome_lower = nome.lower()
    for fase, padrao in _PADROES_FASE.items():
        if padrao.search(nome_lower):
            return fase
    return None


def _localizar_dat(cfg_path: Path) -> Path:
    """Encontra o arquivo de dados correspondente (.DAT ou .Comtrade.Session)."""
    # Testa as extensões padrão substituindo o sufixo direto
    for sufixo in (".DAT", ".dat", ".Comtrade.Session", ".comtrade.session"):
        candidato = cfg_path.with_suffix(sufixo)
        if candidato.exists():
            return candidato

    # Se não achar por sufixo direto, varre a pasta ignorando maiúsculas/minúsculas
    pasta_pai = cfg_path.parent
    nome_base = cfg_path.stem.lower()
    for arquivo in pasta_pai.iterdir():
        nome_atual = arquivo.name.lower()
        if nome_atual.startswith(nome_base) and any(ext in nome_atual for ext in ("dat", "session")):
            return arquivo

    raise FileNotFoundError(
        f"Arquivo de dados correspondente a {cfg_path.name} não encontrado na pasta."
    )


def _parse_cabecalho_comtrade(linhas: list[str]) -> dict:
    """Extrai metadados e descrição de canais de um .CFG COMTRADE (ASCII ou BINARY)."""
    station, rec_id, *_ = linhas[0].split(",")
    _, nA_s, nD_s = linhas[1].split(",")
    nA = int(nA_s.rstrip("Aa "))
    nD = int(nD_s.rstrip("Dd "))

    canais_a = [
        {
            "nome":    partes[1].strip(),
            "unidade": partes[4].strip(),
            "a":       float(partes[5]),
            "b":       float(partes[6]),
        }
        for partes in (linhas[2 + i].split(",") for i in range(nA))
    ]
    canais_d = [
        {"nome": linhas[2 + nA + i].split(",")[1].strip()}
        for i in range(nD)
    ]

    idx = 2 + nA + nD
    freq_linha = float(linhas[idx]); idx += 1
    nrates     = int(linhas[idx]);   idx += 1
    idx += max(nrates, 1)
    inicio_ts  = linhas[idx].strip(); idx += 1
    trigger_ts = linhas[idx].strip(); idx += 1
    formato    = linhas[idx].strip().upper()  # "ASCII" ou "BINARY"

    if formato not in ("ASCII", "BINARY"):
        raise NotImplementedError(
            f"Loader suporta COMTRADE ASCII e BINARY (recebeu {formato!r})."
        )

    return {
        "station":    station.strip(),
        "rec_id":     rec_id.strip(),
        "canais_a":   canais_a,
        "canais_d":   canais_d,
        "freq_linha": freq_linha,
        "inicio_ts":  inicio_ts,
        "trigger_ts": trigger_ts,
        "formato":    formato,
    }


def _ler_dados_ascii(dat_path: Path, n_cols: int) -> np.ndarray:
    """Lê o .DAT em ASCII, descartando linhas vazias e EOF DOS (0x1A)."""
    linhas_validas: list[str] = []
    with open(dat_path, encoding="latin-1") as f:
        for ln in f:
            ln = ln.strip().rstrip("\x1a").strip()
            if not ln or ln.count(",") + 1 < n_cols:
                continue
            linhas_validas.append(ln)
    raw = np.array([
        [float(v) for v in ln.split(",")[:n_cols]]
        for ln in linhas_validas
    ])
    return raw.reshape(1, -1) if raw.ndim == 1 else raw


def _ler_dados_binary(dat_path: Path, nA: int, nD: int) -> np.ndarray:
    """Lê o .DAT em formato BINARY (COMTRADE IEEE C37.111-1999).

    Estrutura de cada amostra:
      • n       : uint32  (número sequencial da amostra)
      • t_stamp : uint32  (timestamp em microsegundos)
      • nA vals : int16   (um por canal analógico)
      • nD_words: uint16  (ceil(nD/16) palavras de 16 bits para digitais)
    """
    nD_words = (nD + 15) // 16
    rec_size  = 8 + 2 * nA + 2 * nD_words  # bytes por amostra

    with open(dat_path, "rb") as f:
        raw_bytes = f.read()

    n_samples = len(raw_bytes) // rec_size
    if n_samples == 0:
        raise ValueError("Arquivo .DAT binário vazio ou tamanho de registro incompatível.")

    rows = []
    offset = 0
    for _ in range(n_samples):
        if offset + rec_size > len(raw_bytes):
            break
        n_seq   = struct.unpack_from("<I", raw_bytes, offset)[0];     offset += 4
        t_us    = struct.unpack_from("<I", raw_bytes, offset)[0];     offset += 4
        analogs = struct.unpack_from(f"<{nA}h", raw_bytes, offset);   offset += 2 * nA
        dig_raw = struct.unpack_from(f"<{nD_words}H", raw_bytes, offset)
        offset += 2 * nD_words

        bits = []
        for word in dig_raw:
            for bit_pos in range(16):
                bits.append((word >> bit_pos) & 1)
        bits = bits[:nD]

        rows.append([n_seq, t_us] + list(analogs) + bits)

    return np.array(rows, dtype=float)


def ler_comtrade(caminho_cfg: Path) -> tuple[pd.DataFrame, dict]:
    """Lê par .CFG/.DAT (COMTRADE 1999, ASCII ou BINARY) e devolve (df_canais, meta).

    df_canais: DataFrame com coluna 'tempo' (s) e uma coluna por canal
               (analógicos já convertidos em unidade física + digitais).
    meta: frequência da linha, amostras_por_ciclo, timestamps, etc.
    """
    cfg_path = Path(caminho_cfg)
    dat_path = _localizar_dat(cfg_path)
    linhas   = cfg_path.read_text(encoding="latin-1").splitlines()
    hdr      = _parse_cabecalho_comtrade(linhas)
    canais_a, canais_d = hdr["canais_a"], hdr["canais_d"]
    nA, nD   = len(canais_a), len(canais_d)
    formato  = hdr["formato"]

    if formato == "BINARY":
        logger.info("   ↳ Formato BINARY detectado — usando leitor binário.")
        raw = _ler_dados_binary(dat_path, nA, nD)
    else:
        n_cols = 2 + nA + nD
        raw    = _ler_dados_ascii(dat_path, n_cols)

    t = raw[:, 1] * 1e-6  # microsegundos → segundos

    dados: dict = {"tempo": t}
    for i, c in enumerate(canais_a):
        dados[c["nome"]] = raw[:, 2 + i] * c["a"] + c["b"]
    for i, c in enumerate(canais_d):
        dados[c["nome"]] = raw[:, 2 + nA + i].astype(int)
    df = pd.DataFrame(dados)

    dt = float(t[1] - t[0]) if len(t) >= 2 else None
    n_ciclo = int(round(1.0 / (hdr["freq_linha"] * dt))) if dt else None
    meta = {
        "estacao":            hdr["station"],
        "rec_id":             hdr["rec_id"],
        "freq_linha":         hdr["freq_linha"],
        "n_amostras":         len(t),
        "dt":                 dt,
        "amostras_por_ciclo": n_ciclo,
        "inicio":             hdr["inicio_ts"],
        "trigger":            hdr["trigger_ts"],
        "formato":            formato,
        "canais_analog":      [c["nome"] for c in canais_a],
        "canais_digitais":    [c["nome"] for c in canais_d],
        "unidades":           {c["nome"]: c["unidade"] for c in canais_a},
    }
    return df, meta


def auto_detect_channels(
    channel_names: list[str]
) -> tuple[tuple[str, str, str] | None, tuple[str, str, str] | None, tuple[str, str, str] | None]:
    """Descobre heuristicamente os canais de correntes para as fases A, B e C.

    Agrupa em Primário (W1) e Secundário (W2), bem como canal diferencial.
    """
    phase_channels = []
    diff_channels = []

    for name in channel_names:
        name_lower = name.lower()
        if any(x in name_lower for x in ("diff", "oper", "bias", "rest")):
            diff_channels.append(name)
            continue

        # Correntes de fase: IA, IB, IC, Ia, Ib, Ic, "Current IA", etc.
        phase = _fase_do_canal(name)
        if phase:
            phase_channels.append((name, phase))

    lado1 = []
    lado2 = []

    for name, phase in phase_channels:
        name_lower = name.lower()
        # Indicadores óbvios de enrolamento primário/lado 1
        if any(x in name_lower for x in (".a", "-1", "_1", "_p", "_w1", ".1", "_l1")):
            lado1.append((name, phase))
        # Indicadores óbvios de enrolamento secundário/lado 2
        elif any(x in name_lower for x in (".b", "-2", "_2", "_s", "_w2", ".2", "_l2")):
            lado2.append((name, phase))

    # Se a divisão óbvia falhar, divide por ordem de aparecimento: a primeira
    # ocorrência de cada fase vai para o lado 1, uma eventual repetição vai para o 2.
    if len(lado1) != 3 or len(lado2) != 3:
        grupo1: list[tuple[str, str]] = []
        grupo2: list[tuple[str, str]] = []
        for name, phase in phase_channels:
            if any(g[1] == phase for g in grupo1):
                grupo2.append((name, phase))
            else:
                grupo1.append((name, phase))
        lado1, lado2 = grupo1, grupo2

    def ordenar_abc(grupo):
        dict_grupo = {phase: name for name, phase in grupo}
        if all(f in dict_grupo for f in ('A', 'B', 'C')):
            return (dict_grupo['A'], dict_grupo['B'], dict_grupo['C'])
        return None

    canais_p = ordenar_abc(lado1)
    canais_s = ordenar_abc(lado2)

    diff_abc = {'A': None, 'B': None, 'C': None}
    for name in diff_channels:
        fase = _fase_do_canal(name)
        if fase:
            diff_abc[fase] = name

    if all(diff_abc.values()):
        canais_diff = (diff_abc['A'], diff_abc['B'], diff_abc['C'])
    else:
        if len(diff_channels) == 3:
            canais_diff = tuple(diff_channels)
        else:
            canais_diff = None

    return canais_p, canais_s, canais_diff


_ROTULOS_LADO_CTS = {
    "p": ("Primário (W1)",   "canais_p"),
    "s": ("Secundário (W2)", "canais_s"),
}


def _sanity_check_canais(df_sinais: pd.DataFrame, cfg: Config) -> None:
    """Avisa se um dos lados tem corrente praticamente nula.

    Útil para flagrar canais trocados; lado totalmente zerado é OK quando o
    disjuntor oposto está aberto durante energização.
    """
    picos = {
        lado: max(float(df_sinais[f"I{f}_{lado}"].abs().max()) for f in cfg.fases)
        for lado in ("p", "s")
    }
    max_total = max(picos.values())
    if max_total == 0:
        logger.warning("⚠️  AMBOS os lados estão zerados — verifique os nomes dos canais.")
        return
    for lado, pico in picos.items():
        if pico >= 0.05 * max_total:
            continue
        rotulo, attr = _ROTULOS_LADO_CTS[lado]
        canais = getattr(cfg, attr)
        logger.warning(
            f"⚠️  {rotulo} {canais}: pico {pico:.2f} A "
            f"({100 * pico / max_total:.2f}% do outro lado). "
            "Pode ser lado aberto durante energização (OK), ou "
            "canal mal mapeado no Config (verifique placa de CTs)."
        )


def carregar_sinais_comtrade(
    cfg: Config
) -> tuple[pd.DataFrame, pd.DataFrame, dict, Config]:
    """Carrega um caso real e devolve dados no esquema canônico do pipeline.

    Retorna:
      df_sinais    — colunas canônicas (tempo, Ia_p..Ic_p, Ia_s..Ic_s)
      df_extras    — DataFrame bruto do COMTRADE (todos os canais)
      meta         — metadados do registro
      cfg_ajustada — Config com amostras_por_ciclo derivado do arquivo
    """
    if cfg.caminho_comtrade is None:
        raise ValueError("cfg.caminho_comtrade não definido.")

    df_raw, meta = ler_comtrade(cfg.caminho_comtrade)
    canais_disponiveis = meta["canais_analog"]

    # Valida se os canais configurados existem no arquivo COMTRADE
    todos_p_existem = all(c in canais_disponiveis for c in cfg.canais_p)
    todos_s_existem = all(c in canais_disponiveis for c in cfg.canais_s)

    if not (todos_p_existem and todos_s_existem):
        logger.info("ℹ️  Nomes de canais configurados não encontrados. Tentando detecção automática...")
        auto_p, auto_s, auto_diff = auto_detect_channels(canais_disponiveis)

        if auto_p and auto_s and all(auto_p) and all(auto_s):
            logger.info(f"   • Detetado Primário: {auto_p}")
            logger.info(f"   • Detetado Secundário: {auto_s}")
            cfg = replace(
                cfg,
                canais_p=auto_p,
                canais_s=auto_s,
            )
            if auto_diff:
                logger.info(f"   • Detetado Relé Diferencial: {auto_diff}")
                cfg = replace(cfg, canais_diff_rele=auto_diff)
        else:
            raise KeyError(
                f"Canais configurados {cfg.canais_p} ou {cfg.canais_s} não existem no arquivo "
                f"e a detecção automática falhou. Canais disponíveis: {canais_disponiveis}"
            )

    mapa_canonico = {
        **{f"I{fase}_p": canal for fase, canal in zip(cfg.fases, cfg.canais_p)},
        **{f"I{fase}_s": canal for fase, canal in zip(cfg.fases, cfg.canais_s)},
    }
    dados = {"tempo": df_raw["tempo"].to_numpy()}
    dados.update({
        destino: df_raw[origem].to_numpy()
        for destino, origem in mapa_canonico.items()
    })
    df_sinais = pd.DataFrame(dados).round(5)

    cfg_ajustada = replace(
        cfg,
        amostras_por_ciclo=meta["amostras_por_ciclo"],
        frequencia=meta["freq_linha"],
    )
    logger.info(
        f"📥 COMTRADE carregado: {meta['estacao']} | {meta['n_amostras']} amostras "
        f"| dt={meta['dt']*1e6:.1f} µs | {meta['amostras_por_ciclo']} amostras/ciclo"
    )
    _sanity_check_canais(df_sinais, cfg)
    return df_sinais, df_raw, meta, cfg_ajustada
