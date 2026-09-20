from fastapi import FastAPI
from app.routers.auth import router as auth_router
from app.routers.medicamento import router as medicamento_router

app = FastAPI(
    title="CliniRotina API",
    description="Backend de suporte à organização de rotinas de saúde e integração com rotinas de otimização",
    version="0.3.0",
)

app.include_router(auth_router)
app.include_router(medicamento_router)


@app.get("/", tags=["Raiz"])
def root():
    return {"message": "API CliniRotina operacional", "status": "online"}


@app.get("/health", tags=["Saúde"])
def health_check():
    return {"database": "connected", "service": "healthy"}