"""Motor determinístico de conciliação. Todos os números do parecer vêm daqui, nunca do LLM."""
import pandas as pd

REGRAS = {
    "R01": "Documento ausente na Base B", "R02": "Documento ausente na Base A",
    "R03": "Divergência de valor", "R04": "Possível transposição de dígitos",
    "R05": "Documento duplicado", "R06": "Divergência de data acima da tolerância",
    "R07": "Divergência de centro de custo",
}


def brl(v: float) -> str:
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def severidade(exposicao: float) -> str:
    return "Alta" if exposicao >= 10000 else "Média" if exposicao >= 1000 else "Baixa"


def transposicao(x: float, y: float) -> bool:
    sx, sy = f"{x:.2f}".replace(".", ""), f"{y:.2f}".replace(".", "")
    if sx == sy or len(sx) != len(sy):
        return False
    d = [i for i in range(len(sx)) if sx[i] != sy[i]]
    return len(d) == 2 and d[1] == d[0] + 1 and sx[d[0]] == sy[d[1]] and sx[d[1]] == sy[d[0]]


def _norm(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["doc_id"] = df["doc_id"].astype(str).str.strip().str.upper()
    df["data"] = pd.to_datetime(df["data"])
    df["valor"] = df["valor"].astype(float).round(2)
    return df


def reconcile(a: pd.DataFrame, b: pd.DataFrame, tol: float = 0.01, tol_dias: int = 3) -> pd.DataFrame:
    a, b, out = _norm(a), _norm(b), []

    def add(doc, regra, va, vb, exposicao, detalhe):
        out.append({"doc_id": doc, "regra": regra, "descricao_regra": REGRAS[regra],
                    "severidade": severidade(exposicao) if regra not in ("R06", "R07") else "Baixa",
                    "valor_a": va, "valor_b": vb, "exposicao": round(float(exposicao), 2), "detalhe": detalhe})

    for nome, df in (("A", a), ("B", b)):
        for doc, g in df[df.duplicated("doc_id", keep=False)].groupby("doc_id"):
            add(doc, "R05", None, None, g.valor.iloc[0], f"Aparece {len(g)}x na Base {nome}")

    m = a.drop_duplicates("doc_id").merge(b.drop_duplicates("doc_id"), on="doc_id", how="outer",
                                          suffixes=("_a", "_b"), indicator=True)
    for r in m.to_dict("records"):
        doc = r["doc_id"]
        if r["_merge"] == "left_only":
            add(doc, "R01", r["valor_a"], None, r["valor_a"], "Lançado na Base A e inexistente na Base B")
        elif r["_merge"] == "right_only":
            add(doc, "R02", None, r["valor_b"], r["valor_b"], "Lançado na Base B e inexistente na Base A")
        else:
            va, vb = r["valor_a"], r["valor_b"]
            if abs(va - vb) > tol:
                add(doc, "R04" if transposicao(va, vb) else "R03", va, vb, abs(va - vb), f"A={brl(va)} vs B={brl(vb)}")
            dias = abs((r["data_a"] - r["data_b"]).days)
            if dias > tol_dias:
                add(doc, "R06", va, vb, 0, f"Datas diferem em {dias} dias")
            if r["centro_custo_a"] != r["centro_custo_b"]:
                add(doc, "R07", va, vb, 0, f"{r['centro_custo_a']} vs {r['centro_custo_b']}")
    cols = ["doc_id", "regra", "descricao_regra", "severidade", "valor_a", "valor_b", "exposicao", "detalhe"]
    return pd.DataFrame(out, columns=cols).sort_values("exposicao", ascending=False).reset_index(drop=True)


def summarize(a, b, f: pd.DataFrame) -> dict:
    docs = len(set(a.doc_id.astype(str)) | set(b.doc_id.astype(str)))
    return {"linhas_a": len(a), "linhas_b": len(b), "documentos_unicos": docs,
            "documentos_com_achado": int(f.doc_id.nunique()),
            "taxa_conformidade": round(1 - f.doc_id.nunique() / docs, 4) if docs else 1.0,
            "exposicao_total": round(float(f.exposicao.sum()), 2),
            "por_regra": {k: int(v) for k, v in f.groupby("descricao_regra").size().items()},
            "por_severidade": {k: int(v) for k, v in f.groupby("severidade").size().items()}}


def evaluate(f: pd.DataFrame, truth: list) -> dict:
    esperado = {(t["doc_id"], t["regra_esperada"]) for t in truth}
    achado = set(zip(f.doc_id, f.regra))
    tp = len(esperado & achado)
    return {"precisao": round(tp / len(achado), 4) if achado else 0, "recall": round(tp / len(esperado), 4) if esperado else 0,
            "anomalias_injetadas": len(esperado), "anomalias_detectadas": tp}
