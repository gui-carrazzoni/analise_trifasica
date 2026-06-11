import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import os
import shutil
import numpy as np
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, RedirectResponse
import uvicorn

from configs_analise import Config, executar_simulacao_protecao
from configs_analise.protection import (
    obter_taps_efetivos,
    estimar_taps_por_enrolamento,
    obter_limiar_operacao,
    _canais_diff_disponiveis,
)

# Rótulo amigável das fases internas ("a"/"b"/"c" -> "A"/"B"/"C")
_FASE_LABEL = {"a": "A", "b": "B", "c": "C"}

# Paleta por fase alinhada ao tema escuro do site (style.css).
_CORES_FASE = {"a": "#2f81f7", "b": "#3fb950", "c": "#d29922"}


def montar_resumo(resultados, cfg, df_raw):
    """Extrai veredito global + métricas por fase dos DataFrames do pipeline.

    Não recalcula nada: lê as colunas que o pipeline já produziu
    (diferencial + restrição) e condensa no ponto de maior Idiff de cada fase.
    """
    df_diff = resultados["diferencial"]
    df_restr = resultados["restricao"]
    df_fas = resultados["fasores"]

    tap_p, tap_s = obter_taps_efetivos(df_fas, df_raw, cfg)

    # Origem dos TAPs: manual (ambos informados) ou estimado por enrolamento.
    tap_manual = cfg.tap_p_a_por_pu is not None and cfg.tap_s_a_por_pu is not None
    tap_info = {
        "tap_p": round(float(tap_p), 3),
        "tap_s": round(float(tap_s), 3),
        "origem": "manual" if tap_manual else "estimado",
        "p_determinado": True,
        "s_determinado": True,
    }
    if not tap_manual:
        _, _, est_info = estimar_taps_por_enrolamento(df_fas, df_raw, cfg)
        tap_info["p_determinado"] = bool(est_info.get("p_determinado", False))
        tap_info["s_determinado"] = bool(est_info.get("s_determinado", False))

    fases_info = []
    houve_trip = houve_pedido = houve_bloqueio = False

    for fase in cfg.fases:
        idiff_pu = df_diff[f"Idiff_pu_{fase}"].to_numpy()
        idiff_a = df_diff[f"Idiff_{fase}"].to_numpy()
        ibias_pu = df_diff[f"Ibias_pu_{fase}"].to_numpy()
        razao = df_restr[f"Razao_H2_H1_{fase}"].to_numpy()

        # Ponto de operação representativo = instante de maior Idiff (pu)
        idx = int(np.argmax(idiff_pu))

        pediu_trip = bool(df_diff[f"Trip_Caracteristica_{fase}"].to_numpy().any())
        bloqueada = bool(df_restr[f"Bloqueio_{fase}"].to_numpy().any())
        disparou = bool(df_restr[f"Trip_Efetivo_{fase}"].to_numpy().any())

        houve_trip = houve_trip or disparou
        houve_pedido = houve_pedido or pediu_trip
        houve_bloqueio = houve_bloqueio or bloqueada

        if disparou:
            status = "TRIP"
        elif pediu_trip and bloqueada:
            status = "BLOQUEIO"
        else:
            status = "ESTAVEL"

        fases_info.append({
            "fase": _FASE_LABEL.get(fase, fase.upper()),
            "idiff_pu": round(float(idiff_pu[idx]), 3),
            "idiff_a": round(float(idiff_a[idx]), 2),
            "ibias_pu": round(float(ibias_pu[idx]), 3),
            "h2h1_pct": round(float(np.max(razao)) * 100.0, 1),
            "pediu_trip": pediu_trip,
            "bloqueada": bloqueada,
            "disparou": disparou,
            "status": status,
        })

    if houve_trip:
        veredito = {
            "status": "TRIP",
            "label": "TRIP — Operação do 87T",
            "detail": "A corrente diferencial cruzou a característica de "
                      "restrição e não houve bloqueio por 2ª harmônica.",
        }
    elif houve_pedido and houve_bloqueio:
        veredito = {
            "status": "BLOQUEIO",
            "label": "Bloqueio por 2ª Harmônica",
            "detail": "A característica pediu disparo, mas a restrição "
                      "harmônica (inrush) atuou e bloqueou o trip.",
        }
    else:
        veredito = {
            "status": "ESTAVEL",
            "label": "Sem Operação — Estável",
            "detail": "A corrente diferencial permaneceu abaixo da "
                      "característica de restrição durante todo o registro.",
        }

    return {
        "veredito": veredito,
        "fases": fases_info,
        "taps": tap_info,
        "config": {
            "vector_group": cfg.vector_group,
            "lado_estrela": cfg.lado_estrela,
            "limite_h2_pct": round(float(cfg.limite_bloqueio_h2) * 100.0, 1),
            "cross_blocking": bool(cfg.cross_blocking),
            "lado_h2h1": cfg.lado_h2h1,
        },
    }


def _serie(a, casas=4):
    """Converte um array numérico em lista JSON-segura (NaN/inf -> None)."""
    arr = np.asarray(a, dtype=float)
    return [None if not np.isfinite(v) else round(float(v), casas) for v in arr]


def _bits(a):
    """Converte uma série booleana em lista de 0/1 (para gráficos de estado)."""
    return [int(x) for x in np.asarray(a).astype(int)]


def montar_series(resultados, cfg, df_raw):
    """Empacota as séries temporais do pipeline em JSON para gráficos interativos.

    Nada é recalculado além da curva de característica e da escala de validação:
    o front (Plotly) desenha tudo a partir destes vetores, permitindo zoom/pan
    nativos sobre as amostras brutas.
    """
    df_sin = resultados["sinais"]
    df_fas = resultados["fasores"]
    df_diff = resultados["diferencial"]
    df_restr = resultados["restricao"]
    fases = list(cfg.fases)

    # Característica de operação (plano Idiff × Ibias).
    max_bias = max(3.0, float(max(df_diff[f"Ibias_pu_{f}"].max() for f in fases)) * 1.1)
    bias_line = np.linspace(0.0, max_bias, 400)
    oper_line = obter_limiar_operacao(bias_line, cfg)

    out = {
        "fases_key": fases,
        "fases": [_FASE_LABEL.get(f, f.upper()) for f in fases],
        "cores": {f: _CORES_FASE.get(f, "#2f81f7") for f in fases},
        "limite_h2": float(cfg.limite_bloqueio_h2),
        "tempo": _serie(df_diff["tempo"], 5),
        "caracteristica": {
            "bias": _serie(bias_line, 4),
            "oper": _serie(oper_line, 4),
            "max_bias": round(float(max_bias), 3),
        },
        "sinais": {}, "h1mag": {}, "diff": {}, "idiff_pu": {}, "ibias_pu": {},
        "limiar_pu": {}, "razao": {}, "bloqueio_indiv": {}, "trip_caract": {},
        "idiff_operacao": {},
    }

    for f in fases:
        out["sinais"][f] = {"p": _serie(df_sin[f"I{f}_p"], 3), "s": _serie(df_sin[f"I{f}_s"], 3)}
        out["h1mag"][f] = {"p": _serie(df_fas[f"Mag_I{f}_p_H1"], 3), "s": _serie(df_fas[f"Mag_I{f}_s_H1"], 3)}
        out["diff"][f] = _serie(df_diff[f"Idiff_{f}"], 3)
        out["idiff_pu"][f] = _serie(df_diff[f"Idiff_pu_{f}"], 4)
        out["ibias_pu"][f] = _serie(df_diff[f"Ibias_pu_{f}"], 4)
        out["limiar_pu"][f] = _serie(df_diff[f"Idiff_Limiar_pu_{f}"], 4)
        out["razao"][f] = _serie(df_restr[f"Razao_H2_H1_{f}"], 4)
        out["bloqueio_indiv"][f] = _bits(df_restr[f"Bloqueio_individual_{f}"])
        out["trip_caract"][f] = _bits(df_diff[f"Trip_Caracteristica_{f}"])
        out["idiff_operacao"][f] = _serie(df_restr[f"Idiff_Operacao_{f}"], 3)

    # Validação vs registro do relé (só quando os canais *-DIFF existem).
    canais_diff = _canais_diff_disponiveis(df_raw, cfg) if df_raw is not None else []
    if len(canais_diff) == 3:
        _, tap_s = obter_taps_efetivos(df_fas, df_raw, cfg)
        escala = (1.0 / tap_s) if (tap_s and tap_s > 0) else 1.0
        info = (f"TAP {tap_s:.1f} A_sec/pu" if (tap_s and tap_s > 0)
                else "TAP indisponível — escalas distintas")
        val = {"escala": float(escala), "unidade": "pu", "info_tap": info,
               "calc": {}, "rele": {}, "canais": {}}
        for f, canal in zip(fases, canais_diff):
            val["calc"][f] = _serie(df_diff[f"Idiff_{f}"], 3)
            val["rele"][f] = _serie(df_raw[canal], 4)
            val["canais"][f] = canal
        out["validacao"] = val
    else:
        out["validacao"] = None

    return out


app = FastAPI(title="Análise de Proteção Diferencial (87T)")

# Garantir que a pasta static existe
os.makedirs("static", exist_ok=True)

# Montar arquivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def redirect_to_static():
    return RedirectResponse(url="/static/index.html")


@app.post("/api/analisar")
async def analisar_caso(
    vector_group: int = Form(...),
    lado_estrela: str = Form(...),
    tap_mode: str = Form("estimar"),
    tap_p: str | None = Form(None),
    tap_s: str | None = Form(None),
    cfg_file: UploadFile = File(...),
    dat_file: UploadFile = File(...)
):
    scratch_dir = Path("scratch_api")
    scratch_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Salvar arquivos temporariamente
        cfg_path = scratch_dir / cfg_file.filename
        dat_path = scratch_dir / dat_file.filename

        with open(cfg_path, "wb") as buffer:
            shutil.copyfileobj(cfg_file.file, buffer)
        with open(dat_path, "wb") as buffer:
            shutil.copyfileobj(dat_file.file, buffer)

        # Tratar TAP
        tap_p_val = None
        tap_s_val = None
        if tap_mode == "manual":
            if tap_p and tap_p.strip():
                tap_p_val = float(tap_p)
            if tap_s and tap_s.strip():
                tap_s_val = float(tap_s)

        # Instanciar a Configuração
        cfg = Config(
            fonte="comtrade",
            caminho_comtrade=cfg_path,
            vector_group=vector_group,
            lado_estrela=lado_estrela,
            tap_p_a_por_pu=tap_p_val,
            tap_s_a_por_pu=tap_s_val,
            pasta=scratch_dir
        )

        # Executar a simulação
        resultados, cfg_efetivo, meta, df_raw = executar_simulacao_protecao(cfg)

        # Condensar veredito + métricas por fase
        resumo = montar_resumo(resultados, cfg_efetivo, df_raw)

        # Empacotar séries para os gráficos interativos (Plotly no front)
        series = montar_series(resultados, cfg_efetivo, df_raw)

        return JSONResponse(content={
            "status": "success",
            "resumo": resumo,
            "series": series,
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Limpeza
        if 'cfg_path' in locals() and cfg_path.exists():
            cfg_path.unlink()
        if 'dat_path' in locals() and dat_path.exists():
            dat_path.unlink()


if __name__ == "__main__":
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
