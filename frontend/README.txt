Hifazat frontend — quick start
==============================

PROTOTYPE — All data is simulated. Not an official service.

Setup (from the folder that contains both backend/ and frontend/):

  cd frontend
  npm install
  npm run dev      -> open http://localhost:5173

Start the backend first, on port 8000:

  Linux/macOS:  source backend/.venv/bin/activate
  Windows:      backend\.venv\Scripts\activate
  then:         cd backend && uvicorn app.main:app --reload --port 8000

The backend must also allow CORS from http://localhost:5173, e.g. in your
FastAPI app:

  from fastapi.middleware.cors import CORSMiddleware
  app.add_middleware(
      CORSMiddleware,
      allow_origins=["http://localhost:5173"],
      allow_methods=["*"],
      allow_headers=["*"],
  )

Notes:
- Base URL of the backend is one constant: src/api.js line 16 (BASE_URL).
- X-API-Key sent with every request: "hifazat-prototype-key" (src/api.js).
- Login stores token/role/name in localStorage and redirects by role.
- Production build: npm run build  (output in dist/)
