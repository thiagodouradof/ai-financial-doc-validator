import json
import pandas as pd
import streamlit as st
from validator.generate_data import generate
from validator.reconcile import reconcile, summarize, evaluate, brl
from validator.report import generate_report

st.set_page_config(page_title="Validador de Documentos Financeiros", layout="wide")
st.title("Agente validador de documentos financeiros")
st.caption("Cruza duas bases, aplica regras de negócio e gera um parecer de auditoria. Dados 100% sintéticos.")

with st.sidebar:
    fonte = st.radio("Fonte dos dados", ["Dados sintéticos", "Upload de CSV"])
    tol = st.number_input("Tolerância de valor (R$)", 0.0, 100.0, 0.01, 0.01)
    tol_dias = st.slider("Tolerância de data (dias)", 0, 15, 3)
    provider = st.selectbox("Gerador do parecer", ["offline", "anthropic", "openai", "gemini"])
    st.caption("Provedores de LLM exigem chave de API no ambiente (veja .env.example).")

truth = None
if fonte == "Dados sintéticos":
    n = st.sidebar.slider("Documentos", 100, 2000, 300, 50)
    seed = st.sidebar.number_input("Seed", 0, 9999, 42)
    a, b, truth = generate(n, int(seed))
else:
    ua, ub = st.file_uploader("Base A (CSV)", type="csv"), st.file_uploader("Base B (CSV)", type="csv")
    if not (ua and ub):
        st.info("Envie as duas bases com as colunas: doc_id, data, centro_custo, valor.")
        st.stop()
    a, b = pd.read_csv(ua), pd.read_csv(ub)

achados = reconcile(a, b, tol, tol_dias)
resumo = summarize(a, b, achados)
c = st.columns(4)
c[0].metric("Documentos", resumo["documentos_unicos"])
c[1].metric("Com achados", resumo["documentos_com_achado"])
c[2].metric("Conformidade", f"{resumo['taxa_conformidade']:.1%}")
c[3].metric("Exposição (R$)", brl(resumo['exposicao_total']))
if truth:
    st.caption(f"Avaliação contra gabarito sintético: {evaluate(achados, truth)}")

esq, dir_ = st.columns([2, 1])
sev = esq.multiselect("Severidade", ["Alta", "Média", "Baixa"], default=["Alta", "Média", "Baixa"])
esq.dataframe(achados[achados.severidade.isin(sev)], use_container_width=True, height=380)
dir_.bar_chart(achados.groupby("descricao_regra").size())

st.subheader("Parecer executivo")
if st.button("Gerar parecer"):
    st.session_state["parecer"] = generate_report(resumo, achados, provider)
if "parecer" in st.session_state:
    st.markdown(st.session_state["parecer"])
    st.download_button("Baixar parecer (.md)", st.session_state["parecer"], "parecer.md")
st.download_button("Baixar achados (.csv)", achados.to_csv(index=False), "findings.csv")
