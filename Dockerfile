# Imagem de deploy do Analisador 87T (FastAPI + uvicorn).
# Compatível com Hugging Face Spaces (Docker SDK) e Render.
FROM python:3.11-slim

# libgomp1: runtime de threading usado por numpy/pandas em algumas operações.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Hugging Face Spaces roda o container como uid 1000 — criamos esse usuário
# para que os diretórios de trabalho (uploads, cache do matplotlib) sejam graváveis.
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    MPLBACKEND=Agg \
    MPLCONFIGDIR=/home/user/.config/matplotlib \
    PYTHONUNBUFFERED=1
WORKDIR $HOME/app

# Instala dependências primeiro (cache de camada).
COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copia o restante do projeto (ver .dockerignore — casos_reais NÃO entra).
COPY --chown=user:user . .

# HF Spaces espera a porta 7860; Render injeta $PORT. Atende aos dois.
EXPOSE 7860
CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-7860}"]
