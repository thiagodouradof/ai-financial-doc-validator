"""Parecer executivo. O LLM só redige; os números vêm do motor de regras (reconcile.py)."""
import json, os
from .reconcile import brl

SYSTEM = ("Você é um auditor financeiro sênior. Redija um parecer executivo em português, objetivo e em Markdown, "
          "usando APENAS os números fornecidos. Nunca invente valores, documentos ou causas certas; "
          "trate causas como hipóteses. Estrutura: Resumo, Principais achados, Riscos, Recomendações.")


def build_prompt(resumo: dict, achados, top_n: int = 10) -> str:
    top = achados.head(top_n)[["doc_id", "regra", "severidade", "exposicao", "detalhe"]].to_dict("records")
    return f"RESUMO:\n{json.dumps(resumo, ensure_ascii=False, indent=2)}\n\nMAIORES ACHADOS:\n{json.dumps(top, ensure_ascii=False, indent=2)}"


def offline(resumo: dict, achados, top_n: int = 5) -> str:
    r = resumo
    linhas = [f"- **{x.doc_id}** ({x.descricao_regra}, severidade {x.severidade}): R$ {brl(x.exposicao)}. {x.detalhe}"
              for x in achados.head(top_n).itertuples()]
    regras = "\n".join(f"- {k}: {v}" for k, v in r["por_regra"].items())
    parecer = "NÃO RECOMENDADO para fechamento sem revisão" if r["por_severidade"].get("Alta", 0) else "APROVADO COM RESSALVAS"
    return (f"# Parecer de conciliação\n\n**Conclusão:** {parecer}.\n\n## Resumo\n"
            f"Foram confrontados {r['documentos_unicos']} documentos únicos. {r['documentos_com_achado']} apresentam achados "
            f"(conformidade de {r['taxa_conformidade']:.1%}) e a exposição total é de R$ {brl(r['exposicao_total'])}.\n\n"
            f"## Achados por regra\n{regras}\n\n## Maiores exposições\n" + "\n".join(linhas) +
            "\n\n## Recomendações\n1. Tratar primeiro as severidades Alta.\n2. Validar na origem as divergências com possível transposição de dígitos.\n"
            "3. Corrigir ausências e duplicidades antes do fechamento.\n\n_Parecer gerado por template determinístico (modo offline)._")


def _anthropic(prompt):
    import anthropic
    m = anthropic.Anthropic().messages.create(model=os.getenv("LLM_MODEL") or "claude-sonnet-4-6", max_tokens=1500,
                                              system=SYSTEM, messages=[{"role": "user", "content": prompt}])
    return m.content[0].text


def _openai(prompt):
    from openai import OpenAI
    r = OpenAI().chat.completions.create(model=os.getenv("LLM_MODEL") or "gpt-4o-mini",
                                         messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}])
    return r.choices[0].message.content


def _gemini(prompt):
    import google.generativeai as genai
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    return genai.GenerativeModel(os.getenv("LLM_MODEL") or "gemini-1.5-flash", system_instruction=SYSTEM).generate_content(prompt).text


PROVIDERS = {"anthropic": _anthropic, "openai": _openai, "gemini": _gemini}


def generate_report(resumo: dict, achados, provider: str = "offline") -> str:
    if provider not in PROVIDERS:
        return offline(resumo, achados)
    try:
        return PROVIDERS[provider](build_prompt(resumo, achados))
    except Exception as e:  # sem chave, sem rede ou SDK ausente: cai no modo offline
        return offline(resumo, achados) + f"\n\n> Falha no provedor `{provider}` ({type(e).__name__}); usado modo offline."
