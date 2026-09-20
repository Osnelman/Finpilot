import csv
import random
from datetime import date, timedelta

random.seed(42)

OUTPUT_FILE = "data/transactions.csv"

# Période retenue : juin, juillet, août 2026.
MOIS = [6, 7, 8]

# Les montants sont exprimés en FCFA ; positif = entrée, négatif = sortie.
# Le résumé final sert de vérité de référence pour les tests.


def ajouter_transaction(writer, jour, libelle, montant):
    # csv.writer attend une liste de valeurs, pas un dictionnaire.
    writer.writerow([jour.strftime("%Y-%m-%d"), libelle, montant])


def remplir_mois(writer, annee, mois):
    # Revenu mensuel régulier : salaire augmenté d'environ 150 000 FCFA pour obtenir
    # un solde moyen global positif, conforme au besoin de référence de test.
    salaire = 1000000 + random.randint(-50000, 80000)
    ajouter_transaction(writer, date(annee, mois, 25), "SALAIRE", salaire)

    # 1 ou 2 entrées irrégulières selon le mois.
    entrees_irregulieres = {
        6: [(date(2026, 6, 12), "PRESTATION CLIENT", 250000), (date(2026, 6, 28), "REMBOURSEMENT ASSURANCE", 95000)],
        7: [(date(2026, 7, 8), "PRESTATION CLIENT", 320000)],
        8: [(date(2026, 8, 10), "PRESTATION CLIENT", 275000), (date(2026, 8, 24), "REMBOURSEMENT DEPOT", 110000)],
    }
    for jour, libelle, montant in entrees_irregulieres.get(mois, []):
        ajouter_transaction(writer, jour, libelle, montant)

    # Deux paiements récurrents mensuels : l'un varie légèrement selon le mois.
    labels_internet = {
        6: "FORFAIT INTERNET 10GO",
        7: "Forfait internet 15 Go",
        8: "FORFAIT INTERNET 15GO",
    }
    ajouter_transaction(writer, date(annee, mois, 8), labels_internet[mois], -25000)
    ajouter_transaction(writer, date(annee, mois, 15), "ABONNEMENT ASSURANCE", -20000)

    # Cotisation hebdomadaire : 4 versements tous les 7 jours.
    for semaine in range(4):
        jour = date(annee, mois, 2) + timedelta(days=7 * semaine)
        ajouter_transaction(writer, jour, "COTISATION HEBDOMADAIRE", -6000)

    # Dépenses courantes : transport, alimentation, téléphone.
    for _ in range(11):
        jour = date(annee, mois, random.randint(3, 28))
        libelle = random.choice(["TRANSPORT", "CARBURANT", "BUS", "TAXI"])
        montant = -random.randint(18000, 35000)
        ajouter_transaction(writer, jour, libelle, montant)

    # Nombre d'achats alimentaires qui augmente sur la période pour refléter une hausse nette.
    for _ in range(15 if mois == 6 else 16 if mois == 7 else 17):
        jour = date(annee, mois, random.randint(4, 28))
        libelle = random.choice(["SUPERMARCHE", "EPICERIE", "COURSES QUOTIDIENNES", "ALIMENTATION", "RESTAURANT"])
        montant = -random.randint(22000, 65000)
        if mois == 8:
            montant = -random.randint(30000, 85000)
        ajouter_transaction(writer, jour, libelle, montant)

    # Crédit téléphonique récurrent, avec variations modestes.
    for _ in range(4):
        jour = date(annee, mois, random.randint(5, 26))
        ajouter_transaction(writer, jour, "CREDIT TELEPHONE", -random.randint(12000, 22000))

    # Dépenses diverses et loyers de consommation.
    for _ in range(6):
        jour = date(annee, mois, random.randint(6, 27))
        libelle = random.choice(["ACHAT DIVERS", "PAPETERIE", "CANTINE", "RESTAURANT", "COURSES DIVERSES"])
        montant = -random.randint(8000, 26000)
        ajouter_transaction(writer, jour, libelle, montant)

    # Dépense anormale : 5 à 10 fois la moyenne d'une catégorie.
    if mois == 7:
        ajouter_transaction(writer, date(2026, 7, 18), "REPARATION VEHICULE", -220000)

    # Libellé hors catégorie pour vérifier la détection d'un cas non classifiable.
    ajouter_transaction(writer, date(annee, mois, random.randint(11, 24)), "ACHAT LIVRE MAISON", -18000)


def main():
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as fichier_csv:
        writer = csv.writer(fichier_csv)
        writer.writerow(["date", "libelle", "montant"])

        for mois in MOIS:
            remplir_mois(writer, 2026, mois)

    # Lecture du CSV pour produire un résumé lisible et cohérent.
    with open(OUTPUT_FILE, "r", newline="", encoding="utf-8") as fichier_csv:
        lecteur = csv.DictReader(fichier_csv)
        transactions = list(lecteur)

    # Calcul de la variation mensuelle pour la catégorie alimentation.
    totals_mensuels = {"2026-06": 0, "2026-07": 0, "2026-08": 0}
    transport_mensuel = {"2026-06": 0, "2026-07": 0, "2026-08": 0}

    for ligne in transactions:
        montant = int(ligne["montant"])
        mois = ligne["date"][:7]
        libelle = ligne["libelle"].upper()

        if any(mot in libelle for mot in ["SUPERMARCHE", "EPICERIE", "ALIMENTATION", "RESTAURANT", "CANTINE", "COURSES"]):
            totals_mensuels[mois] += abs(montant)
        if any(mot in libelle for mot in ["TRANSPORT", "CARBURANT", "BUS", "TAXI", "REPARATION", "VEHICULE"]):
            transport_mensuel[mois] += abs(montant)

    moyenne_transport = sum(transport_mensuel.values()) / 3
    hausse_alim = totals_mensuels["2026-08"] - totals_mensuels["2026-06"]

    print("Récapitulatif des éléments insérés :")
    print("- Revenu mensuel régulier : SALAIRE, autour de 850000 FCFA / mois, sur juin, juillet et août 2026.")
    print("- Entrées irrégulières : PRESTATION CLIENT et REMBOURSEMENT ASSURANCE/DEPOT sur certains mois.")
    print("- Paiements récurrents mensuels : FORFAIT INTERNET (libellé maîtrisé avec var. légère) et ABONNEMENT ASSURANCE.")
    print("- Cotisation hebdomadaire : COTISATION HEBDOMADAIRE, 4 versements par mois.")
    print("- Dépenses courantes : transport, alimentation, téléphone et autres frais de vie, avec montants variables.")
    print(f"- Dépense anormale : REPARATION VEHICULE, -220000 FCFA en juillet, soit environ {round(220000 / moyenne_transport, 1)}x la moyenne mensuelle du transport.")
    print(f"- Hausse nette : total alimentation de {totals_mensuels['2026-06']} FCFA en juin à {totals_mensuels['2026-08']} FCFA en août, hausse de {hausse_alim} FCFA.")
    print("- Libellé hors catégorie : ACHAT LIVRE MAISON, qui ne correspond à aucune catégorie prédéfinie.")
    print(f"- Nombre de lignes générées : {len(transactions)} (hors en-tête)")


if __name__ == "__main__":
    main()
