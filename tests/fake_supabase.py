"""Substituto em memória do cliente Supabase, usado apenas nos testes."""
import uuid
from types import SimpleNamespace


class FakeQuery:
    def __init__(self, store: list[dict]):
        self.store = store
        self.filtros = []
        self.acao = "select"
        self.payload = None
        self.ordem = None

    def select(self, *_):
        self.acao = "select"
        return self

    def insert(self, payload):
        self.acao, self.payload = "insert", payload
        return self

    def update(self, payload):
        self.acao, self.payload = "update", payload
        return self

    def delete(self):
        self.acao = "delete"
        return self

    def eq(self, col, val):
        self.filtros.append(lambda r: r.get(col) == val)
        return self

    def in_(self, col, vals):
        self.filtros.append(lambda r: r.get(col) in vals)
        return self

    def gte(self, col, val):
        self.filtros.append(lambda r: r.get(col) >= val)
        return self

    def lt(self, col, val):
        self.filtros.append(lambda r: r.get(col) < val)
        return self

    def order(self, col):
        self.ordem = col
        return self

    def _match(self):
        return [r for r in self.store if all(f(r) for f in self.filtros)]

    def execute(self):
        if self.acao == "insert":
            row = {"id": str(uuid.uuid4()), **self.payload}
            self.store.append(row)
            return SimpleNamespace(data=[dict(row)])
        rows = self._match()
        if self.acao == "update":
            for r in rows:
                r.update(self.payload)
        elif self.acao == "delete":
            for r in rows:
                self.store.remove(r)
        if self.ordem:
            rows = sorted(rows, key=lambda r: r[self.ordem])
        return SimpleNamespace(data=[dict(r) for r in rows])


class FakeSupabase:
    def __init__(self):
        self.tabelas: dict[str, list[dict]] = {}

    def table(self, nome):
        return FakeQuery(self.tabelas.setdefault(nome, []))
