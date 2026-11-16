import pandas as pd
from validator.generate_data import generate
from validator.reconcile import reconcile, evaluate, transposicao, severidade


def _df(rows):
    return pd.DataFrame(rows, columns=["doc_id", "data", "centro_custo", "valor"])


def test_transposicao():
    assert transposicao(12980.50, 12089.50) is False  # troca não adjacente
    assert transposicao(12980.50, 12908.50) is True


def test_regras_basicas():
    a = _df([("D1", "2025-01-01", "CC1", 100.0), ("D2", "2025-01-01", "CC1", 50.0), ("D3", "2025-01-01", "CC1", 10.0)])
    b = _df([("D1", "2025-01-01", "CC1", 100.0), ("D2", "2025-01-01", "CC1", 55.0), ("D4", "2025-01-01", "CC1", 7.0)])
    f = reconcile(a, b)
    assert set(f.regra) == {"R01", "R02", "R03"}
    assert f[f.regra == "R03"].exposicao.iloc[0] == 5.0


def test_severidade():
    assert severidade(20000) == "Alta" and severidade(1500) == "Média" and severidade(10) == "Baixa"


def test_gerador_e_motor_sinteticos():
    a, b, truth = generate(300, 7)
    m = evaluate(reconcile(a, b), truth)
    assert m["recall"] == 1.0 and m["precisao"] >= 0.95
