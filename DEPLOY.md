# Publicar o Analisador 87T (link para WhatsApp)

O app é uma página web (FastAPI + uvicorn). Hospede em um serviço gratuito e
mande **só o link** — o professor abre no navegador (Mac, Windows ou celular),
sobe o `.cfg`/`.dat` e vê o resultado. Sem instalação, sem aviso de segurança.

Os arquivos `Dockerfile` e `.dockerignore` já estão prontos no repositório.

---

## Opção A — Hugging Face Spaces (recomendado: fica **sempre ligado**)

Melhor experiência para quem recebe o link (sem cold-start).

1. Crie uma conta em <https://huggingface.co> (grátis).
2. **New Space** → escolha **Docker** como *SDK* → visibilidade **Public**.
3. Suba o código para o Space (ele tem um Git próprio):
   ```bash
   git remote add space https://huggingface.co/spaces/SEU_USUARIO/analise-87t
   git push space versao-api:main
   ```
   (ou arraste os arquivos pela aba **Files** do Space)
4. No topo do `README.md` **do Space**, garanta este cabeçalho YAML:
   ```yaml
   ---
   title: Analisador 87T
   emoji: ⚡
   colorFrom: blue
   colorTo: indigo
   sdk: docker
   app_port: 7860
   pinned: false
   ---
   ```
5. O Space builda sozinho (~3–5 min). O link fica:
   `https://SEU_USUARIO-analise-87t.hf.space` → **é esse que vai no WhatsApp.**

---

## Opção B — Render (mais fácil de subir: usa seu GitHub direto)

Mais simples de configurar, mas o plano grátis **hiberna** após 15 min sem uso
(a primeira abertura depois disso leva ~50 s para "acordar").

1. Crie conta em <https://render.com> e conecte sua conta do GitHub.
2. **New** → **Web Service** → selecione o repositório `analise_trifasica`,
   branch `versao-api`.
3. Render detecta o `Dockerfile` automaticamente. Plano: **Free**.
4. **Create Web Service**. Ao terminar o build, o link é algo como
   `https://analise-87t.onrender.com` → esse vai no WhatsApp.

> O Render injeta a variável `PORT`; o `Dockerfile` já a respeita.

---

## Testar a imagem localmente (opcional, exige Docker)

```bash
docker build -t analise87t .
docker run -p 7860:7860 analise87t
# abra http://localhost:7860
```

## Observações
- Os **dados reais** (`casos_reais/`) ficam fora da imagem (`.dockerignore`) —
  mantenha assim por confidencialidade.
- O serviço é **stateless**: cada upload é processado e descartado
  (`scratch_api/` é temporário). Nada do professor fica armazenado.
