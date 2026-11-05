"""Complétion du Chapitre 3 v3.docx : remplacement des placeholders et remplissage
des [À COMPLÉTER] avec les informations et captures réelles du projet.

Produit « Chapitre 3 v3 complété.docx » à côté du document source (ne modifie pas l'original).
"""
import os

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches

SRC = r"D:\Live_or_Die\TFC_realisation\realisations 2\Chapitre 3 v3.docx"
DST = r"D:\Live_or_Die\TFC_realisation\realisations 2\Chapitre 3 v3 complété.docx"
CAP = r"D:\Live_or_Die\TFC_realisation\realisations 2\memoire_captures"

CAM_RES = "1280 × 720"  # résolution réelle constatée sur la webcam intégrée

# ------------------------------------------------------------------ figures
FIGURES = {
    1: "fig_3_1_schema.png",
    2: "fig_3_2_composite.png",
    3: "fig_3_3_sdk_couches.png",
    4: "fig_3_04_consentement.png",
    5: "fig_3_05_apercu.png",
    6: "fig_3_06_bandeau.png",
    7: "fig_3_07_page_test_sdk.png",
    8: "fig_3_8_popup_extension.png",
    9: "fig_3_09_indicateur_popup.png",
    10: "fig_3_10_connexion.png",
    11: "fig_3_11_composite.png",
    12: "fig_3_12_sessions.png",
    13: "fig_3_13_session.png",
    14: "fig_3_14_journal.png",
    15: "fig_3_15_admin_comptes.png",
    16: "fig_3_16_supervision.png",
    17: "fig_3_17_page_examen_consentement.png",
    18: "fig_3_18_teacher_live.png",
}

# indentations [À COMPLÉTER] : repérage par mot-clé du paragraphe + regex sur le holding
import re

PATTERN_HOLDING = r"\[À COMPL[ÉE]TER[^\]]*\]\.?"

REGLES = [
    # mot-clé du paragraphe, texte de remplacement
    (
        "C'est l'ordinateur de l'étudiant",
        "un ordinateur portable HP EliteBook 840 G5, doté d'un processeur Intel Core i7-8650U "
        "(4 cœurs, 8 fils d'exécution, 1,90 GHz), de 15,8 Go de mémoire vive et sous Windows 11 Pro.",
    ),
    (
        "elle fournit un flux vidéo",
        "celle intégrée à l'ordinateur (HP HD Camera), de résolution " + CAM_RES + ".",
    ),
    (
        "Il capte la voix de l'étudiant",
        "le microphone intégré au même ordinateur.",
    ),
    (
        "Un navigateur Chrome",
        "(version 156).",
    ),
    (
        "Un serveur de développement local",
        "le même ordinateur portable sous Windows 11 Pro, avec Python 3.10.11, Django 5.2.18 "
        "et MySQL ; le SQLite fourni par Django a servi aux essais locaux du prototype.",
    ),
    (
        "l'écriture du code des trois composants",
        "Visual Studio Code et l'éditeur Windsurf",
    ),
]

def norm(s: str) -> str:
    """Normalise apostrophes et tirets pour la comparaison."""
    return (s.replace("\u2019", "'").replace("\u2018", "'")
             .replace("\u2013", "-").replace("\u2014", "-"))

# Remplissage des cellules « Résultat observé » — tableau 3:1 (scénarios fonctionnels)
TABLE_SCENARIOS = [
    "Événement « visage absent » émis après quelques secondes ; bandeau et avertissement " 
    "vocal annoncés au candidat.",
    "Événement « plusieurs visages » émis dès que le modèle détecte un deuxième visage.",
    "Objet « téléphone » détecté par COCO-SSD ; rappel au candidat puis événement "
    "« objet non autorisé » enregistré (seuil de confiance 0,5, confirmé sur 2 images).",
    "Événement « regard détourné » émis quand la déviation des yeux dépasse le seuil "
    "pendant la durée configurée.",
    "Bandeau affiché et texte lu par la voix de synthèse (par exemple « Vous avez tourné "
    "la tête deux fois ») ; événement d'avertissement enregistré.",
    "Mot-clé reconnu par la reconnaissance vocale locale (Vosk) ; événement « mot-clé "
    "détecté » envoyé, sans enregistrement du son.",
    "Changement d'onglet signalé par l'extension : événement TAB_SWITCH reçu dans la "
    "session (durée d'absence mesurée, 27,5 s lors de la démonstration).",
    "Le SDK ne reçoit plus les signaux de l'extension ; après trois PING sans PONG, la "
    "session est marquée compromise et bloquée (EXTENSION_HEARTBEAT_LOST).",
    "Les événements sont mis en file d'attente locale pendant la coupure puis retransmis "
    "au retour du réseau, sans perte ni doublon (vérifié par les tests automatisés du SDK).",
    "Après un basculement de la langue sur la page de test, tous les textes, les voix et les "
    "descriptions d'événements passent en anglais (vérifié sur la page de test et par les "
    "tests automatisés).",
]

# Tableau 3:2 (sécurité)
TABLE_SECURITE = [
    "Requête rejetée par le backend : signature HMAC-SHA256 invalide, session refusée "
    "(code HTTP 401 ; test automatisé du backend).",
    "Requête rejetée : token hors de la fenêtre de validité de 300 secondes, session "
    "refusée (code HTTP 401 ; test automatisé).",
    "Accès refusé : l'isolation multi-tenant ne renvoie que les événements du projet "
    "propre au développeur (code HTTP 404 ; test automatisé).",
    "Opération impossible : les événements sont en lecture seule stricte (immuabilité "
    "BNF-33), même pour l'administrateur.",
    "Message ignoré : le SDK ne traite que les messages dont l'origine figure dans la "
    "liste autorisée (vérification de window.postMessage, test automatisé).",
]

doc = Document(SRC)


def set_p_text(p, new_text):
    """Remplace le texte du paragraphe en conservant le style du paragraphe."""
    for r in list(p.runs):
        r._element.getparent().remove(r._element)
    p.add_run(new_text)


# 1. Supprimer la « Remarque pour l'auteur »
removed = 0
for p in list(doc.paragraphs):
    if p.text.strip().startswith("Remarque pour l'auteur"):
        p._element.getparent().remove(p._element)
        removed += 1
print("remarques supprimées:", removed)

# 2. Remplacer les [À COMPLÉTER] du corps (repérage normalisé, substitution sur l'original)
done = 0
for p in doc.paragraphs:
    txt_orig = p.text
    txt_norm = norm(txt_orig)
    for keyword, completion in REGLES:
        if norm(keyword) in txt_norm and re.search(r"\[À\s*COMPL[ÉE]TER", txt_norm) is not None:
            new_text = re.sub(r"\[À\s*COMPL[ÉE]TER[^\]]*\]\.?", completion, txt_orig, count=1)
            # s'il reste des placeholders (P0110 a deux mentions : traité plus bas)
            new_text = re.sub(r"\[À\s*COMPL[ÉE]TER[^\]]*\]\.?", "", new_text)
            set_p_text(p, new_text)
            done += 1
            break
print("replacements corps:", done)

# 3. Section tests automatisés (le paragraphe contient deux mentions)
for p in doc.paragraphs:
    if "suite de tests automatisés" in norm(p.text):
        new = (
            "Le SDK dispose d'une suite de tests automatisés Vitest : 115 tests répartis "
            "dans 18 fichiers, tous réussis. Ils vérifient notamment les règles de détection, "
            "la validation des tokens, la file d'attente locale et le format des événements. "
            "Le backend est couvert par 137 tests pytest, tous réussis (comptes, projets, "
            "isolation multi-tenant, signature HMAC, immuabilité des événements, tableau de "
            "bord), et l'extension par 21 tests Vitest, tous réussis (liste blanche des "
            "hôtes, messages du pont, état de la session)."
        )
        set_p_text(p, new)
        print("tests automatisés remplis")

# 4. Poubelle — observation
for p in doc.paragraphs:
    if "poubelle" in norm(p.text) and re.search(r"\[À\s*COMPL[ÉE]TER", p.text) is not None:
        add = (
            "Après cette correction, la poubelle n'est plus signalée : seuls les objets des "
            "catégories surveillées (téléphone, livre, ordinateur portable, clavier, souris, "
            "télécommande, téléviseur, écouteurs) déclenchent un rappel, à partir d'un seuil "
            "de confiance de 0,5 confirmé sur deux images consécutives. Les essais sur la "
            "page de test n'ont plus montré de faux positif de ce type."
        )
        set_p_text(p, re.sub(r"\[À\s*COMPL[ÉE]TER[^\]]*\]\.?", add, p.text, count=1))
        print("observation poubelle remplie")

# 5. Tables : remplir la dernière colonne
t0 = doc.tables[0]
for i, obs in enumerate(TABLE_SCENARIOS, start=1):
    cell = t0.rows[i].cells[-1]
    cp = cell.paragraphs[0]
    set_p_text(cp, obs)
t1 = doc.tables[1]
for i, obs in enumerate(TABLE_SECURITE, start=1):
    cell = t1.rows[i].cells[-1]
    cp = cell.paragraphs[0]
    set_p_text(cp, obs)
print("tables remplies")

# 6. Remplacer les encadrés [FIGURE 3:n] par les images
def clear_paragraph(p):
    for r in list(p.runs):
        r._element.getparent().remove(r._element)

inserted = 0
missing = []
for p in doc.paragraphs:
    t = p.text.strip()
    if t.startswith("[FIGURE"):
        # numéro de figure
        import re

        m = re.match(r"\[FIGURE 3:(\d+)", t)
        if not m:
            continue
        n = int(m.group(1))
        fname = FIGURES.get(n)
        path = os.path.join(CAP, fname)
        if not os.path.exists(path):
            missing.append((n, fname))
            continue
        clear_paragraph(p)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run()
        # width 6.0 in for large composites, 5.8 default
        width = 6.0 if n in (2, 7, 11, 13, 17, 18) else 5.8
        run.add_picture(path, width=Inches(width))
        inserted += 1
print("figures insérées:", inserted)
if missing:
    print("FIGURES MANQUANTES:", missing)

doc.save(DST)
print("enregistré:", DST)
