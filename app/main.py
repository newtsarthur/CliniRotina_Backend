import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.auth import router as auth_router
from app.routers.medicamento import router as medicamento_router

app = FastAPI(
    title="CliniRotina API",
    description="Backend de suporte à organização de rotinas de saúde e integração com rotinas de otimização",
    version="0.3.0",
)

# Origens locais (Vite/localhost em qualquer porta), deploys da Vercel (*.vercel.app)
# e origens extras opcionais via variável de ambiente FRONTEND_URL (separadas por vírgula).
extra_origins = [o.strip() for o in os.getenv("FRONTEND_URL", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=extra_origins,
    allow_origin_regex=r"^(https?://(localhost|127\.0\.0\.1)(:\d+)?|https://([a-z0-9-]+\.)*vercel\.app)$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(medicamento_router)


@app.get("/", tags=["Raiz"])
def root():
    return {"message": "API CliniRotina operacional", "status": "online"}


@app.get("/health", tags=["Saúde"])
def health_check():
    return {"database": "connected", "service": "healthy"}