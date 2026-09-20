import uuid
import bcrypt
from datetime import datetime, timedelta

from jose import jwt

from app.config import settings
from app.services.supabase_client import get_supabase


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_token(subject: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=settings.jwt_expire_hours)
    payload = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def register_user(data: dict) -> dict:
    supabase = get_supabase()

    # Verificar duplicidade de CPF
    existing = (
        supabase.table("usuario")
        .select("id")
        .eq("cpf", data["cpf"])
        .execute()
    )
    if existing.data:
        raise ValueError("CPF já cadastrado")

    senha_hash = hash_password(data["senha"])
    user_id = str(uuid.uuid4())

    insert_data = {
        "id": user_id,
        "nome": data["nome"],
        "cpf": data["cpf"],
        "telefone": data.get("telefone"),
        "senha_hash": senha_hash,
        "tipo_perfil": data["tipo_perfil"],
    }

    result = supabase.table("usuario").insert(insert_data).execute()
    if not result.data:
        raise RuntimeError("Falha ao cadastrar usuário")

    row = result.data[0]
    token = create_token(row["id"])
    return {
        "access_token": token,
        "id": row["id"],
        "nome": row["nome"],
        "cpf": row["cpf"],
        "tipo_perfil": row["tipo_perfil"],
    }


def authenticate_user(cpf: str, senha: str) -> dict:
    supabase = get_supabase()

    result = (
        supabase.table("usuario")
        .select("id, nome, cpf, senha_hash, tipo_perfil")
        .eq("cpf", cpf)
        .execute()
    )

    if not result.data:
        raise ValueError("CPF ou senha inválidos")

    user = result.data[0]
    if not verify_password(senha, user["senha_hash"]):
        raise ValueError("CPF ou senha inválidos")

    token = create_token(user["id"])
    return {
        "access_token": token,
        "id": user["id"],
        "nome": user["nome"],
        "cpf": user["cpf"],
        "tipo_perfil": user["tipo_perfil"],
    }