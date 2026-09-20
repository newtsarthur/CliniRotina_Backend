from app.services.supabase_client import get_supabase


def create_medicamento(data: dict) -> dict:
    supabase = get_supabase()
    result = supabase.table("medicamento").insert(data).execute()
    if not result.data:
        raise RuntimeError("Falha ao criar medicamento")
    return result.data[0]


def list_medicamentos(id_idoso: str | None = None) -> list:
    supabase = get_supabase()
    query = supabase.table("medicamento").select("*")
    if id_idoso:
        query = query.eq("id_idoso", id_idoso)
    result = query.execute()
    return result.data or []


def get_medicamento(medicamento_id: str) -> dict | None:
    supabase = get_supabase()
    result = supabase.table("medicamento").select("*").eq("id", medicamento_id).execute()
    if not result.data:
        return None
    return result.data[0]


def update_medicamento(medicamento_id: str, data: dict) -> dict | None:
    supabase = get_supabase()
    result = supabase.table("medicamento").update(data).eq("id", medicamento_id).execute()
    if not result.data:
        return None
    return result.data[0]


def delete_medicamento(medicamento_id: str) -> bool:
    supabase = get_supabase()
    result = supabase.table("medicamento").delete().eq("id", medicamento_id).execute()
    return bool(result.data)