"""Gerador de dados 100% sintéticos: duas bases com anomalias injetadas e gabarito."""
import argparse, json, random
from datetime import date, timedelta
from pathlib import Path
import pandas as pd

CENTROS = ["CC-100 Tecnologia", "CC-200 Operações", "CC-300 Comercial", "CC-400 Jurídico", "CC-500 RH"]
CONTAS = [("3.1.01", "Licenças de Software"), ("3.1.02", "Serviços de Consultoria"),
          ("3.2.01", "Infraestrutura Cloud"), ("3.3.01", "Treinamento"), ("3.4.01", "Viagens")]
TIPOS = {"valor": "R03", "transposicao": "R04", "ausente_b": "R01", "ausente_a": "R02",
         "duplicado": "R05", "data": "R06", "centro_custo": "R07"}


def _transpor(v: float, rng: random.Random) -> float:
    s = f"{v:.2f}".replace(".", "")
    pos = [i for i in range(len(s) - 1) if s[i] != s[i + 1] and not (i == 0 and s[1] == "0")]
    i = rng.choice(pos)
    s = s[:i] + s[i + 1] + s[i] + s[i + 2:]
    return int(s) / 100


def generate(n: int = 300, seed: int = 42, taxa: float = 0.18):
    rng = random.Random(seed)
    rows = []
    for i in range(1, n + 1):
        conta, desc = rng.choice(CONTAS)
        rows.append({"doc_id": f"DOC-{i:05d}",
                     "data": (date(2025, 1, 1) + timedelta(days=rng.randint(0, 89))).isoformat(),
                     "centro_custo": rng.choice(CENTROS), "conta": conta, "descricao": desc,
                     "fornecedor": f"Fornecedor {rng.choice('ABCDEFGHIJ')}",
                     "valor": round(rng.uniform(150, 45000), 2)})
    a, b = pd.DataFrame(rows), pd.DataFrame(rows)
    drop_a, drop_b, dups, truth = set(), set(), [], []
    chaves = list(TIPOS)
    for k, doc in enumerate(rng.sample(list(a.doc_id), int(n * taxa))):
        tipo, ix = chaves[k % len(chaves)], b.index[b.doc_id == doc][0]
        if tipo == "valor":
            b.at[ix, "valor"] = round(b.at[ix, "valor"] * rng.uniform(1.02, 1.3), 2)
        elif tipo == "transposicao":
            b.at[ix, "valor"] = _transpor(b.at[ix, "valor"], rng)
        elif tipo == "ausente_b":
            drop_b.add(doc)
        elif tipo == "ausente_a":
            drop_a.add(doc)
        elif tipo == "duplicado":
            dups.append(b.loc[ix].to_dict())
        elif tipo == "data":
            b.at[ix, "data"] = (date.fromisoformat(b.at[ix, "data"]) + timedelta(days=rng.randint(10, 25))).isoformat()
        elif tipo == "centro_custo":
            b.at[ix, "centro_custo"] = rng.choice([c for c in CENTROS if c != b.at[ix, "centro_custo"]])
        truth.append({"doc_id": doc, "tipo": tipo, "regra_esperada": TIPOS[tipo]})
    a = a[~a.doc_id.isin(drop_a)].reset_index(drop=True)
    b = pd.concat([b[~b.doc_id.isin(drop_b)], pd.DataFrame(dups)]).sample(frac=1, random_state=seed).reset_index(drop=True)
    return a, b, truth


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=300)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", default="data")
    args = p.parse_args()
    a, b, truth = generate(args.n, args.seed)
    out = Path(args.out); out.mkdir(exist_ok=True)
    a.to_csv(out / "base_a_razao_contabil.csv", index=False)
    b.to_csv(out / "base_b_relatorio_gerencial.csv", index=False)
    (out / "ground_truth.json").write_text(json.dumps(truth, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Base A: {len(a)} linhas | Base B: {len(b)} linhas | anomalias injetadas: {len(truth)}")
