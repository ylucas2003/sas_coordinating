"""Fake mínimo do cliente PostgREST — só o que o motor de lembretes usa.

Existe porque a varredura da véspera (P3) é a única peça do motor cuja lógica
NÃO cabe numa função pura: ela é reconciliação, e o que importa é a sequência
(materializa → envia → tick seguinte). O primeiro bug real que este fake pegou
foi exatamente isso — a varredura tentando recriar, depois do envio, o disparo
de cada aluno, porque 'enviado' não estava na lista de quem já tinha um.

⚠️ NÃO substitui a verificação no banco de verdade: aqui o índice único é
imitado em Python, o claim (CAS) não tem concorrência real e o schema cache do
PostgREST não existe. Isso é a §6 do plano, com curl e psql.
"""
from __future__ import annotations

import uuid


class Resp:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count


class Query:
    def __init__(self, db, tabela, op, payload=None, **kw):
        self.db, self.tabela, self.op, self.payload, self.kw = db, tabela, op, payload, kw
        self.filtros = []
        self.colunas = "*"
        self.contagem = None
        self._limit = None
        self._order = None

    # --- filtros ---
    def eq(self, c, v): self.filtros.append(("eq", c, v)); return self
    def lt(self, c, v): self.filtros.append(("lt", c, v)); return self
    def lte(self, c, v): self.filtros.append(("lte", c, v)); return self
    def gte(self, c, v): self.filtros.append(("gte", c, v)); return self
    def in_(self, c, v): self.filtros.append(("in", c, list(v))); return self
    def is_(self, c, v): self.filtros.append(("is", c, v)); return self

    @property
    def not_(self):
        """`.not_.is_(col, "null")` — só a negação de `is`, que é a usada."""
        return _Negado(self)
    def like(self, c, v): self.filtros.append(("like", c, v)); return self
    def limit(self, n): self._limit = n; return self
    def order(self, c, desc=False): self._order = (c, desc); return self

    def _bate(self, linha) -> bool:
        for tipo, col, val in self.filtros:
            atual = linha.get(col)
            if tipo == "eq" and atual != val: return False
            if tipo == "in" and atual not in val: return False
            if tipo == "is" and val == "null" and atual is not None: return False
            if tipo == "nao_is" and val == "null" and atual is None: return False
            if tipo == "lt" and not (atual is not None and str(atual) < str(val)): return False
            if tipo == "lte" and not (atual is not None and str(atual) <= str(val)): return False
            if tipo == "gte" and not (atual is not None and str(atual) >= str(val)): return False
            if tipo == "like":
                alvo = str(val).replace("%", "")
                if not str(atual or "").startswith(alvo): return False
        return True

    def _embed(self, linha):
        """Resolve 'evento_agenda(...)' do select aninhado."""
        if "evento_agenda(" not in self.colunas:
            return linha
        copia = dict(linha)
        eid = linha.get("evento_agenda_id")
        copia["evento_agenda"] = dict(self.db["evento_agenda"].get(eid, {})) if eid else None
        return copia

    def execute(self):
        tabela = self.db.setdefault(self.tabela, {})
        if self.op == "select":
            linhas = [self._embed(l) for l in tabela.values() if self._bate(l)]
            if self._order:
                linhas.sort(key=lambda l: str(l.get(self._order[0]) or ""), reverse=self._order[1])
            n = len(linhas)
            if self._limit: linhas = linhas[: self._limit]
            return Resp(linhas, count=n if self.contagem else None)
        if self.op == "insert":
            itens = self.payload if isinstance(self.payload, list) else [self.payload]
            criados = []
            for item in itens:
                linha = dict(item)
                linha.setdefault("id", str(uuid.uuid4()))
                linha.setdefault("estado", "agendado")
                linha.setdefault("tentativas", 0)
                # índice único parcial da 0020
                chave = linha.get("chave_idempotencia")
                if chave:
                    for outra in tabela.values():
                        if outra.get("chave_idempotencia") == chave and outra.get("estado") != "cancelado":
                            raise RuntimeError(f"unique violation: {chave}")
                tabela[linha["id"]] = linha
                criados.append(linha)
            return Resp(criados)
        if self.op == "upsert":
            item = dict(self.payload)
            chave = self.kw.get("on_conflict", "id")
            existente = next((k for k, v in tabela.items() if v.get(chave) == item.get(chave)), None)
            id_ = existente or item.get("id") or str(uuid.uuid4())
            item.setdefault("id", id_)
            tabela[id_] = {**tabela.get(id_, {}), **item}
            return Resp([tabela[id_]])
        if self.op == "update":
            afetadas = []
            for linha in tabela.values():
                if self._bate(linha):
                    linha.update(self.payload)
                    afetadas.append(linha)
            return Resp(afetadas)
        raise AssertionError(self.op)


class _Negado:
    """O `.not_` do postgrest-py devolve um proxy; aqui só `is_` é preciso."""
    def __init__(self, q): self.q = q
    def is_(self, c, v):
        self.q.filtros.append(("nao_is", c, v))
        return self.q


class Tabela:
    def __init__(self, db, nome): self.db, self.nome = db, nome
    def select(self, *cols, count=None):
        q = Query(self.db, self.nome, "select"); q.colunas = ",".join(cols); q.contagem = count; return q
    def insert(self, json, **kw): return Query(self.db, self.nome, "insert", json, **kw)
    def upsert(self, json, **kw): return Query(self.db, self.nome, "upsert", json, **kw)
    def update(self, json, **kw): return Query(self.db, self.nome, "update", json, **kw)


class FakeCliente:
    def __init__(self, db): self.db = db
    def table(self, nome): return Tabela(self.db, nome)
