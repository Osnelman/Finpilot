import io
import streamlit as st
from analyse import (charger_transactions, categoriser, bilan_mensuel, comparer_mois,
                     detecter_recurrences, detecter_anomalies, budget_engage,
                     obligations_a_venir, projection_objectif, _depenses)
from agent import repondre, rediger_bilan

st.set_page_config(page_title="FinPilot", page_icon="💰", layout="wide")
st.title("💰 FinPilot")
st.caption("Agent d'aide à la décision en finances personnelles. "
           "Il explique vos données ; il ne donne pas de conseil financier ni d'investissement.")

# ---------- Import ----------
st.sidebar.header("Données")
fichier = st.sidebar.file_uploader("Importer un relevé (CSV)", type=["csv"])
exemple = st.sidebar.checkbox("Utiliser le relevé d'exemple (données fictives)")
st.sidebar.caption("Colonnes attendues : date (AAAA-MM-JJ), libelle, montant "
                   "(FCFA ; positif = entrée, négatif = dépense).")

if fichier is not None:
    source = io.BytesIO(fichier.getvalue())
elif exemple:
    source = "data/transactions.csv"
else:
    st.info("Importez un relevé CSV (ou cochez le relevé d'exemple) dans la barre latérale.")
    st.stop()

try:
    df, avertissements = charger_transactions(source)
except Exception as e:
    st.error(f"Fichier inutilisable : {e}")
    st.stop()
for a in avertissements:
    st.warning(a)
df = categoriser(df)
mois = sorted(df["mois"].unique())

# ---------- Budgets et objectif ----------
st.sidebar.header("Budgets mensuels (FCFA)")
depenses_df = _depenses(df)
moyenne = depenses_df.groupby("categorie")["montant"].sum() / len(mois)
budgets = {}
for c in sorted(depenses_df["categorie"].unique()):
    defaut = int(round(float(moyenne.get(c, 0)), -3))
    budgets[c] = st.sidebar.number_input(c, min_value=0, value=defaut, step=1000, key=f"bud_{c}")

st.sidebar.header("Objectif d'épargne")
obj_montant = st.sidebar.number_input("Montant visé (FCFA)", min_value=0, value=300000, step=10000)
obj_actuel = st.sidebar.number_input("Déjà épargné (FCFA)", min_value=0, value=0, step=10000)
objectif = {"montant": obj_montant, "epargne_actuelle": obj_actuel}

t1, t2, t3, t4, t5, t6 = st.tabs(["Tableau de bord", "Récurrences et échéances", "Budget",
                                  "Objectif d'épargne", "Poser une question", "Bilan mensuel"])

with t1:
    bilan = bilan_mensuel(df)
    st.subheader("Revenus et dépenses par mois (FCFA)")
    st.dataframe(bilan)
    st.bar_chart(bilan.set_index("mois")[["revenus", "depenses"]])
    c1, c2 = st.columns(2)
    with c1:
        m_sel = st.selectbox("Dépenses par catégorie, mois :", mois, index=len(mois) - 1)
        d = _depenses(df)
        st.bar_chart(d[d["mois"] == m_sel].groupby("categorie")["montant"].sum())
    with c2:
        ma = st.selectbox("Comparer : mois de départ", mois, index=max(len(mois) - 2, 0))
        mb = st.selectbox("avec le mois", mois, index=len(mois) - 1)
        st.dataframe(comparer_mois(df, ma, mb))
    st.subheader("Dépenses inhabituelles")
    an = detecter_anomalies(df)
    if an.empty:
        st.write("Aucune dépense inhabituelle détectée.")
    else:
        st.dataframe(an)

with t2:
    st.subheader("Paiements récurrents détectés")
    st.dataframe(detecter_recurrences(df))
    st.subheader("Échéances des 30 prochains jours")
    st.dataframe(obligations_a_venir(df))

with t3:
    m_bud = st.selectbox("Mois :", mois, index=len(mois) - 1, key="mois_budget")
    st.dataframe(budget_engage(df, budgets, m_bud))

with t4:
    eco = st.slider("Économie supplémentaire par mois (FCFA)", 0, 200000, 0, step=5000)
    p = projection_objectif(df, objectif["montant"], objectif["epargne_actuelle"], eco)
    st.metric("Épargne mensuelle moyenne estimée (FCFA)", f"{p['epargne_mensuelle_moyenne']:,}".replace(",", " "))
    if p["mois_necessaires"] is None:
        st.warning("Au rythme actuel, l'objectif n'est pas atteignable. Essayez d'augmenter l'économie mensuelle.")
    elif p["mois_necessaires"] == 0:
        st.success("Objectif déjà atteint.")
    else:
        st.success(f"Objectif atteint en environ {p['mois_necessaires']} mois (vers {p['date_estimee']}).")

with t5:
    exemples = ["Où ai-je le plus dépensé ce mois-ci ?",
                "Pour quels abonnements est-ce que je paie ?",
                "Quelles dépenses ont augmenté par rapport au mois dernier ?",
                "Quelle part de mon budget est déjà engagée ?"]
    choix = st.selectbox("Questions d'exemple", ["(question libre)"] + exemples)
    question = st.text_input("Votre question", value="" if choix.startswith("(") else choix)
    if st.button("Demander") and question.strip():
        with st.spinner("FinPilot analyse..."):
            st.session_state["derniere"] = (question.strip(), *repondre(question.strip(), df, budgets, objectif))
    if "derniere" in st.session_state:
        q, rep, outil, donnees = st.session_state["derniere"]
        st.markdown(f"**Question :** {q}")
        st.write(rep)
        with st.expander("Données utilisées (calculées par le code)"):
            st.text(donnees)

with t6:
    if st.button("Générer le bilan mensuel"):
        with st.spinner("Rédaction du bilan..."):
            st.session_state["bilan_txt"] = rediger_bilan(df, budgets, objectif)
    if "bilan_txt" in st.session_state:
        st.write(st.session_state["bilan_txt"])
        st.download_button("Télécharger le bilan (.txt)", st.session_state["bilan_txt"], file_name="bilan_finpilot.txt")