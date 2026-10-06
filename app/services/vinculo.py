from app.services.supabase_client import get_supabase


def cuidador_vinculado(id_cuidador: str, id_idoso: str) -> bool:
    supabase = get_supabase()
    result = (
        supabase.table("vinculo_cuidador")
        .select("id")
        .eq("id_cuidador", id_cuidador)
        .eq("id_idoso", id_idoso)
        .execute()
    )
    return bool(result.data)


def ids_idosos_do_cuidador(id_cuidador: str) -> list[str]:
    supabase = get_supabase()
    result = (
        supabase.table("vinculo_cuidador")
        .select("id_idoso")
        .eq("id_cuidador", id_cuidador)
        .execute()
    )
    return [row["id_idoso"] for row in result.data or []]


def ids_idosos_acessiveis(user: dict) -> list[str]:
    if user["tipo_perfil"] == "IDOSO":
        return [user["id"]]
    return ids_idosos_do_cuidador(user["id"])


def get_vinculo(vinculo_id: str) -> dict | None:
    supabase = get_supabase()
    result = supabase.table("vinculo_cuidador").select("*").eq("id", vinculo_id).execute()
    return result.data[0] if result.data else None


def create_vinculo(id_cuidador: str, cpf_idoso: str, parentesco: str | None) -> dict:
    supabase = get_supabase()
    idoso = (
        supabase.table("usuario")
        .select("id, nome, tipo_perfil")
        .eq("cpf", cpf_idoso)
        .execute()
    )
    if not idoso.data:
        raise LookupError("Nenhum usuário encontrado com este CPF")
    idoso = idoso.data[0]
    if idoso["tipo_perfil"] != "IDOSO":
        raise ValueError("O CPF informado não pertence a um usuário do perfil IDOSO")
    if cuidador_vinculado(id_cuidador, idoso["id"]):
        raise FileExistsError("Você já está vinculado a este idoso")

    result = (
        supabase.table("vinculo_cuidador")
        .insert({"id_cuidador": id_cuidador, "id_idoso": idoso["id"], "parentesco": parentesco})
        .execute()
    )
    if not result.data:
        raise RuntimeError("Falha ao criar vínculo")
    return {**result.data[0], "nome_idoso": idoso["nome"]}


def list_vinculos(user: dict) -> list[dict]:
    supabase = get_supabase()
    coluna_propria, coluna_outro = (
        ("id_cuidador", "id_idoso") if user["tipo_perfil"] == "CUIDADOR" else ("id_idoso", "id_cuidador")
    )
    vinculos = (
        supabase.table("vinculo_cuidador").select("*").eq(coluna_propria, user["id"]).execute().data
        or []
    )
    if not vinculos:
        return []

    ids = list({v[coluna_outro] for v in vinculos})
    usuarios = supabase.table("usuario").select("id, nome").in_("id", ids).execute().data or []
    nomes = {u["id"]: u["nome"] for u in usuarios}

    for v in vinculos:
        v["nome_idoso"] = nomes.get(v["id_idoso"]) if coluna_outro == "id_idoso" else user["nome"]
        v["nome_cuidador"] = nomes.get(v["id_cuidador"]) if coluna_outro == "id_cuidador" else user["nome"]
    return vinculos


def delete_vinculo(vinculo_id: str) -> bool:
    supabase = get_supabase()
    result = supabase.table("vinculo_cuidador").delete().eq("id", vinculo_id).execute()
    return bool(result.data)
