# streamlit_app.py
# Dashboard com 4 páginas:
# 1) Hemo 8R (KPIs + gráficos)
# 2) Emicizumabe (HB/ROCHE – leitura)
# 3) Aquisições – Coagulopatias (MS) (gráficos + filtro por medicamento)
# 4) Emicizumabe – Pacientes (somente TABELA, sem cálculos)

import re
import datetime as dt
import pandas as pd
import streamlit as st
import altair as alt

st.set_page_config(page_title="I.M - HB", layout="wide")

# ==========================
# Utilidades
# ==========================
@st.cache_data(show_spinner=False)
def load_csv_auto(path: str) -> pd.DataFrame:
    for sep in (";", ",", None):
        try:
            if sep is None:
                return pd.read_csv(path, sep=None, engine="python", dtype=str)
            return pd.read_csv(path, sep=sep, dtype=str)
        except Exception:
            continue
    raise RuntimeError(f"Falha ao ler CSV: {path}")

def to_num(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .fillna("0")
        .str.replace(r"\.", "", regex=True)
        .str.replace(",", ".", regex=False)
        .str.strip()
        .replace({"": "0"})
        .pipe(pd.to_numeric, errors="coerce")
        .fillna(0)
    )

# ==========================
# Página: Emicizumabe (HB/ROCHE) – leitura simples
# ==========================
def page_emicizumabe():
    st.title("Emicizumabe – Tabelas HB e ROCHE")

    PATH_HB = "dados_emicizumabe_HB.csv"
    PATH_ROCHE = "dados_emicizumabe_ROCHE.csv"

    try:
        df_hb = load_csv_auto(PATH_HB)
        df_roche = load_csv_auto(PATH_ROCHE)
    except Exception as e:
        st.error(f"Erro ao carregar CSVs: {e}")
        st.stop()

    tab_hb, tab_roche = st.tabs(["Hemobrás (UI)", "ROCHE (mg)"])

    with tab_hb:
        st.subheader("Cenário Hemobrás (UI)")
        st.data_editor(
            df_hb,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            disabled=True,
        )

    with tab_roche:
        st.subheader("Cenário ROCHE (mg)")
        st.data_editor(
            df_roche,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            disabled=True,
        )

# ==========================
# Página: Hemo 8R
# ==========================
@st.cache_data(show_spinner=False)
def load_ms_data(path_csv: str = "hemo8R_MS.csv"):
    df = pd.read_csv(path_csv, sep=";", dtype=str)
    df = df.rename(columns={"ano": "Ano", "quantidade": "Quantidade"})
    df["Ano"] = pd.to_numeric(df["Ano"], errors="coerce")
    df["Quantidade"] = pd.to_numeric(df["Quantidade"], errors="coerce")
    df = df.dropna().sort_values("Ano")
    return df

@st.cache_data(show_spinner=False)
def load_hemo8r_servicos(path_csv: str):
    df = pd.read_csv(path_csv, sep=";", dtype=str)
    ui_cols = ["250 UI", "500 UI", "1000 UI", "1500 UI", "Total Geral"]
    base_cols = ["Período de saída", "Serviço de Saúde"] + ui_cols
    df = df[base_cols]

    for c in ui_cols:
        df[c] = to_num(df[c]).astype(int)

    meses = {
        "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4,
        "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
        "outubro": 10, "novembro": 11, "dezembro": 12
    }

    def parse_periodo(s):
        s = str(s).strip().lower()
        m = re.match(r"([a-zç]+)\/?(\d{2}|\d{4})", s)
        if not m:
            return pd.NaT
        mon = m.group(1).replace("ç", "c")
        ano = int(m.group(2))
        ano = 2000 + ano if ano < 100 else ano
        mes = meses.get(mon)
        if not mes:
            return pd.NaT
        return dt.date(ano, mes, 1)

    df["periodo"] = df["Período de saída"].apply(parse_periodo)
    df = df.dropna(subset=["periodo"]).copy()
    return df, ui_cols

def page_hemo8r():
    st.title("Hemo 8R")

    st.subheader("Distribuição – Ministério da Saúde")
    try:
        df_ms = load_ms_data("hemo8R_MS.csv")
    except Exception as e:
        st.warning(f"Erro ao carregar hemo8R_MS.csv: {e}")
        df_ms = pd.DataFrame()

    if not df_ms.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("De", str(df_ms["Ano"].min()))
        c2.metric("Até", str(df_ms["Ano"].max()))
        c3.metric("Total distribuído (UI)", f"{int(df_ms['Quantidade'].sum()):,}".replace(",", "."))

        chart_ms = (
            alt.Chart(df_ms)
            .mark_bar()
            .encode(
                x=alt.X("Ano:O", title="Ano"),
                y=alt.Y("Quantidade:Q", title="Quantidade (UI)", axis=alt.Axis(format=",.0f")),
                tooltip=[alt.Tooltip("Ano:O"), alt.Tooltip("Quantidade:Q", format=",.0f")]
            )
            .properties(height=380)
        )
        st.altair_chart(chart_ms, use_container_width=True)
        with st.expander("Ver dados do MS"):
            st.dataframe(df_ms, use_container_width=True)
    else:
        st.info("Sem dados do MS.")

    st.subheader("Distribuição – Serviços de Saúde")
    DATA_PATH = "historico_hemo8r.csv"
    try:
        df, ui_cols = load_hemo8r_servicos(DATA_PATH)
    except Exception as e:
        st.error(f"Erro ao carregar {DATA_PATH}: {e}")
        st.stop()

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("De", df["periodo"].min().strftime("%b/%Y"))
    col2.metric("Até", df["periodo"].max().strftime("%b/%Y"))
    col3.metric("Serviços", f"{df['Serviço de Saúde'].nunique():,}".replace(",", "."))
    col4.metric("Volume total (UI)", f"{int(df['Total Geral'].sum()):,}".replace(",", "."))
    col5.metric("Registros", f"{len(df):,}".replace(",", "."))

    st.subheader("Evolução mensal por UI")
    monthly = df.groupby("periodo")[ui_cols].sum().sort_index()
    st.line_chart(monthly)

    st.subheader("Top serviços por volume total (UI)")
    top_n = st.slider("Quantos serviços exibir?", 5, 31, 15, key="n_top_hemo")
    rank = (
        df.groupby("Serviço de Saúde")["Total Geral"]
        .sum()
        .reset_index()
        .sort_values("Total Geral", ascending=False)
        .head(top_n)
    )
    chart = (
        alt.Chart(rank)
        .mark_bar()
        .encode(
            x=alt.X("Serviço de Saúde:N", sort=rank["Serviço de Saúde"].tolist(), title="Serviço"),
            y=alt.Y("Total Geral:Q", title="Volume total (UI)", axis=alt.Axis(format=",.0f")),
            tooltip=["Serviço de Saúde", alt.Tooltip("Total Geral:Q", format=",.0f")]
        )
        .properties(height=400)
    )
    st.altair_chart(chart, use_container_width=True)
    with st.expander("Ver amostra dos dados tratados"):
        st.dataframe(df, use_container_width=True)

# ==========================
# Página: Aquisições – Coagulopatias (MS)
# ==========================
@st.cache_data(show_spinner=False)
def load_coagulopatias_data(path_csv: str = "medicamentos_coagulopatias.csv"):
    df_raw = pd.read_csv(path_csv, sep=";", dtype=str)
    year_cols = [c for c in df_raw.columns if c.lower() != "medicamento"]
    df = df_raw.melt(
        id_vars="medicamento",
        value_vars=year_cols,
        var_name="Ano",
        value_name="Quantidade"
    )
    df["Ano"] = pd.to_numeric(df["Ano"], errors="coerce")
    df["Quantidade"] = to_num(df["Quantidade"])
    df = df.dropna(subset=["Ano"])
    df["Ano"] = df["Ano"].astype(int)
    df = df.sort_values(["Ano", "medicamento"])
    return df

def page_aquisicoes_ms():
    st.title("Aquisições – Medicamentos para Coagulopatias (MS)")

    try:
        df = load_coagulopatias_data("medicamentos_coagulopatias.csv")
    except Exception as e:
        st.error(f"Erro ao carregar medicamentos_coagulopatias.csv: {e}")
        st.stop()

    if df.empty:
        st.warning("Planilha vazia.")
        st.stop()

    # ----- Filtro por medicamento (barra lateral) -----
    with st.sidebar:
        st.subheader("Filtros – Aquisições (MS)")
        meds = sorted(df["medicamento"].unique().tolist())
        sel_meds = st.multiselect(
            "Filtrar por medicamento",
            options=meds,
            default=meds,
        )

    if not sel_meds:
        st.info("Selecione pelo menos um medicamento para visualizar os gráficos.")
        st.stop()

    df_filtrado = df[df["medicamento"].isin(sel_meds)].copy()

    # KPIs (após filtro)
    anos = sorted(df_filtrado["Ano"].unique())
    ano_min, ano_max = int(min(anos)), int(max(anos))
    total_geral = int(df_filtrado["Quantidade"].sum())
    num_meds = df_filtrado["medicamento"].nunique()

    c1, c2, c3 = st.columns(3)
    c1.metric("Período", f"{ano_min}–{ano_max}")
    c2.metric("Medicamentos distintos", str(num_meds))
    c3.metric("Total adquirido", f"{total_geral:,}".replace(",", "."))

    st.markdown("---")

    # Gráfico: total anual (após filtro)
    st.subheader("Total anual (medicamentos selecionados)")
    total_anual = (
        df_filtrado.groupby("Ano", as_index=False)["Quantidade"]
        .sum()
        .sort_values("Ano")
    )
    chart_total_anual = (
        alt.Chart(total_anual)
        .mark_bar()
        .encode(
            x=alt.X("Ano:O", title="Ano"),
            y=alt.Y("Quantidade:Q", title="Quantidade total", axis=alt.Axis(format=",.0f")),
            tooltip=[alt.Tooltip("Ano:O"), alt.Tooltip("Quantidade:Q", format=",.0f")]
        )
        .properties(height=360)
    )
    st.altair_chart(chart_total_anual, use_container_width=True)

    # Gráfico: composição por medicamento (após filtro)
    st.subheader("Composição por medicamento (barras empilhadas)")
    comp_anual = (
        df_filtrado.groupby(["Ano", "medicamento"], as_index=False)["Quantidade"]
        .sum()
    )
    chart_stack = (
        alt.Chart(comp_anual)
        .mark_bar()
        .encode(
            x=alt.X("Ano:O", title="Ano"),
            y=alt.Y("Quantidade:Q", title="Quantidade", axis=alt.Axis(format=",.0f")),
            color=alt.Color("medicamento:N", title="Medicamento"),
            tooltip=[
                alt.Tooltip("Ano:O", title="Ano"),
                alt.Tooltip("medicamento:N", title="Medicamento"),
                alt.Tooltip("Quantidade:Q", title="Quantidade", format=",.0f"),
            ],
        )
        .properties(height=400)
    )
    st.altair_chart(chart_stack, use_container_width=True)

    with st.expander("Ver dados (após filtro)"):
        st.dataframe(df_filtrado.sort_values(["Ano", "medicamento"]), use_container_width=True)

# ==========================
# NOVA Página: Emicizumabe – Pacientes (SOMENTE TABELA)
# ==========================
def page_emicizumabe_pacientes():
    st.title("Emicizumabe – Pacientes")
    PATH = "emicizumane_pacientes.csv"  # mantenha este nome exatamente, ou ajuste aqui

    try:
        df = load_csv_auto(PATH)
    except Exception as e:
        st.error(f"Erro ao carregar {PATH}: {e}")
        st.stop()

    st.data_editor(
        df,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        disabled=True,  # leitura apenas
    )

# ==========================
# Navegação
# ==========================
with st.sidebar:
    st.header("Navegação")
    page = st.radio(
        "Escolha a página",
        options=[
            "Hemo 8R",
            "Emicizumabe",
            "Aquisições – Coagulopatias (MS)",
            "Emicizumabe – Pacientes"
        ],
        index=0,
    )

# Router
if page == "Hemo 8R":
    page_hemo8r()
elif page == "Emicizumabe":
    page_emicizumabe()
elif page == "Aquisições – Coagulopatias (MS)":
    page_aquisicoes_ms()
else:
    page_emicizumabe_pacientes()
