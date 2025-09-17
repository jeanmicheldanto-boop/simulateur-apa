# app.py — Calculateur GIR + APA/Participation + coûts par mode (MVP intégré aux règles)
# -----------------------------------------------------------------------------
# ⚠️ Prototype pédagogique. Les règles proviennent de votre fiche « Calcul-APA »
# (MTP, plafonds par GIR, règle de participation et division des revenus par 1,7
# en couple). Les valeurs réelles doivent être revérifiées et datées.
# -----------------------------------------------------------------------------

import streamlit as st
import pandas as pd
from typing import Dict, Tuple
import pathlib, json, yaml

st.set_page_config(
    page_title="Estim'Autonomie — GIR • APA • Coût par mode",
    page_icon="🧭",
    layout="centered",
)

st.title("🧭 Estim'Autonomie — Évaluer le GIR, estimer l'APA et le reste à charge")
st.caption("Prototype. Les règles de calcul sont paramétrables via un fichier `config.yaml` à côté de `app.py`.")

# -----------------------------------------------------------------------------
# Chargement configuration (MTP + plafonds)
# -----------------------------------------------------------------------------

DEFAULT_CFG = {
    "mtp": 1365.08,  # Montant de la MTP (mensuel)
    "plafonds_multiplicateurs": {  # Plafond APA = coef * MTP
        1: 1.615,
        2: 1.306,
        3: 0.944,
        4: 0.630,
    },
}

CFG_PATHS = [pathlib.Path("config.yaml"), pathlib.Path("config.yml"), pathlib.Path("config.json")]

def load_cfg() -> dict:
    for p in CFG_PATHS:
        if p.exists():
            try:
                if p.suffix in (".yaml", ".yml"):
                    return yaml.safe_load(p.read_text(encoding="utf-8")) or DEFAULT_CFG
                if p.suffix == ".json":
                    return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
    return DEFAULT_CFG

CFG = load_cfg()
MTP = float(CFG.get("mtp", DEFAULT_CFG["mtp"]))
PLAF_COEF = {int(k): float(v) for k, v in CFG.get("plafonds_multiplicateurs", DEFAULT_CFG["plafonds_multiplicateurs"]).items()}

# -----------------------------------------------------------------------------
# Données de démonstration pour coûts / dépenses par département
# -----------------------------------------------------------------------------
DATA_COST = pd.DataFrame([
    {"dept": "75 - Paris", "mode": "Emploi direct", "cout_horaire": 14.0, "depense_annuelle": 3200.0},
    {"dept": "75 - Paris", "mode": "SAAD - mandataire", "cout_horaire": 22.0, "depense_annuelle": 4500.0},
    {"dept": "75 - Paris", "mode": "SAAD - prestataire", "cout_horaire": 28.0, "depense_annuelle": 6200.0},
    {"dept": "62 - Pas-de-Calais", "mode": "Emploi direct", "cout_horaire": 13.5, "depense_annuelle": 3000.0},
    {"dept": "62 - Pas-de-Calais", "mode": "SAAD - mandataire", "cout_horaire": 21.0, "depense_annuelle": 4300.0},
    {"dept": "62 - Pas-de-Calais", "mode": "SAAD - prestataire", "cout_horaire": 26.0, "depense_annuelle": 5800.0},
    {"dept": "69 - Rhône", "mode": "Emploi direct", "cout_horaire": 14.2, "depense_annuelle": 3300.0},
    {"dept": "69 - Rhône", "mode": "SAAD - mandataire", "cout_horaire": 22.5, "depense_annuelle": 4700.0},
    {"dept": "69 - Rhône", "mode": "SAAD - prestataire", "cout_horaire": 29.0, "depense_annuelle": 6400.0},
])

DEPARTEMENTS = sorted(DATA_COST["dept"].unique().tolist())
MODES = ["Emploi direct", "SAAD - mandataire", "SAAD - prestataire"]

# -----------------------------------------------------------------------------
# A. Évaluation GIR — MVP simplifié (comme avant)
# -----------------------------------------------------------------------------
AGGIR_ITEMS = [
    ("Cohérence", "Comprendre/exprimer, comportements adaptés"),
    ("Orientation", "Se repérer dans le temps/espace"),
    ("Toilette", "Se laver"),
    ("Habillage", "S'habiller"),
    ("Alimentation", "Manger/boire"),
    ("Élimination", "Utiliser les toilettes"),
    ("Transferts", "Se lever/se coucher/s'asseoir"),
    ("Déplacements intérieurs", "Se déplacer dans le logement"),
    ("Déplacements extérieurs", "Sortir de chez soi"),
    ("Communication", "Utiliser les moyens de communication"),
]

CHOICES = {0: "Autonome (sans aide)", 1: "Aide partielle (ponctuelle)", 2: "Aide fréquente ou continue"}
HELP_LINK = (
    "ℹ️ Explication grand public : "
    "https://www.pour-les-personnes-agees.gouv.fr/preserver-son-autonomie/perte-d-autonomie-evaluation-et-droits/comment-fonctionne-la-grille-aggir"
)

def compute_gir_simplified(responses: Dict[str, int]) -> int:
    vals = list(responses.values())
    severe = sum(1 for v in vals if v == 2)
    partial = sum(1 for v in vals if v == 1)
    sev_keys = {k for k, v in responses.items() if v == 2}
    if severe >= 4 and ("Cohérence" in sev_keys or "Orientation" in sev_keys):
        return 1
    if severe >= 2:
        return 2
    if severe >= 1 and partial >= 2:
        return 3
    if partial >= 1:
        return 4
    return 6 if severe == 0 and partial == 0 else 5

NOTES_GIR = {1: "Dépendance très lourde : présence quasi-constante nécessaire.",
             2: "Dépendance lourde : aide fréquente pour actes essentiels.",
             3: "Dépendance notable : aide quotidienne.",
             4: "Aide ponctuelle pour certains actes.",
             5: "Autonomie globale avec aides domestiques.",
             6: "Autonomie : pas d'aide pour les actes essentiels."}

with st.expander("1) Évaluer le GIR (MVP)", expanded=True):
    st.markdown(HELP_LINK)
    with st.form("form_gir"):
        st.write("**Pour chaque item, cochez la situation la plus proche.**")
        responses: Dict[str, int] = {}
        cols = st.columns(2)
        for i, (code, label) in enumerate(AGGIR_ITEMS):
            with cols[i % 2]:
                val = st.radio(f"{code} — {label}", options=list(CHOICES.keys()), format_func=lambda x: CHOICES[x], key=f"aggir_{code}")
                responses[code] = int(val)
        submitted = st.form_submit_button("Estimer mon GIR")

    if submitted:
        gir = compute_gir_simplified(responses)
        st.session_state["gir_estime"] = gir
        st.success(f"**GIR estimé (MVP) : {gir}** — {NOTES_GIR[gir]}")
        if gir in PLAF_COEF:
            plafond = PLAF_COEF[gir] * MTP
            st.info(f"Plafond APA indicatif pour GIR {gir} (mensuel) ≈ **{plafond:,.0f} €** (coef {PLAF_COEF[gir]} × MTP {MTP:,.2f}).")
        st.caption("Estimation indicative à confirmer par évaluation officielle.")

# -----------------------------------------------------------------------------
# B. APA & participation — présentation simplifiée (plafond → A → résultats)
# -----------------------------------------------------------------------------

# A1/A2/A3: fractions de A selon MTP
T1 = 0.317  # seuil 1 × MTP
T2 = 0.498  # seuil 2 × MTP
LOW = 0.725 # 0,725 × MTP : aucune participation
HIGH = 2.67 # 2,67 × MTP : 90 % de participation

def split_A(A: float, mtp: float) -> Tuple[float, float, float]:
    s1 = T1 * mtp
    s2 = T2 * mtp
    a1 = min(A, s1)
    a2 = min(max(A - s1, 0.0), max(s2 - s1, 0.0))
    a3 = max(A - s2, 0.0)
    return a1, a2, a3

def compute_participation(R: float, A: float, mtp: float) -> float:
    if A <= 0:
        return 0.0
    if R <= LOW * mtp:
        return 0.0
    if R >= HIGH * mtp:
        return 0.9 * A
    a1, a2, a3 = split_A(A, mtp)
    denom = (HIGH - LOW) * mtp      # 1,945 × MTP
    base = ((R - LOW * mtp) / denom) * 0.9
    term2 = ((1 - 0.4) / denom) * R + 0.4
    term3 = ((1 - 0.2) / denom) * R + 0.2
    P = a1 * base + a2 * base * term2 + a3 * base * term3
    return max(min(P, 0.9 * A), 0.0)

with st.expander("2) Estimer mes droits APA et ma participation", expanded=True):
    if "gir_estime" not in st.session_state:
        st.warning("Commencez par estimer le GIR (section 1).")
    else:
        gir = int(st.session_state["gir_estime"])
        coef = PLAF_COEF.get(gir, 0.0)
        plafond = round(coef * MTP, 2)

        # Contexte et rappel du plafond
        st.info(
            f"**Plafond mensuel pour GIR {gir} : {plafond:,.0f} €**.\n\n"
            "Le **plan d’aide accepté** est souvent **inférieur au plafond**, "
            "sur la base d’une **évaluation des besoins à domicile** par un travailleur médico-social "
            "et du **choix de la personne** (accord sur le **nombre d’heures** et sur le **montant de la participation**)."
        )

        col1, col2 = st.columns(2)
        with col1:
            situation = st.selectbox("Situation familiale", ["Seul(e)", "En couple"], index=0)
        with col2:
            revenus_foyer = st.number_input("Revenus mensuels du foyer (€)", min_value=0.0, value=1500.0, step=50.0)

        # Revenus pris en compte (règle couple)
        R = revenus_foyer if situation == "Seul(e)" else revenus_foyer / 1.7

        # Saisie du plan d'aide accepté (par défaut = plafond)
        st.write("**Montant du plan d’aide accepté (A)**")
        A = st.number_input(
            "A (€ / mois)",
            min_value=0.0,
            value=float(plafond),
            step=10.0,
            help="Par défaut au plafond, mais souvent inférieur après évaluation et choix de la personne."
        )
        if A > plafond:
            st.warning(f"A dépasse le plafond GIR : {plafond:,.0f} €. L'aide versée sera plafonnée.")
        A_effectif = min(A, plafond)

        # Calculs
        P = compute_participation(R, A_effectif, MTP)  # participation (reste à charge estimé)
        T = 0.0 if A_effectif == 0 else P / A_effectif # taux de participation
        APA_versee = max(A_effectif - P, 0.0)          # montant d'APA effectivement versé

        # Mémoriser pour le bloc C (heures possibles)
        st.session_state["APA_versee"] = APA_versee

        st.divider()
        st.subheader("Résultat")
        # Affichage épuré : plan d’aide, taux, reste à charge, APA
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Plan d’aide retenu (A)", f"{A_effectif:,.0f} € / mois")
        c2.metric("Taux de participation", f"{T*100:,.1f} %")
        c3.metric("Reste à charge estimé", f"{P:,.0f} € / mois")
        c4.metric("APA versée (estimation)", f"{APA_versee:,.0f} € / mois")


# -----------------------------------------------------------------------------
# C. Mode d'intervention — estimation d'heures possibles
# -----------------------------------------------------------------------------
with st.expander("3) Choisir un mode d'intervention — heures possibles", expanded=True):
    if "gir_estime" not in st.session_state:
        st.warning("Commencez par estimer le GIR et la participation (sections 1 et 2).")
    else:
        APA_versee = float(st.session_state.get("APA_versee", 0.0))

        couts_horaires = CFG.get("couts_horaires", {
            "Emploi direct": 18.96,
            "SAAD - mandataire": 21.00,
            "SAAD - prestataire": 24.58,
        })

        mode = st.selectbox("Mode d'intervention", list(couts_horaires.keys()), index=0)
        cout_h = float(couts_horaires.get(mode, 0.0))

        heures_possibles = 0.0 if cout_h <= 0 else round(APA_versee / cout_h, 1)

        st.metric("APA estimée (après participation)", f"{APA_versee:,.0f} € / mois")
        st.metric(f"Heures possibles en {mode}", f"{heures_possibles} h / mois",
                  help=f"Calcul : APA ÷ {cout_h:.2f} €/h")

# -----------------------------------------------------------------------------
# D. Export minimal (CSV)
# -----------------------------------------------------------------------------
with st.expander("Exporter mon estimation", expanded=False):
    gir = int(st.session_state.get("gir_estime", 0))
    plafond = PLAF_COEF.get(gir, 0.0) * MTP if gir in PLAF_COEF else 0.0
    export = {"gir_estime": gir, "mtp": MTP, "plafond_gir": plafond}
    csv = pd.DataFrame([export]).to_csv(index=False).encode("utf-8")
    st.download_button("Télécharger (CSV)", data=csv, file_name="estimation_gir_apa.csv", mime="text/csv")

st.divider()
st.caption("Règles paramétrées : MTP, plafonds par GIR, division des revenus par 1,7 en couple, paliers A1/A2/A3 et formule de participation.")
