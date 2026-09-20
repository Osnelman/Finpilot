# analyse.py
import pandas as pd
import math
COLONNES_REQUISES = {"date", "libelle", "montant"}


def charger_transactions(source):
    """Lit un CSV de transactions (chemin ou fichier importé) et le nettoie.

    Convention : montant > 0 = entrée d'argent, montant < 0 = dépense.
    Retourne (df, avertissements). Lève ValueError si le fichier est inutilisable.
    """
    try:
        # sep=None : détecte automatiquement « , » ou « ; »
        # utf-8-sig : accepte aussi les fichiers enregistrés avec BOM (Excel)
        df = pd.read_csv(source, sep=None, engine="python", encoding="utf-8-sig")
    except pd.errors.EmptyDataError:
        raise ValueError("Le fichier est vide.")
    except UnicodeDecodeError:
        raise ValueError("Encodage non reconnu : enregistrez le fichier en UTF-8.")

    df.columns = [str(c).strip().lower() for c in df.columns]
    manquantes = COLONNES_REQUISES - set(df.columns)
    if manquantes:
        raise ValueError(
            f"Colonnes manquantes : {', '.join(sorted(manquantes))}. "
            "Colonnes attendues : date, libelle, montant."
        )

    df = df[["date", "libelle", "montant"]].copy()
    n_initial = len(df)

    # Les valeurs illisibles deviennent NaT / NaN, puis sont écartées
    df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d", errors="coerce")
    df["montant"] = pd.to_numeric(df["montant"], errors="coerce")
    df["libelle"] = df["libelle"].fillna("").astype(str)
    df = df.dropna(subset=["date", "montant"])

    if df.empty:
        raise ValueError("Aucune ligne valide (dates AAAA-MM-JJ et montants numériques attendus).")

    avertissements = []
    n_ignorees = n_initial - len(df)
    if n_ignorees:
        avertissements.append(f"{n_ignorees} ligne(s) ignorée(s) (date ou montant illisible).")

    # Libellé normalisé : minuscules, espaces multiples réduits
    df["libelle_norm"] = (
        df["libelle"].str.lower().str.replace(r"\s+", " ", regex=True).str.strip()
    )
    # Clé de regroupement sans chiffres : « forfait 10go » et « Forfait 15 Go » coïncident
    df["cle"] = (
        df["libelle_norm"].str.replace(r"\d+", "", regex=True)
        .str.replace(r"\s+", " ", regex=True).str.strip()
    )
    df["mois"] = df["date"].dt.to_period("M").astype(str)  # ex. « 2026-07 »

    return df.sort_values("date").reset_index(drop=True), avertissements


def categoriser(df):
    """Ajoute une colonne `categorie` à partir du libellé de la transaction."""
    d = df.copy()
    d["libelle_norm"] = (
        d["libelle"].fillna("").astype(str).str.lower().str.replace(r"\s+", " ", regex=True).str.strip()
    )

    def categorie_par_libelle(libelle):
        texte = str(libelle).upper()

        if any(m in texte for m in ["SALAIRE", "PRESTATION", "REMBOURSEMENT"]):
            return "Revenu"
        if any(m in texte for m in ["FORFAIT INTERNET", "INTERNET", "ABONNEMENT INTERNET"]):
            return "Internet"
        if any(m in texte for m in ["ASSURANCE", "ABONNEMENT", "PRET"]):
            return "Assurance"
        if "COTISATION" in texte:
            return "Cotisation"
        if any(m in texte for m in ["TRANSPORT", "CARBURANT", "BUS", "TAXI", "MOTO", "REPARATION", "VEHICULE"]):
            return "Transport"
        if any(m in texte for m in ["SUPERMARCHE", "EPICERIE", "ALIMENTATION", "COURSE", "RESTAURANT", "CANTINE", "COURSES"]):
            return "Alimentation"
        if any(m in texte for m in ["TELEPHONE", "CREDIT", "TEL"]):
            return "Telephone"
        return "Autre"

    d["categorie"] = d["libelle_norm"].apply(categorie_par_libelle)
    return d


def bilan_mensuel(df):
    d = df.copy()
    if "mois" not in d.columns:
        d["date"] = pd.to_datetime(d["date"])
        d["mois"] = d["date"].dt.to_period("M").astype(str)
    d["revenus"] = d["montant"].where(d["montant"] > 0, 0)
    d["depenses"] = (-d["montant"]).where(d["montant"] < 0, 0)
    bilan = d.groupby("mois", as_index=False)[["revenus", "depenses"]].sum()
    bilan["solde"] = bilan["revenus"] - bilan["depenses"]
    return bilan.sort_values("mois").reset_index(drop=True)


def _depenses(df):
    """Dépenses uniquement, montants en valeur positive."""
    d = df[df["montant"] < 0].copy()
    d["montant"] = d["montant"].abs()
    return d


def comparer_mois(df, mois_a, mois_b):
    """Dépenses par catégorie : mois_a vs mois_b, la plus forte hausse en premier."""
    d = _depenses(df)
    a = d[d["mois"] == mois_a].groupby("categorie")["montant"].sum()
    b = d[d["mois"] == mois_b].groupby("categorie")["montant"].sum()
    res = pd.DataFrame({"mois_a": a, "mois_b": b}).fillna(0)
    res["difference"] = res["mois_b"] - res["mois_a"]
    # mois_a == 0 : pourcentage non défini (NaN)
    res["variation_pct"] = (
        res["difference"] / res["mois_a"].replace(0, float("nan")) * 100
    ).round(1)
    res = res.sort_values("difference", ascending=False)
    res.index.name = "categorie"
    return res.reset_index()


COLS_REC = ["libelle", "frequence", "occurrences", "montant_moyen",
            "derniere_date", "prochaine_date", "ecart_jours", "cout_mensuel_estime"]


def detecter_recurrences(df, min_occ=3, tol_montant=0.45):
    """Paiements récurrents (hebdomadaires ou mensuels), regroupés par libellé sans chiffres."""
    d = _depenses(df)
    lignes = []
    for cle, g in d.groupby("cle"):
        if not cle or len(g) < min_occ:
            continue
        g = g.sort_values("date")
        ecarts = g["date"].diff().dt.days.dropna()
        if ecarts.empty:
            continue

        # Règle tolérante : 75 % des écarts proches d'une fréquence donnée suffisent.
        proche7 = ((ecarts - 7).abs() <= 7 * 0.75).mean()
        proche30 = ((ecarts - 30).abs() <= 30 * 0.75).mean()

        if proche7 >= 0.75:
            freq, facteur = "hebdomadaire", 52 / 12
            pas = 7
        elif proche30 >= 0.75:
            freq, facteur = "mensuelle", 1
            pas = 30
        else:
            continue

        med = g["montant"].median()
        if med == 0:
            continue
        if (g["montant"].max() - g["montant"].min()) / med > tol_montant:
            continue
        moy = g["montant"].mean()
        lignes.append({
            "libelle": g["libelle"].iloc[-1],
            "frequence": freq,
            "occurrences": len(g),
            "montant_moyen": round(moy),
            "derniere_date": g["date"].max(),
            "prochaine_date": g["date"].max() + pd.Timedelta(days=pas),
            "ecart_jours": pas,
            "cout_mensuel_estime": round(moy * facteur),
        })
    res = pd.DataFrame(lignes, columns=COLS_REC)
    return res.sort_values("cout_mensuel_estime", ascending=False).reset_index(drop=True)


def detecter_anomalies(df, seuil=3.0, min_obs=5):
    """Dépenses au moins `seuil` fois supérieures à la médiane de leur catégorie."""
    d = _depenses(df)
    d["mediane_categorie"] = d.groupby("categorie")["montant"].transform("median")
    d["nb_cat"] = d.groupby("categorie")["montant"].transform("count")
    d["ratio"] = (d["montant"] / d["mediane_categorie"]).round(1)
    a = d[(d["nb_cat"] >= min_obs) & (d["ratio"] >= seuil)]
    cols = ["date", "libelle", "categorie", "montant", "mediane_categorie", "ratio"]
    return a.sort_values("ratio", ascending=False)[cols].reset_index(drop=True)


def _statut(r):
    if r["budget"] == 0:
        return "sans budget" if r["depense"] > 0 else "ok"
    return "dépassé" if r["depense"] > r["budget"] else "ok"


def budget_engage(df, budgets, mois):
    """Dépenses réelles du mois vs budgets. budgets = {"Transport": 20000, ...}"""
    d = _depenses(df)
    reel = d[d["mois"] == mois].groupby("categorie")["montant"].sum()
    res = pd.DataFrame({"budget": pd.Series(budgets, dtype="float64"), "depense": reel}).fillna(0)
    res["reste"] = res["budget"] - res["depense"]
    res["pct_utilise"] = (
        res["depense"] / res["budget"].replace(0, float("nan")) * 100
    ).round(1)
    res["statut"] = res.apply(_statut, axis=1)
    res.index.name = "categorie"
    return res.reset_index()


def obligations_a_venir(df, jours=30, date_ref=None):
    """Paiements récurrents prévus dans les `jours` jours après date_ref (par défaut : dernière date du fichier)."""
    rec = detecter_recurrences(df)
    ref = pd.Timestamp(date_ref) if date_ref else df["date"].max()
    fin = ref + pd.Timedelta(days=jours)
    lignes = []
    for _, r in rec.iterrows():
        pas = pd.Timedelta(days=int(r["ecart_jours"]))
        d = r["prochaine_date"]
        while d <= fin:
            if d > ref:
                lignes.append({"libelle": r["libelle"], "date_prevue": d,
                               "montant_estime": r["montant_moyen"]})
            d += pas
    res = pd.DataFrame(lignes, columns=["libelle", "date_prevue", "montant_estime"])
    return res.sort_values("date_prevue").reset_index(drop=True)


def projection_objectif(df, objectif, epargne_actuelle=0, economie_supplementaire=0):
    """Estime le nombre de mois pour atteindre un objectif d'épargne, au rythme moyen observé."""
    bilan = bilan_mensuel(df)
    epargne_mensuelle = float(bilan["solde"].mean()) + economie_supplementaire
    reste = max(objectif - epargne_actuelle, 0)
    if reste == 0:
        mois_necessaires = 0
    elif epargne_mensuelle <= 0:
        mois_necessaires = None  # objectif inatteignable à ce rythme
    else:
        mois_necessaires = math.ceil(reste / epargne_mensuelle)
    date_estimee = None
    if mois_necessaires is not None:
        date_estimee = str(pd.Period(df["mois"].max(), freq="M") + mois_necessaires)
    return {
        "epargne_mensuelle_moyenne": int(round(epargne_mensuelle)),
        "reste_a_epargner": reste,
        "mois_necessaires": mois_necessaires,
        "date_estimee": date_estimee,
    }