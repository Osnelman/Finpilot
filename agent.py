import json
import pandas as pd
from analyse import (bilan_mensuel, comparer_mois, detecter_recurrences, detecter_anomalies,
                     budget_engage, obligations_a_venir, projection_objectif, _depenses)
from llm import demander_llm

OUTILS = {
    "depenses_par_categorie": "total des dépenses par catégorie, du plus élevé au plus faible. Paramètre optionnel : mois (AAAA-MM), sinon toute la période.",
    "abonnements": "paiements récurrents (abonnements, forfaits, cotisations) avec montant et prochaine date.",
    "comparer_mois": "évolution des dépenses par catégorie entre deux mois. Paramètres : mois_a (le plus ancien) et mois_b (AAAA-MM).",
    "budget": "dépenses réelles d'un mois comparées aux budgets définis. Paramètre optionnel : mois (AAAA-MM).",
    "anomalies": "dépenses inhabituellement élevées.",
    "echeances": "paiements récurrents attendus dans les 30 prochains jours.",
    "objectif": "projection de l'objectif d'épargne.",
    "bilan": "revenus, dépenses et solde par mois.",
}


def _txt(titre, res):
    if isinstance(res, pd.DataFrame):
        corps = "(aucun résultat)" if res.empty else res.to_string(index=False)
    else:
        corps = json.dumps(res, ensure_ascii=False, default=str)
    return f"{titre}\n{corps}"


def executer_outil(nom, params, df, budgets, objectif):
    mois = sorted(df["mois"].unique())
    dernier = mois[-1]
    avant = mois[-2] if len(mois) > 1 else mois[-1]
    p = params if isinstance(params, dict) else {}

    def m(cle, defaut):
        v = p.get(cle)
        return v if v in mois else defaut

    if nom == "depenses_par_categorie":
        mm = m("mois", None)
        d = _depenses(df)
        if mm:
            d = d[d["mois"] == mm]
        res = d.groupby("categorie")["montant"].sum().sort_values(ascending=False).reset_index()
        return _txt(f"Dépenses par catégorie ({mm or 'toute la période'}), en FCFA", res)
    if nom == "abonnements":
        return _txt("Paiements récurrents détectés (FCFA)", detecter_recurrences(df))
    if nom == "comparer_mois":
        a, b = m("mois_a", avant), m("mois_b", dernier)
        return _txt(f"Dépenses par catégorie : {a} (mois_a) puis {b} (mois_b), en FCFA", comparer_mois(df, a, b))
    if nom == "budget":
        mm = m("mois", dernier)
        return _txt(f"Budget contre dépenses réelles, {mm} (FCFA)", budget_engage(df, budgets, mm))
    if nom == "anomalies":
        return _txt("Dépenses inhabituellement élevées (FCFA)", detecter_anomalies(df))
    if nom == "echeances":
        return _txt("Paiements attendus dans les 30 prochains jours (FCFA)", obligations_a_venir(df))
    if nom == "objectif":
        return _txt("Projection de l'objectif d'épargne (FCFA)",
                    projection_objectif(df, objectif["montant"], objectif["epargne_actuelle"]))
    if nom == "bilan":
        return _txt("Bilan mensuel (FCFA)", bilan_mensuel(df))
    return "Outil inconnu."


def routage_secours(question):
    q = question.lower()
    regles = [
        (["abonnement", "récurrent", "recurrent", "forfait"], "abonnements"),
        (["augment", "compar", "hausse", "évolu", "evolu"], "comparer_mois"),
        (["budget", "engag"], "budget"),
        (["anormal", "inhabituel", "suspect"], "anomalies"),
        (["échéance", "echeance", "à venir", "a venir", "prochain"], "echeances"),
        (["objectif", "épargn", "epargn"], "objectif"),
        (["bilan", "solde", "revenu"], "bilan"),
    ]
    for mots, outil in regles:
        if any(mot in q for mot in mots):
            return outil, {}
    return "depenses_par_categorie", {}


def choisir_outil(question, mois):
    dernier = mois[-1]
    avant = mois[-2] if len(mois) > 1 else mois[-1]
    liste = "\n".join(f"- {n} : {d}" for n, d in OUTILS.items())
    prompt = f"""Tu es le routeur d'un assistant de finances personnelles. Choisis l'outil qui répond à la question.
Outils :
{liste}
Mois disponibles : {', '.join(mois)}. « Ce mois-ci » = {dernier}. « Le mois dernier » = {avant}.
Réponds UNIQUEMENT par un objet JSON de la forme {{"outil": "<nom>", "parametres": {{}}}}.
Question : {question}"""
    try:
        brut = demander_llm(prompt, json_mode=True)
        data = json.loads(brut[brut.find("{"): brut.rfind("}") + 1])
        if data.get("outil") in OUTILS:
            return data["outil"], data.get("parametres", {})
    except Exception:
        pass
    return routage_secours(question)


def repondre(question, df, budgets, objectif):
    """Retourne (réponse, nom de l'outil, données utilisées)."""
    mois = sorted(df["mois"].unique())
    nom, params = choisir_outil(question, mois)
    donnees = executer_outil(nom, params, df, budgets, objectif)
    prompt = f"""Tu es FinPilot, assistant d'analyse de finances personnelles. Réponds en français, clairement, en 5 phrases maximum.
Règles : utilise UNIQUEMENT les chiffres des données ci-dessous, n'invente aucun nombre, ne fais aucun calcul nouveau, donne les montants en FCFA. Ne donne aucun conseil financier ni d'investissement : explique seulement ce que montrent les données.
Question : {question}
Données ({nom}) :
{donnees}"""
    try:
        rep = demander_llm(prompt).strip()
    except Exception as e:
        rep = f"Le modèle IA est indisponible ({type(e).__name__}). Voici les données calculées par FinPilot."
    return rep, nom, donnees


def rediger_bilan(df, budgets, objectif):
    mois = sorted(df["mois"].unique())
    dernier = mois[-1]
    avant = mois[-2] if len(mois) > 1 else mois[-1]
    blocs = [
        executer_outil("bilan", {}, df, budgets, objectif),
        executer_outil("depenses_par_categorie", {"mois": dernier}, df, budgets, objectif),
        executer_outil("comparer_mois", {"mois_a": avant, "mois_b": dernier}, df, budgets, objectif),
        executer_outil("abonnements", {}, df, budgets, objectif),
        executer_outil("anomalies", {}, df, budgets, objectif),
        executer_outil("echeances", {}, df, budgets, objectif),
        executer_outil("budget", {"mois": dernier}, df, budgets, objectif),
        executer_outil("objectif", {}, df, budgets, objectif),
    ]
    donnees = "\n\n".join(blocs)
    prompt = f"""Tu es FinPilot. Rédige en français le bilan financier du mois {dernier} (300 mots maximum) avec 4 parties : 1) Résumé (revenus, dépenses, solde) ; 2) Observations clés ; 3) Points d'attention (anomalies, dépassements de budget, échéances) ; 4) Actions à mener (3 actions concrètes, par exemple vérifier une dépense ou revoir un budget).
Règles : utilise UNIQUEMENT les chiffres fournis, n'invente aucun nombre, montants en FCFA, aucun conseil d'investissement.
Données :
{donnees}"""
    try:
        return demander_llm(prompt).strip()
    except Exception as e:
        return f"Le modèle IA est indisponible ({type(e).__name__}). Données calculées :\n\n{donnees}"