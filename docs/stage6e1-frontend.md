# Stage 6E.1 frontend

The professional frontend lives in `frontend/` and uses Next.js App Router, TypeScript, Tailwind CSS and Recharts. It is a same-origin BFF: the FastAPI bearer token is stored in an HttpOnly cookie and browser requests go through `/api/*`; the backend URL is never exposed to client JavaScript. Mutation requests are protected by SameSite cookies and an Origin/Host check.

## Local development

From the repository root, prepare the existing local backend and mock worker:

```bash
cp .env.example .env
# set FINFLOW_MOCK_EXTRACTION=1 and local database settings in .env
cd backend && alembic upgrade head && cd ..
uvicorn backend.app.main:app --reload
# in another terminal, from the repository root:
FINFLOW_MOCK_EXTRACTION=1 python -m backend.worker
```

In a third terminal:

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Open <http://localhost:3000>. Mock mode is explicitly labelled in the scanner and is not Qwen inference. Use `npm run typecheck`, `npm run lint`, `npm test` and `npm run build` for frontend validation.

The frontend currently has unit coverage for correction diffing. Full browser acceptance remains dependent on a running isolated backend/database/worker fixture; do not point tests at production data.

## Scope and security notes

The dashboard consumes `/expenses/summary`; scanner polling consumes `/predict` and `/jobs/{job_id}`; review uses the review, image, correction, approval and rejection APIs. Approval is never performed by saving corrections and remains backend-authoritative. Original model values are displayed read-only. Viewer controls are hidden in the UI, while API RBAC remains authoritative.

The BFF uses an HttpOnly token cookie, same-origin image retrieval and no localStorage token. Production still requires HTTPS, a deployed reverse proxy, strict CSP/CORS configuration, rate limiting, secret rotation and a browser-level security review.
