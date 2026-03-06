# vapt-vupt

## Deploy no Render (Front + Back)

Este repositorio ja inclui `render.yaml` para subir os dois servicos juntos.

### 1. Preparar variaveis de ambiente

No Render, configure no servico `vapt-vupt-api`:

- `LALAMOVE_API_KEY`
- `LALAMOVE_API_SECRET`

Opcional:

- `LALAMOVE_BASE_URL` (padrao: `https://rest.sandbox.lalamove.com`)

### 2. Criar servicos via Blueprint

1. Suba este repositorio no GitHub.
2. No Render, clique em `New +` -> `Blueprint`.
3. Selecione o repositorio.
4. O Render vai ler `render.yaml` e criar:
	- `vapt-vupt-api` (Web Service Python/Flask)
	- `vapt-vupt-front` (Static Site React)

### 3. Build/start configurados

Backend (`back`):

- Build: `pip install -r requirements.txt`
- Start: `gunicorn app:app`
- Healthcheck: `/health`

Frontend (`front/vapt-vupt-front`):

- Build: `npm ci && npm run build`
- Publish: `build`
- `REACT_APP_API_BASE_URL` aponta automaticamente para o host do backend (o front completa com `https://`)

### 4. Desenvolvimento local

Frontend usa `REACT_APP_API_BASE_URL` quando definido; se nao estiver definido, usa `http://localhost:5000`.