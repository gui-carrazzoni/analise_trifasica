import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import os
import shutil
import base64
import io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, RedirectResponse
import uvicorn

from configs_analise import Config, executar_simulacao_protecao, apresentar_resultados

# Nomes para os gráficos gerados
NOMES_GRAFICOS = {
    1: "01 - Sinais e Fasores",
    2: "02 - Corrente Diferencial",
    3: "03 - Característica de Restrição",
    4: "04 - Restrição Harmônica",
    5: "05 - Diagnóstico de Bloqueio Cruzado (Cross-Blocking)",
    6: "06 - Validação do Relé",
}

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
        
        # Gerar os gráficos (fica na memória)
        apresentar_resultados(resultados, cfg_efetivo, df_raw=df_raw)
        
        # Extrair gráficos da memória para base64
        images = []
        for fig_num in plt.get_fignums():
            fig = plt.figure(fig_num)
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
            buf.seek(0)
            img_b64 = base64.b64encode(buf.read()).decode("utf-8")
            
            nome_grafico = NOMES_GRAFICOS.get(fig_num, f"Gráfico {fig_num}")
            images.append({
                "name": nome_grafico,
                "data": f"data:image/png;base64,{img_b64}"
            })
            
        plt.close("all")
        
        return JSONResponse(content={"status": "success", "images": images})

    except Exception as e:
        plt.close("all")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Limpeza
        if 'cfg_path' in locals() and cfg_path.exists():
            cfg_path.unlink()
        if 'dat_path' in locals() and dat_path.exists():
            dat_path.unlink()

if __name__ == "__main__":
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
