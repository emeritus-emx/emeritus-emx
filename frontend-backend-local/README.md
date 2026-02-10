# NUESA Frontend Backend (Minimal Express)

Minimal Node/Express backend to support the frontend.

Quick start (WSL):

```bash
cd /home/tonie/project/NUESA\ SCHOLARS\ \&\ INTENT/frontend-backend-local
npm install
npm run start
```

Defaults:
- Server port: `5000` (use `PORT` env var to override)
- API base path: `/api`

Endpoints:
- `GET /` — root
- `GET /health` — health check
- `GET /api/opportunities` — sample list
- `POST /api/contact` — sample POST receiver
