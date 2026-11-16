"""CLI: python run_validation.py [--provider offline|anthropic|openai|gemini]"""
import argparse, json
from pathlib import Path
import pandas as pd
from validator.reconcile import reconcile, summarize, evaluate
from validator.report import generate_report

p = argparse.ArgumentParser()
p.add_argument("--a", default="data/base_a_razao_contabil.csv")
p.add_argument("--b", default="data/base_b_relatorio_gerencial.csv")
p.add_argument("--truth", default="data/ground_truth.json")
p.add_argument("--provider", default="offline")
p.add_argument("--tol", type=float, default=0.01)
p.add_argument("--tol-dias", type=int, default=3)
args = p.parse_args()

a, b = pd.read_csv(args.a), pd.read_csv(args.b)
achados = reconcile(a, b, args.tol, args.tol_dias)
resumo = summarize(a, b, achados)
Path("outputs").mkdir(exist_ok=True)
achados.to_csv("outputs/findings.csv", index=False)
Path("outputs/parecer.md").write_text(generate_report(resumo, achados, args.provider), encoding="utf-8")
print(json.dumps(resumo, ensure_ascii=False, indent=2))
if Path(args.truth).exists():
    print("Avaliação vs gabarito:", evaluate(achados, json.loads(Path(args.truth).read_text(encoding="utf-8"))))
