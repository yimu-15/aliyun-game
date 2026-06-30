"""FastAPI 后端入口"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import backend
from backend.api.prediction import router as prediction_router
from backend.api.data import router as data_router

app = FastAPI(
    title=backend.TITLE,
    version=backend.VERSION,
    description=backend.DESCRIPTION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(prediction_router, prefix="/api/prediction", tags=["预测"])
app.include_router(data_router, prefix="/api/data", tags=["数据"])


@app.get("/api/health")
def health_check():
    return {"status": "ok", "version": backend.VERSION}


def start():
    """入口函数 — 通过 pyproject.toml [project.scripts] 调用"""
    uvicorn.run(
        "backend.main:app",
        host=backend.HOST,
        port=backend.PORT,
        reload=backend.RELOAD,
    )


if __name__ == "__main__":
    start()
