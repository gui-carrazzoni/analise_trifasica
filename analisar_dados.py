import sys

# Garante saída em UTF-8 no console (Windows usa cp1252 por padrão, que não
# codifica os emojis/símbolos usados nas mensagens de progresso).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import matplotlib
# Configura o matplotlib para rodar em modo "non-interactive" (não abre janelas)
# Isso permite salvar os gráficos como arquivo PNG diretamente, sem travar o loop
matplotlib.use("Agg")

import matplotlib.pyplot as plt
from pathlib import Path
from configs_analise import Config, executar_simulacao_protecao, apresentar_resultados, exportar_resultados

# ==============================================================================
# SCRIPT DE ANÁLISE EM LOTE (VARRE UMA PASTA DE CASOS REAIS)
# ==============================================================================

# 1. Defina a pasta onde estão as suas oscilografias (.cfg e .dat)
PASTA_ENTRADA = Path("./casos_reais")
PASTA_SAIDA = Path("./resultados_lote")

# 2. Configurações gerais do Transformador e Placa dos TCs
CONFIG_PADRAO = {
    # Mapeamento dos canais analógicos que aparecem nas suas oscilografias
    "canais_p": ("IA-1", "IB-1", "IC-1"),  # Correntes do Primário
    "canais_s": ("IA-2", "IB-2", "IC-2"),  # Correntes do Secundário
    "canais_diff_rele": ("IA-DIFF", "IB-DIFF", "IC-DIFF"),
    
    # Parâmetros físicos do Transformador
    "vector_group": 1,            # 1 para Yd1 ou 11 para Yd11
    "lado_estrela": "secundario", # "primario" ou "secundario"
    
    # Lógica do relé
    "cross_blocking": True,
    "lado_h2h1": "max",
    "limite_bloqueio_h2": 0.15,
}

# Nomes amigáveis para cada figura gerada (na ordem em que o pipeline as cria).
NOMES_GRAFICOS = {
    1: "01_sinais_e_fasores.png",
    2: "02_corrente_diferencial.png",
    3: "03_caracteristica_restricao.png",
    4: "04_restricao_harmonica.png",
    5: "05_diagnostico_crossblocking.png",
    6: "06_validacao_rele.png",
}

def processar_lote():
    if not PASTA_ENTRADA.exists():
        PASTA_ENTRADA.mkdir(parents=True, exist_ok=True)
        print(f"📁 Pasta de entrada '{PASTA_ENTRADA}' criada.")
        print("   Por favor, coloque seus arquivos .cfg e .dat nela e execute novamente.")
        return

    # Busca todos os arquivos .cfg e .CFG na pasta, garantindo caminhos únicos (Windows é case-insensitive)
    arquivos_cfg = sorted(list({p.resolve() for p in (list(PASTA_ENTRADA.glob("*.cfg")) + list(PASTA_ENTRADA.glob("*.CFG")))}))
    
    if not arquivos_cfg:
        print(f"⚠️  Nenhum arquivo .cfg ou .CFG encontrado em '{PASTA_ENTRADA}'.")
        return

    print(f"🚀 Iniciando análise em lote de {len(arquivos_cfg)} caso(s)...")
    PASTA_SAIDA.mkdir(parents=True, exist_ok=True)

    for i, cfg_path in enumerate(arquivos_cfg, 1):
        nome_caso = cfg_path.stem
        print(f"\n[Caso {i}/{len(arquivos_cfg)}] Processando: {nome_caso}...")
        
        # Cria pasta específica de saída para esse caso
        pasta_caso_saida = PASTA_SAIDA / nome_caso
        pasta_caso_saida.mkdir(parents=True, exist_ok=True)
        
        # Cria a configuração específica para este arquivo COMTRADE
        cfg = Config(
            fonte="comtrade",
            caminho_comtrade=cfg_path,
            pasta=pasta_caso_saida,
            **CONFIG_PADRAO
        )
        
        try:
            # 1. Executa o pipeline puro
            resultados, cfg_efetivo, meta, df_raw = executar_simulacao_protecao(cfg)
            
            # 2. Exporta os resultados calculados para CSV na pasta do caso
            exportar_resultados(resultados, cfg_efetivo)
            
            # 3. Gera os gráficos e salva como imagem PNG (sem abrir janela)
            apresentar_resultados(resultados, cfg_efetivo, df_raw=df_raw)
            
            # Como usamos o backend 'Agg', salvamos as figuras geradas em disco
            for fig_num in plt.get_fignums():
                fig = plt.figure(fig_num)
                nome_grafico = NOMES_GRAFICOS.get(fig_num, f"grafico_{fig_num}.png")
                fig.savefig(pasta_caso_saida / nome_grafico, dpi=150, bbox_inches="tight")
            
            # Limpa as figuras da memória para o próximo caso
            plt.close("all")
            
            print(f"   ✅ Sucesso! Resultados e gráficos salvos em: {pasta_caso_saida}")
            
        except Exception as e:
            print(f"   ❌ Erro ao processar caso {nome_caso}: {e}")
            plt.close("all")

if __name__ == "__main__":
    processar_lote()
