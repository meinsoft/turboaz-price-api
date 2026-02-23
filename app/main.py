from fastapi import FastAPI
from app.routers.recommend import router as rec_router
from app.routers.analyze import router as ana_router

app = FastAPI(title="TurboAZ Analiz API")
app.include_router(rec_router, prefix="/api")
app.include_router(ana_router, prefix="/api")
