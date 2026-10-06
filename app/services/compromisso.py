from app.services.supabase_client import get_supabase

TABELA = "compromisso_medico"


def _serializar(data: dict) -> dict:
    if data.get("data_hora") is not None:
        data["data_hora"] = data["data_hora"].isoformat()
    return data


def existe_conflito(id_idoso: str, data_hora_iso: str, ignorar_id: str | None = None) -> bool:
    supabase = get_supabase()
    result = (
        supabase.table(TABELA)
        .select("id")
        .eq("id_idoso", id_idoso)
        .eq("data_hora", data_hora_iso)
        .execute()
    )
    return any(row["id"] != ignorar_id for row in result.data or [])


def create_compromisso(data: dict) -> dict:
    data = _serializar(data)
    if existe_conflito(data["id_idoso"], data["data_hora"]):
        raise FileExistsError("Já existe um compromisso para este idoso neste mesmo horário")
    supabase = get_supabase()
    result = supabase.table(TABELA).insert(data).execute()
    if not result.data:
        raise RuntimeError("Falha ao criar compromisso")
    return result.data[0]


def list_compromissos(
    ids_idosos: list[str],
    tipo: str | None = None,
    a_partir_de: str | None = None,
    ate: str | None = None,
) -> list:
    if not ids_idosos:
        return []
    supabase = get_supabase()
    query = supabase.table(TABELA).select("*").in_("id_idoso", ids_idosos)
    if tipo:
        query = query.eq("tipo", tipo)
    if a_partir_de:
        query = query.gte("data_hora", a_partir_de)
    if ate:
        query = query.lt("data_hora", ate)
    result = query.order("data_hora").execute()
    return result.data or []


def get_compromisso(compromisso_id: str) -> dict | None:
    supabase = get_supabase()
    result = supabase.table(TABELA).select("*").eq("id", compromisso_id).execute()
    return result.data[0] if result.data else None


def update_compromisso(compromisso_id: str, id_idoso: str, data: dict) -> dict | None:
    data = _serializar(data)
    if "data_hora" in data and existe_conflito(id_idoso, data["data_hora"], ignorar_id=compromisso_id):
        raise FileExistsError("Já existe um compromisso para este idoso neste mesmo horário")
    supabase = get_supabase()
    result = supabase.table(TABELA).update(data).eq("id", compromisso_id).execute()
    return result.data[0] if result.data else None


def delete_compromisso(compromisso_id: str) -> bool:
    supabase = get_supabase()
    result = supabase.table(TABELA).delete().eq("id", compromisso_id).execute()
    return bool(result.data)
