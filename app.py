# app.py — Calculateur GIR + APA/Participation + coûts par mode (MVP ajusté)
# -----------------------------------------------------------------------------
# ⚠️ Prototype pédagogique. Les règles proviennent de ta fiche « Calcul-APA ».
# -----------------------------------------------------------------------------

import streamlit as st
import pandas as pd
from typing import Dict, Tuple
import pathlib, json, yaml, io
from datetime import datetime

# ──────────────────────────────────────────────────────────────────────────────
# Page config
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Mes droits en matière de perte d'autonomie",
    page_icon="🧭",
    layout="centered",
)

# Police plus petite pour les valeurs de st.metric (évite la coupure de “/ an” etc.)
st.markdown("""
<style>
div[data-testid="stMetricValue"] { font-size: 1.6rem; } /* défaut ~2rem */
div[data-testid="stMetricDelta"] { font-size: 0.9rem; }
</style>
""", unsafe_allow_html=True)

st.title("🧭 Mes droits en matière de perte d'autonomie — Estimation GIR & APA")
st.caption("Estimation indicative. Les aides dépendent d’une évaluation à domicile et des pratiques départementales.")

# ──────────────────────────────────────────────────────────────────────────────
# Chargement configuration (MTP + plafonds)
# ──────────────────────────────────────────────────────────────────────────────
DEFAULT_CFG = {
    "mtp": 1365.08,  # Montant de la MTP (mensuel)
    "plafonds_multiplicateurs": {  # Plafond APA = coef * MTP
        1: 1.615,
        2: 1.306,
        3: 0.944,
        4: 0.630,
    },
    # Coûts horaires par défaut pour l'estimation d'heures
    "couts_horaires": {
        "Emploi direct": 18.96,
        "SAAD - mandataire": 21.00,
        "SAAD - prestataire": 24.58,
    }
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

# ──────────────────────────────────────────────────────────────────────────────
# A. Évaluation GIR — MVP simplifié
# ──────────────────────────────────────────────────────────────────────────────
AGGIR_ITEMS = [
    ("Cohérence", "Comprendre, s'exprimer et se comporter de manière adaptée"),
    ("Orientation", "Se repérer dans le temps et les lieux"),
    ("Toilette", "Se laver"),
    ("Habillage", "S'habiller"),
    ("Alimentation", "Manger et boire"),
    ("Élimination", "Utiliser les toilettes"),
    ("Transferts", "Se lever, se coucher et s'asseoir"),
    ("Déplacements intérieurs", "Se déplacer dans le logement"),
    ("Déplacements extérieurs", "Sortir de chez soi"),
    ("Communication", "Téléphone, alarme…"),
]
CHOICES = {0: "Autonome (sans aide)", 1: "Aide partielle (ponctuelle)", 2: "Aide fréquente ou continue"}
HELP_LINK = ("ℹ️ Explication grand public : "
             "https://www.pour-les-personnes-agees.gouv.fr/preserver-son-autonomie/perte-d-autonomie-evaluation-et-droits/comment-fonctionne-la-grille-aggir")

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

NOTES_GIR = {
    1: "GIR 1 : dépendance très lourde (aide continue, fonctions mentales très altérées).",
    2: "GIR 2 : aide importante (confinement ou altérations cognitives marquées).",
    3: "GIR 3 : aide pluriquotidienne pour l’autonomie corporelle.",
    4: "GIR 4 : aide ponctuelle (transferts, toilette, repas…).",
    5: "GIR 5 : aide ménagère possible (hors APA).",
    6: "GIR 6 : autonome pour les actes essentiels.",
}

with st.expander("1) Estimer le GIR", expanded=True):
    st.markdown(HELP_LINK)
    with st.form("form_gir"):
        st.write("**Pour chaque item, cochez la situation la plus proche.**")
        responses: Dict[str, int] = {}
        cols = st.columns(2)
        for i, (code, label) in enumerate(AGGIR_ITEMS):
            with cols[i % 2]:
                val = st.radio(
                    f"{code} — {label}",
                    options=list(CHOICES.keys()),
                    format_func=lambda x: CHOICES[x],
                    key=f"aggir_{code}"
                )
                responses[code] = int(val)
        submitted = st.form_submit_button("Estimer mon GIR")

    if submitted:
        gir = compute_gir_simplified(responses)
        st.session_state["gir_estime"] = gir
        st.session_state["aggir_responses"] = responses
        st.success(f"**GIR estimé : {gir}** — {NOTES_GIR[gir]}")
        if gir in PLAF_COEF:
            plafond = PLAF_COEF[gir] * MTP
            st.info(f"Plafond indicatif d’aides pour GIR {gir} : **{plafond:,.0f} € / mois**")
        st.caption("Estimation indicative à confirmer par une évaluation à domicile par un professionnel.")

        # Message d’orientation aide à l’autonomie (APA / caisses)
        if gir in (1, 2, 3, 4):
            st.warning(
                "➡️ Pour un GIR 1 à 4, vous pouvez **déposer une demande d’aide à l’autonomie** "
                "(dossier **commun APA + aides des caisses de retraite**), à adresser **au Département**. "
                "Informations et formulaire : "
                "https://www.pour-les-personnes-agees.gouv.fr/vivre-a-domicile/beneficier-d-aide-a-domicile/faire-une-demande-d-aides-a-l-autonomie-a-domicile"
            )
        else:
            st.info(
                "➡️ En **GIR 5 ou 6**, vous pouvez demander une **aide à l’autonomie** si vous ressentez un besoin "
                "ou un **enjeu de prévention** ; la demande est à adresser en priorité à votre **caisse de retraite** "
                "(**CARSAT** le plus souvent)."
            )

# ──────────────────────────────────────────────────────────────────────────────
# B. APA & participation — plafonds → A → résultats
# ──────────────────────────────────────────────────────────────────────────────
T1 = 0.317  # seuil 1 × MTP (palier A1)
T2 = 0.498  # seuil 2 × MTP (palier A2)
LOW = 0.725 # 0,725 × MTP : 0 % de participation
HIGH = 2.67 # 2,67 × MTP : 90 % de participation

def split_A(A: float, mtp: float) -> Tuple[float, float, float]:
    s1 = T1 * mtp
    s2 = T2 * mtp
    a1 = min(A, s1)
    a2 = min(max(A - s1, 0.0), max(s2 - s1, 0.0))
    a3 = max(A - s2, 0.0)
    return a1, a2, a3

def compute_participation(R: float, A: float, mtp: float) -> float:
    """
    Implémente exactement la règle transmise :
    - R <= 0,725×MTP : 0 %
    - R >= 2,67×MTP : 90 %
    - Sinon : P = A1*base + A2*base*term2 + A3*base*term3
      avec base = ((R - 0,725*MTP)/((2,67-0,725)*MTP))*0,9
           term2 = ((1-0,4)/denom)*R + 0,4
           term3 = ((1-0,2)/denom)*R + 0,2
    """
    if A <= 0:
        return 0.0
    if R <= LOW * mtp:
        return 0.0
    if R >= HIGH * mtp:
        return 0.9 * A
    a1, a2, a3 = split_A(A, mtp)
    denom = (HIGH - LOW) * mtp      # (2,67 - 0,725) × MTP
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
        plafond = round(coef * MTP, 2) if coef else 0.0

        st.info(
            f"**Plafond mensuel pour GIR {gir} : {plafond:,.0f} € / mois**.\n\n"
            "Le **plan d’aide accepté (A)** est souvent **inférieur au plafond**, "
            "sur la base d’une **évaluation à domicile** par un travailleur médico-social "
            "et du **choix de la personne** (heures et participation)."
        )

        col1, col2 = st.columns(2)
        with col1:
            situation = st.selectbox("Situation familiale", ["Seul(e)", "En couple"], index=0)
        with col2:
            revenus_foyer = st.number_input("Revenus mensuels du foyer (€)", min_value=0.0, value=1500.0, step=50.0)

        # Revenus pris en compte (règle couple)
        R = revenus_foyer if situation == "Seul(e)" else revenus_foyer / 1.7

        st.write("**Montant du plan d’aide accepté (A)**")
        A = st.number_input(
            "A (€ / mois)",
            min_value=0.0,
            value=float(plafond),
            step=10.0,
            help="Par défaut au plafond, mais souvent inférieur après évaluation et choix de la personne."
        )
        if A > plafond > 0:
            st.warning(f"A dépasse le plafond GIR : {plafond:,.0f} €. L'aide versée sera plafonnée.")
        A_effectif = min(A, plafond) if plafond > 0 else A

        # Calculs
        P = compute_participation(R, A_effectif, MTP)  # participation (reste à charge estimé)
        T = 0.0 if A_effectif == 0 else P / A_effectif # taux de participation
        APA_versee = max(A_effectif - P, 0.0)          # montant d'APA effectivement versé

        # Mémo pour le PDF
        st.session_state["R_calcule"] = R
        st.session_state["A_effectif"] = A_effectif
        st.session_state["T_taux"] = T
        st.session_state["P_participation"] = P
        st.session_state["revenus_foyer"] = revenus_foyer
        st.session_state["situation_familiale"] = situation
        # Mémo pour la section suivante
        st.session_state["APA_versee"] = APA_versee

        st.divider()
        st.subheader("Résultat")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Plan d’aide retenu (A)", f"{A_effectif:,.0f} € / mois")
        c2.metric("Taux de participation", f"{T*100:,.1f} %")
        c3.metric("Reste à charge estimé", f"{P:,.0f} € / mois")
        c4.metric("APA versée (estimation)", f"{APA_versee:,.0f} € / mois")

# ──────────────────────────────────────────────────────────────────────────────
# C. Mode d’intervention — estimation d’heures possibles
# ──────────────────────────────────────────────────────────────────────────────
with st.expander("3) Choisir un mode d’intervention — heures possibles", expanded=True):
    if "gir_estime" not in st.session_state:
        st.warning("Commencez par estimer le GIR et la participation (sections 1 et 2).")
    else:
        APA_versee = float(st.session_state.get("APA_versee", 0.0))
        couts_horaires = CFG.get("couts_horaires", DEFAULT_CFG["couts_horaires"])

        mode = st.selectbox("Mode d'intervention", list(couts_horaires.keys()), index=0)
        cout_h = float(couts_horaires.get(mode, 0.0))

        base_heures = 0.0 if cout_h <= 0 else APA_versee / cout_h
        # Fourchette 70–90 %, arrondie à l'entier (pas de virgule)
        h_min = int(max(0, round(base_heures * 0.70)))
        h_max = int(max(h_min, round(base_heures * 0.90)))

        st.metric("APA estimée (après participation)", f"{APA_versee:,.0f} € / mois")
        st.metric(f"Heures possibles en {mode}", f"≈ {h_min}–{h_max} h / mois",
                  help=f"Base: APA ÷ coût horaire ({cout_h:.2f} €/h), puis fourchette 70–90 %.")

        # Paragraphe explicatif sur les modes
        st.markdown(
            "**Lorsque l’APA est accordée, vous choisissez un mode d’intervention parmi 3 :**\n"
            "- **Emploi direct** : vous embauchez directement un(e) aide à domicile (ex. via **CESU**).\n"
            "- **Mandataire** : vous faites appel à une **structure** (souvent association) qui vous accompagne "
            "dans les démarches, mais **vous demeurez l’employeur**.\n"
            "- **Prestataire** : vous choisissez une **structure** (association, CCAS, entreprise privée) qui "
            "**salarie directement** les aides à domicile.\n\n"
            "_Les plans d’aide indicatifs sont calculés à partir de moyennes observées (plafonds, tarifs). "
            "Ils peuvent varier selon les situations individuelles et les pratiques départementales._"
        )

        # Mention après l’affichage des heures/mois
        st.info(
            "Vous restez **libre des heures** acceptées dans le plan d’aide et de celles **mobilisées chaque mois**. "
            "Les aides sont versées selon le **tarif pris en charge par le Département**. "
            "Si le service ou l’employé applique un **tarif supérieur**, un **complément** peut s’ajouter "
            "(en général quelques euros par mois). **N’hésitez pas à nous solliciter sur ce point.**"
        )

# ──────────────────────────────────────────────────────────────────────────────
# D. Export — PDF (CSV supprimé)
# ──────────────────────────────────────────────────────────────────────────────
with st.expander("Exporter mon estimation (PDF)", expanded=False):
    gir = int(st.session_state.get("gir_estime", 0))
    responses = st.session_state.get("aggir_responses", {}) or {}
    plafond = PLAF_COEF.get(gir, 0.0) * MTP if gir in PLAF_COEF else 0.0
    APA_versee = float(st.session_state.get("APA_versee", 0.0))

    # Données pour la synthèse
    revenus_calc = st.session_state.get("R_calcule", None)
    A_effectif = st.session_state.get("A_effectif", None)
    T_taux = st.session_state.get("T_taux", None)
    P_part = st.session_state.get("P_participation", None)

    # Items AGGIR nécessitant aide (valeur 1 ou 2)
    items_aide = [k for k, v in responses.items() if v in (1, 2)]

    try:
        import io, math
        from datetime import datetime
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import cm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        # Police Unicode si dispo
        try:
            pdfmetrics.registerFont(TTFont("DejaVu", "DejaVuSans.ttf"))
            FONT_BASE = "DejaVu"
        except Exception:
            FONT_BASE = "Helvetica"

        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        W, H = A4
        left, right = 2*cm, W - 2*cm
        y = H - 2*cm

        # Helpers qui retournent y (pas de nonlocal)
        def h1(c, text, left, y):
            c.setFont(FONT_BASE, 16); c.drawString(left, y, text)
            return y - 1.0*cm

        def h2(c, text, left, y):
            c.setFont(FONT_BASE, 13); c.drawString(left, y, text)
            return y - 0.6*cm

        def p(c, text, left, y, leading=0.52*cm):
            c.setFont(FONT_BASE, 11)
            for line in text.split("\n"):
                c.drawString(left, y, line)
                y -= leading
            return y

        def kv(c, label, value, left, y):
            c.setFont(FONT_BASE, 11)
            c.drawString(left, y, f"- {label} : {value}")
            return y - 0.5*cm

        # ── En-tête
        y = h1(c, "Estimation GIR & APA — Résumé", left, y)
        c.setFont(FONT_BASE, 10)
        c.drawString(left, y, f"Date : {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        y -= 0.7*cm

        # ── Cadran GIR (centré + clair au-dessus et en-dessous)
        y = h2(c, "Votre GIR (cadran indicatif)", left, y)

        R = 3.8*cm          # rayon (tu peux remettre 4.0*cm si tu veux plus grand)
        clearance_top = 1.0*cm   # marge au-dessus du cadran (évite de "mordre" le titre)
        margin_bottom = 1.4*cm   # marge sous le cadran

        # centre horizontal au milieu de la zone utile
        cx = (left + right) / 2.0
        # centre vertical : on met le haut du cadran (cy + R) à y - clearance_top
        cy = y - (R + clearance_top)

        # Saut de page si besoin
        if cy - R - margin_bottom < 1.8*cm:
            c.showPage()
            y = H - 2*cm
            c.setFont(FONT_BASE, 10)
            c.drawString(left, y, f"Date : {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            y -= 0.7*cm
            y = h2(c, "Votre GIR (cadran indicatif)", left, y)
            cy = y - (R + clearance_top)

        # Demi-cercle + graduations
        c.setLineWidth(2)
        c.arc(cx - R, cy - R, cx + R, cy + R, startAng=180, extent=-180)

        import math
        for i, label in enumerate([1, 2, 3, 4, 5, 6]):
            ang = math.radians(180 - (i * (180 / 5)))
            gx = cx + (R - 0.4*cm) * math.cos(ang)
            gy = cy + (R - 0.4*cm) * math.sin(ang)
            gx2 = cx + (R - 0.8*cm) * math.cos(ang)
            gy2 = cy + (R - 0.8*cm) * math.sin(ang)
            c.setLineWidth(1); c.line(gx, gy, gx2, gy2)
            lx = cx + (R - 1.2*cm) * math.cos(ang)
            ly = cy + (R - 1.2*cm) * math.sin(ang)
            c.setFont(FONT_BASE, 10); c.drawCentredString(lx, ly, str(label))

        # Aiguille
        if gir in [1, 2, 3, 4, 5, 6]:
            ang = math.radians(180 - ((gir - 1) * (180 / 5)))
            nx = cx + (R - 1.0*cm) * math.cos(ang)
            ny = cy + (R - 1.0*cm) * math.sin(ang)
            c.setLineWidth(3); c.line(cx, cy, nx, ny)
            c.circle(cx, cy, 0.12*cm, fill=1)

        # Légende centrée
        c.setFont(FONT_BASE, 12)
        c.drawCentredString(cx, cy - (R + 0.8*cm), f"GIR estimé : {gir if gir else '—'}")

        # Avance du curseur sous le cadran
        y = cy - (R + margin_bottom)


        # ── AGGIR — items nécessitant une aide
        y = h2(c, "AGGIR — principaux éléments nécessitant une aide", left, y)
        if items_aide:
            c.setFont(FONT_BASE, 11)
            col_w = (right - left) / 2
            col_left_x = left
            col_right_x = left + col_w
            x = col_left_x
            line_h = 0.48*cm
            count = 0
            half = (len(items_aide) + 1) // 2
            y_start = y
            for idx, item in enumerate(items_aide):
                c.drawString(x, y, f"• {item}")
                y -= line_h
                count += 1
                if count == half and len(items_aide) > 1:
                    x = col_right_x
                    y = y_start
            y -= 0.4*cm
        else:
            y = p(c, "Aucun item signalé (ou évaluation non remplie).", left, y)

        # ── Synthèse financière
        y = h2(c, "Synthèse financière (mensuelle)", left, y)
        y = kv(c, "Ressources prises en compte",
               f"{revenus_calc:,.0f} €" if revenus_calc is not None else "—", left, y)
        y = kv(c, "Plafond APA (GIR)", f"{plafond:,.0f} €", left, y)
        y = kv(c, "Taux de participation",
               f"{T_taux*100:.1f} %" if T_taux is not None else "—", left, y)
        y = kv(c, "Participation (reste à charge)",
               f"{P_part:,.0f} €" if P_part is not None else "—", left, y)
        y = kv(c, "APA estimée (après participation)", f"{APA_versee:,.0f} €", left, y)
        if A_effectif is not None:
            y = kv(c, "Plan d’aide retenu (A)", f"{A_effectif:,.0f} €", left, y)

        y -= 0.3*cm
        y = p(c,
              "Notes :\n"
              "- Estimation indicative à confirmer par une évaluation à domicile.\n"
              "- Les montants et heures peuvent varier selon les pratiques départementales.\n"
              "- Le montant d'aide présenté correspond à un **plafond** ; l'aide réelle dépendra du plan accepté.",
              left, y, leading=0.5*cm)

        c.showPage()
        c.save()
        buffer.seek(0)
        pdf_bytes = buffer.read()

        st.download_button(
            "Télécharger le PDF détaillé",
            data=pdf_bytes,
            file_name="estimation_gir_apa_detail.pdf",
            mime="application/pdf"
        )
    except Exception as e:
        st.error(f"Impossible de générer le PDF (ReportLab manquant ?): {e}")
        st.info("Astuce : utilisez **Imprimer → Enregistrer en PDF** depuis le navigateur.")



st.divider()
st.caption("Règles paramétrées : MTP, plafonds par GIR, division revenus/1,7 en couple, paliers A1/A2/A3, formule de participation (0,725 / 2,67 / 0,317 / 0,498).")
