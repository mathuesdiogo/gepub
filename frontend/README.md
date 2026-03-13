# Frontend Lab GEPUB

Workspace React + TypeScript integrado ao Django.

## Stack

- React 19 + Vite
- TailwindCSS
- Radix UI
- TanStack Query / Table
- React Hook Form + Zod
- Recharts + Chart.js + Plotly
- Tiptap

## Rotas Django

- Tela: `/sistema/frontend-lab/`
- API overview: `/api/frontend/overview/`
- API secretarias: `/api/frontend/secretarias/`

## Desenvolvimento

```bash
# se o node local ainda nao estiver no PATH:
export PATH="$HOME/.local/node/bin:$PATH"

npm install
npm run dev
```

## Build para Django

```bash
npm run build
```

O build gera os arquivos em `../static/frontend/`:

- `app.js`
- `app.css`
- `chunks/*`

A template Django `templates/core/design_system/frontend_lab.html` carrega esses assets automaticamente.
