from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .data_service import ElexonApiError, load_analysis

app = FastAPI(title="UK Wind Forecast Analysis")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173","https://frontend-sepia-delta-83.vercel.app/"], allow_methods=["GET"], allow_headers=["*"])

@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}

@app.get("/api/analysis")
def analysis() -> dict:
    try:
        return load_analysis()
    except ElexonApiError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

