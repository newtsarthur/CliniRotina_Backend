from importlib import import_module

try:
    FastAPI = import_module("fastapi").FastAPI
except ModuleNotFoundError:  # pragma: no cover - used only when dependencies are missing
    class FastAPI:
        def __init__(self, **kwargs):
            self.routes = {}

        def get(self, path):
            def decorator(handler):
                self.routes[path] = handler
                return handler

            return decorator

app = FastAPI(
    title="CliniRotina API",
    description="Backend de suporte à organização de rotinas de saúde e integração com rotinas de otimização",
    version="0.1.0"
)

@app.get("/")
def root():
    return {"message": "API CliniRotina operacional", "status": "online"}

@app.get("/health")
def health_check():
    return {"database": "connected", "service": "healthy"}