"""Amélioration du Chapitre 3 v3 :

1. renumérotation des figures existantes (les 2 nouvelles images hardware
   deviennent Figures 3:1 et 3:2) + renvois dans le texte ;
2. légendes + explication pour les 2 images des matériels (§3.2) ;
3. captures de code source dans §3.4.1 (agrégateur SDK) et §3.4.2 (service worker) ;
4. nouvelle section 3.5 « Fonctionnement de la supervision par l'IA et du score
   de risque » (flux schématisé, modèles IA, ajout d'un modèle, formule + exemple
   chiffré + tableau des poids) ;
5. renumérotation des sections 3.5→3.6, 3.6→3.7 et des tableaux (3:1→3:2, 3:2→3:3).

Le fichier cible doit être FERMÉ dans Word avant l'exécution.
"""
import os
import re
import shutil

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

SRC = r"C:\Users\PLWAM\AppData\Local\Temp\opencode\ch3_copy.docx"
DST = r"D:\Live_or_Die\TFC_realisation\realisations 2\Chapitre 3 v3 complété.docx"
CAP = r"D:\Live_or_Die\TFC_realisation\realisations 2\memoire_captures"

# --- buffers
WN = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
WP_DRAW = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}inline"

# --------------------------------------------------------------------------- #
def full_text(p):
    return "".join(r.text for r in p.runs)


def replace_cross(p, rx, repl):
    """Remplace les occurrences d'un motif même réparties sur plusieurs runs,
    en conservant le format des runs non touchés."""
    runs = p.runs
    if not runs:
        return False
    texts = [r.text for r in runs]
    starts = []
    off = 0
    for t in texts:
        starts.append(off)
        off += len(t)
    full = "".join(texts)
    m = rx.search(full)
    if m is None:
        return False
    a, b = m.span()
    # index du run de début et de fin
    i = max(j for j, s in enumerate(starts) if s <= a)
    j = max(k for k, s in enumerate(starts) if s <= a)
    # répartition
    lo, hi = m.span()
    out_runs = []
    for idx, r in enumerate(p.runs):
        rs = starts[idx]
        re_ = rs + len(texts[idx])
        prefix = texts[idx][: max(0, min(lo, re_) - rs)] if lo < re_ and rs < lo else ""
        suffix = texts[idx][(min(hi, re_) - rs) :] if hi > rs else texts[idx]
        out_runs.append((prefix, suffix, lo <= rs < hi))
    new_full = rx.sub(repl, full)
    # on reconstruit : tout le texte recomposé est réparti : préfixes avant match,
    # texte remplacé dans le run de début, suffixes après.
    # simple et robuste : donner à chaque run son texte non-modifié hors zone du match
    pieces = []
    for idx, (prefix, suffix, inside) in enumerate(out_runs):
        if idx == i:
            tail = suffix if j == i else ("" if inside else suffix)
            pieces.append(prefix + full[lo:hi] and prefix + (rx.sub(repl, full[lo:hi]) or "") + suffix
                          if j == i else prefix + suffix)
        else:
            pieces.append(prefix + suffix if not inside else (prefix if suffix else ""))
    # réécriture : plus simple — contigu caractérise énormément; fallback global si chevauchement
    if a >= starts[i] and b <= starts[i] + len(texts[i]) and i == j:
        r = p.runs[i]
        r.text = texts[i][: a - starts[i]] + repl(m) if callable(repl) else repl
        r.text = texts[i][: a - starts[i]] + (repl(m) if callable(repl) else repl) + texts[i][b - starts[i] :]
    else:
        # chevauchement : on met le texte complet dans le premier run et on vide les suivants
        new = new_full
        first = p.runs[i]
        first.text = new
        for k in range(i + 1, len(p.runs)):
            p.runs[k].text = ""
    return True


def insert_before(anchor, text=None, style="Normal", align=None):
    p = anchor.insert_paragraph_before()
    if style:
        p.style = anchor.part.document.styles[style] if False else anchor.style if False else p.style
    return p


def add_para_before(anchor, text="", style="Normal", align=None):
    p = anchor.insert_paragraph_before(text, )
    try:
        p.style = anchor.part.document.styles[style] if False else anchor.style if False else p.style
    except Exception:
        pass
    return p


def p_before(anchor, style="Normal", align=None):
    """Nouveau paragraphe vide AVANT `anchor`, style donné."""
    p = anchor.insert_paragraph_before()
    p.style = anchor.part.document.styles[style]
    if align:
        p.alignment = align
    return p


# --------------------------------------------------------------------------- #
shutil.copyfile(SRC, DST)
from docx import Document

doc = Document(DST)

# ============ 1. Renumérotation des figures ================================ #
fig_re = re.compile(r"^(Tableau|Figure)[ ]*3:(\d+)[ ]*:")
count = 0
for p in doc.paragraphs:
    t = full_text(p).strip()
    m = re.match(r"^Figure[ ]*3:(\d+)[ ]*:", t)
    if m:
        count += 1
print("FIGURES existantes :", count)
old = count
# ordre final : 2 hw + [old1..7] + aggregator + old8 + old9 + ext_tabs + old10..20 + 5 nouveaux
map_fig = {1: 3, 2: 4, 3: 5, 4: 6, 5: 7, 6: 8, 7: 9, 8: 11, 9: 12, 10: 14, 11: 15,
           12: 16, 13: 17, 14: 18, 15: 19, 16: 20, 17: 21, 18: 22, 19: 23, 20: 24}
assert old == 20, f"attendu 20 figures, trouvé {old}"

# remplacer dans les légendes
for p in doc.paragraphs:
    t = full_text(p)
    mm = re.match(r"^Figure[ ]*3:(\d+)[ ]*:", t.strip())
    if mm:
        repl = f"Figure 3:{map_fig[int(mm.group(1))]} :"
        # tout le préfixe au début du 1er run
        runs = p.runs
        # le préfixe peut chevaucher des runs ? légende = 1 run normalement
        full = "".join(r.text for r in runs)
        new = re.sub(r"^Figure[ ]*3:(\d+)[ ]*:", repl, full, count=1)
        if new != full:
            runs[0].text = new
            for r in runs[1:]:
                r.text = ""

# remplacer les renvois dans le texte
ref_re = re.compile(r"(?i)(figures?)\s+3:(\d+)")
for p in doc.paragraphs:
    if "figure" not in full_text(p).lower():
        continue
    t = full_text(p)
    if re.search(r"3:(\d+)", t) and "igure" in t:
        def sub_all(m):
            n = int(m.group(2))
            label = m.group(1)
            return f"{label} 3:{map_fig.get(n, n)}"
        replace_cross(p, re.compile(r"(?i)(figures?)\s*3:(\d+)"), sub_all)
        # cas « Figures 3:17 et 3:18 »
        replace_cross(p, re.compile(r"et\s*3:(\d+)"), lambda m: f"et 3:{map_fig.get(int(m.group(1)), m.group(1))}")

# ============ 2. Renumérotation des tableaux (3:1→3:2, 3:2→3:3) ============ #
map_tab = {1: 2, 2: 3}
for p in doc.paragraphs:
    t = full_text(p)
    if "ableau" in t and "3:" in t:
        def sub_tab(m):
            return f"{m.group(1)} 3:{map_tab.get(int(m.group(2)), int(m.group(2)))}"
        replace_cross(p, re.compile(r"(?i)(tableaux?)\s*3:(\d+)"), sub_tab)

# ============ 3. Renumérotation des titres 3.5 → 3.6, 3.6 → 3.7 ============ #
for p in doc.paragraphs:
    st = p.style.name if p.style else ""
    if not st.startswith("Heading"):
        continue
    t = full_text(p)
    m = re.match(r"^(3)\.(\d)(\.(\d))?\s", t)
    if not m:
        continue
    major = int(m.group(2))
    new_major = {5: 6, 6: 7}.get(major)
    if new_major is None:
        continue
    if m.group(4):
        repl = f"3.{new_major}.{m.group(4)} "
    else:
        repl = f"3.{new_major} "
    i = p.runs[0]
    # le numéro peut être au début du premier run
    runs = p.runs
    full = "".join(r.text for r in runs)
    new = re.sub(r"^3\.\d(\.\d)?", repl.rstrip(), full, count=1)
    if new != full:
        runs[0].text = new
        for r in runs[1:]:
            r.text = ""

# ============ 4. Matériels : séparer les 2 images + légendes + explication = #
ps = doc.paragraphs
p_hw = None
for i, p in enumerate(ps):
    if len(p._element.findall(".//" + qn("w:drawing"))) >= 2 and i < 20:
        p_hw = p
        break
assert p_hw is not None, "paragraphe 2 images introuvable"
draws = p_hw._element.findall(".//" + qn("w:drawing"))
anchor = ps[0]
for p in ps:
    if p.style and p.style.name.startswith("Heading") and full_text(p).strip().startswith("3.2.1"):
        anchor = p
        break

img_tpl = None
for p in doc.paragraphs:
    if p.style and p.style.name == "Quote" and p._element.findall(".//" + qn("w:drawing")):
        img_tpl = p
        break

# — déplacer la 2e image dans un paragraphe séparé
p_img2 = p_before(anchor, style="Quote", align=WD_ALIGN_PARAGRAPH.CENTER)
d2 = draws[1]
d2.getparent().remove(d2)
p_img2._element.append(d2)
p_hw.style = doc.styles[img_tpl.style.name] if img_tpl is not None else doc.styles["Quote"]
p_hw.alignment = WD_ALIGN_PARAGRAPH.CENTER

# — légende 1 juste après p_hw : on insère AVANT p_img2
cap1 = p_before(p_img2, style="Normal")
cap1.add_run("Figure 3:1 : Ordinateur portable HP EliteBook 840 G5")
cap2 = p_before(anchor, style="Normal")
cap2.add_run("Figure 3:2 : Webcam intégrée de l'ordinateur (HP HD Camera)")
exp = p_before(anchor, style="Normal")
exp.add_run(
    "La figure 3:1 montre le poste retenu pour conduire les essais. En tant que machine de l'étudiant, "
    "il exécute la page d'examen (avec le SDK et l'extension de surveillance) et, en développement, il "
    "héberge également le serveur local. La figure 3:2 montre sa webcam intégrée (HP HD Camera, "
    "1280 × 720) : c'est elle qui alimente l'ensemble des détections visuelles. Le flux vidéo est traité "
    "localement après autorisation explicite de l'étudiant ; il n'est ni enregistré ni transmis."
)

def add_figure(anchor, image, caption, width, text_before=None, after_text=None):
    """Insère avant `anchor` : [texte][image centrée][légende][explication]."""
    if text_before:
        p = p_before(anchor, style="Normal")
        p.add_run(text_before)
    pip = p_before(anchor, style="Quote", align=WD_ALIGN_PARAGRAPH.CENTER)
    pip.add_run().add_picture(os.path.join(CAP, image), width=Inches(width))
    cp = p_before(anchor, style="Normal")
    cp.add_run(caption)
    if after_text:
        p = p_before(anchor, style="Normal")
        p.add_run(after_text)

# ============ 5. Code source dans 3.4.1 (SDK) et 3.4.2 (extension) ========= #
anchor_342 = None
for p in doc.paragraphs:
    if p.style and p.style.name.startswith("Heading") and full_text(p).strip().startswith("3.4.2"):
        anchor_342 = p
        break
assert anchor_342 is not None
add_figure(
    anchor_342,
    "fig_3_code_aggregator.png",
    "Figure 3:10 : Extrait du code du SDK — l'agrégateur de comportement (BehaviorAggregator.ts)",
    5.2,
    text_before=(
        "Derrière ces interfaces, le comportement du SDK est piloté par le code source. L'extrait "
        "présenté ci-dessous est la couche « décisionnelle » du SDK : c'est là que les mesures brutes "
        "produites par l'intelligence artificielle (position du regard, des mains, objets visibles) "
        "deviennent des événements interprétés."
    ),
    after_text=(
        "Trois logiques de déclenchement y sont centralisées, comme l'indique la documentation du "
        "module : la vision instantanée (visage, objets) est émise immédiatement, la vision agrégée "
        "(regard, tête, mains) ne l'est qu'après une durée soutenue ou une répétition avec hystérésis, "
        "et l'audio exige la confirmation sur plusieurs segments d'une fenêtre glissante. On y voit "
        "aussi le principe anti-surcharge : un événement n'est émis qu'au changement d'état, pour ne "
        "jamais inonder le backend."
    ),
)

anchor_343 = None
for p in doc.paragraphs:
    if p.style and p.style.name.startswith("Heading") and full_text(p).strip().startswith("3.4.3"):
        anchor_343 = p
        break
assert anchor_343 is not None
add_figure(
    anchor_343,
    "fig_3_code_ext_tabs.png",
    "Figure 3:13 : Extrait du code de l'extension — détection du changement d'onglet (tabActivityDetector.ts)",
    5.6,
    text_before=(
        "Le service worker de l'extension supervise la navigation. L'extrait de code suivant montre le "
        "détecteur d'activité des onglets : il mesure la durée d'absence de l'étudiant quand il quitte "
        "l'onglet d'examen, et la restitue dans l'événement quand il revient."
    ),
    after_text=(
        "L'événement TAB_CHANGE_EXT ainsi produit contient la durée exacte d'absence (duration_ms), ce "
        "qui permet au tableau de bord de distinguer un coup d'œil fugace d'une réelle sortie de l'onglet. "
        "Le même service worker authentifie chaque requête et surveille la navigation vers d'autres "
        "domaines (NAVIGATION_EXT)."
    ),
)

# ============ 6. La nouvelle section 3.5 =================================== #
anchor_36 = None
for p in doc.paragraphs:
    if p.style and p.style.name.startswith("Heading 2") and full_text(p).strip().startswith("3.6 Tests"):
        anchor_36 = p
        break
assert anchor_36 is not None, "titre 3.6 Tests introuvable"

def h(text, level):
    p = p_before(anchor_36, style=f"Heading {level}")
    p.add_run(text)
    return p

def add_fig(anchor, image, caption, width):
    pip = p_before(anchor, style="Quote", align=WD_ALIGN_PARAGRAPH.CENTER)
    pip.add_run().add_picture(os.path.join(CAP, image), width=Inches(width))
    cp = p_before(anchor, style="Normal")
    cp.add_run(caption)

def para(text, style="Normal", first=False):
    p = p_before(anchor_36, style=style)
    p.add_run(text)
    return p

# --- 3.5 intro + 3.5.1 flux
h("3.5 Fonctionnement de la supervision par l'IA et du score de risque", 2)
para(
    "Cette section explique le fonctionnement interne Intelligence du système : d'où viennent les "
    "données analysées, comment les modèles produisent des mesures, comment ces mesures deviennent "
    "des événements, et comment le score de risque affiché au tableau de bord est calculé. Quelques "
    "extraits du code source du projet (dans les éditeurs utilisés, VS Code et Windsurf) accompagnent "
    "ces explications."
)
h("3.5.1 Le flux de détection : du capteur au badge de risque", 3)
para(
    "La figure 3:25 résume le trajet complet de l'information, de la caméra au badge affiché au "
    "tableau de bord. En (1), la page d'examen demande l'autorisation de l'étudiant et démarre la "
    "capture vidéo et audio. En (2), les flux sont analysés dans des threads séparés du navigateur "
    "(Web Workers) par les modèles TensorFlow.js et le modèle vocal Vosk, qui produisent des mesures "
    "brutes accompagnées d'une confiance. En (3), l'agrégateur de comportement observe ces mesures "
    "dans la durée et n'émet un signal interprété que lorsqu'un motif suscpete se dessine. En (4), le "
    "normalisateur met le signal au format du contrat partagé : identifiant unique, type, gravité, "
    "libellé dans la langue choisie et confidence_score. Côté serveur, la requête (5) part en HTTP "
    "POST signé avec HMAC-SHA256 et attend dans une file locale en cas de coupure réseau ; elle est "
    "vérifiée (6) — signature, période de session, projet — avant l'écriture immuable de l'événement "
    "en base. Le recalcul du score (7) est délégué à une tâche asynchrone Celery, pour ne jamais "
    "ralentir l'ingestion, et le tableau de bord (8) présente le badge de risque et la chronologie au "
    "développeur."
)
add_fig(anchor_36, "fig_3_flux_ia.png",
        "Figure 3:25 : Flux de détection du système, de la capture au badge de risque", 6.2)
para(
    "Deux choix de conception sont visibles sur ce schéma. D'abord, l'analyse reste entièrement dans "
    "le navigateur de l'étudiant : aucune image ni aucun son n'est transmis, seuls les résultats "
    "d'analyse (événements) traversent le réseau. Ensuite, le calcul du score est asynchrone : chaque "
    "requête reste rapide, et le score affiché est recalculé immédiatement après l'ingestion."
)

# --- 3.5.2 modèles
h("3.5.2 Les modèles d'intelligence artificielle embarqués", 3)
para("Quatre modèles coexistent dans le navigateur de l'étudiant, choisis pour tourner en local et en "
     "temps réel sur un ordinateur portable standard :")
para("– FaceMesh (face-landmarks-detection) : 468 points du visage et de l'iris (2 visages maximum). "
     "C'est lui qui alimente la détection du visage absent, du visage multiple, de la direction du "
     "regard et de la rotation de la tête.")
para("– COCO-SSD (variante légère lite_mobilenet_v2) : détection des objets du catalogue COCO se trouvant dans "
     " la zone de la webcam, en particulier le téléphone, le livre et la présence d'une seconde personne.")
para("– HandPose (MediaPipeHands, 2 mains maximum) : présence des mains dans le champ, utilisée pour "
     "suivre si l'étudiant garde ses mains visibles.")
para("– Vosk (version navigateur) : reconnaissance vocale hors ligne exécutée en WebAssembly ; le "
     "module repère les mots prédéfinis de la liste (FN / EN) directement dans la parole.")
para(
    "L'exécution s'appuie sur TensorFlow.js : le backend WebGL est demandé en premier et le backend "
    "WebAssembly sert de repli si l'accélération graphique n'est pas disponible. Les Workers ne "
    "bloquent jamais la page d'examen et échantillonnent les flux à une cadence adaptée aux capacités "
    "de la machine (devicePerformanceProfile). Les poids des modèles sont auto-hébergés par le "
    "projet, sur le même principe que le code du SDK. La figure 3:26 montre le chargement progressif "
    "de ces modèles dans modelLoader.ts : le modèle du visage, le plus petit et le plus critique, est "
    "chargé en premier ; l'analyse peut démarrer dès qu'il est prêt, pendant que les modèles d'objets "
    "puis de mains continuent de se charger. Une erreur sur un modèle optionnel n'empêche pas les "
    "autres de fonctionner."
)
add_fig(anchor_36, "fig_3_code_modelloader.png",
        "Figure 3:26 : Chargement progressif des modèles d'IA (modelLoader.ts)", 5.2)
para(
    "Ce chargement progressif répond à une contrainte concrète : le modèle de visage est indispensable "
    "(sans lui, aucune des détections visuelles n'a de sens), alors que objets et mains peuvent être "
    "requalifiés après le début de la session. L'interface onFirstReady démarre l'analyse dès que ce "
    "modèle est prêt."
)

# --- 3.5.3 ajout d'un modèle
h("3.5.3 Comment ajouter un nouveau modèle de détection", 3)
para(
    "L'architecture est bâtie pour accueillir un nouveau détecteur sans réécrire les couches "
    "existantes, car chaque couche communique uniquement par des flux standardisés : une mesure brute "
    "en sortie du worker ('raw-measurement'), un signal interprété en sortie de l'agrégateur "
    "('raw-signal'), un événement du contrat partagé en sortie du normalisateur (figure 3:27). "
    "Ajouter un modèle se fait alors en cinq pas :"
)
para("– 1. Charger le modèle : l'ajouter dans modelLoader.ts (Web Worker, progression signalée, "
     "chargement après le visage) et auto-héberger ses poids sur le CDN du projet.")
para("– 2. Mesurer : écrire le détecteur qui traduit les sorties du modèle en mesures brutes "
     "standardisées, chacune munie d'un confidence_score — on ne déclare pas une anomalie dès la "
     "première mesure incertaine.")
para("– 3. Décider : ajouter l'interprétation dans BehaviorAggregator (immédiat ou durée/ répétition), "
     "avec les seuils exposés dans la configuration du SDK (SdkConfig.ts).")
para("– 4. Nommer : enregistrer le type d'événement côté SDK (gravité dans EventClassifier, libellés "
     "et textes vocaux FR/EN dans i18n) puis côté backend (catégorie et éventuel type critique dans "
     "catalog.py). Le score de risque prend immédiatement en compte le nouveau type au poids de sa "
     "catégorie ; un type inconnu est traité comme « sécurité » par précaution.")
para("– 5. Vérifier : compléter les suites de tests (Vitest du SDK avec mesures simulées, pytest du "
     "backend pour les poids) et la page de test du SDK.")
add_fig(anchor_36, "fig_3_code_normalizer.png",
        "Figure 3:27 : Le contrat d'un événement, appliqué par le normalisateur (EventNormalizer.ts)", 5.6)
para(
    "Le normalisateur garantit que l'événement de n'importe quel détecteur présente la même structure "
    "(identifiant, sévérité, confiance, libellé traduit). Le backend, lui, ne connaît que ce contrat : "
    "un nouveau capteur est donc accepté sans modification de l'API."
)

# --- 3.5.4 score de risque
h("3.5.4 Le score de risque : formule, poids et exemple chiffré", 3)
para(
    "Le score de risque est calculé côté backend à partir des événements enregistrés. La fonction "
    "compute_risk_score (figure 3:28) est volontairement simple et explicable : chaque événement "
    "apporte le poids de sa catégorie, modulé par la confiance de son détecteur et relevé d'un "
    "coefficient 1,5 s'il s'agit d'un type critique ; la somme obtenue est transformée par une "
    "saturation exponentielle (figure 3:29) qui garantit un résultat borné dans [0, 1]."
)
add_fig(anchor_36, "fig_3_code_risk.png",
        "Figure 3:28 : Le calcul du score de risque (apps/sessions/risk.py), tel qu'extrait du code", 5.6)
add_fig(anchor_36, "fig_3_formule_score.png",
        "Figure 3:29 : La formule du score de risque appliquée au code ci-dessus", 5.9)
cap_tab = p_before(anchor_36, style="Normal")
cap_tab.add_run("Tableau 3:1 : Poids de base par catégorie et types critiques (risk.py et catalog.py)")
table = doc.add_table(rows=6, cols=3)
table.style = doc.styles["Table Grid"]
data = [
    ("Catégorie", "Poids w", "Types critiques associés"),
    ("Sécurité", "0,35", "DOM_TAMPERING · AUTOMATION_DETECTED · EXTENSION_HEARTBEAT_LOST · "
     "SIMULATED_EVENT_DETECTED"),
    ("Audio", "0,20", "MULTIPLE_VOICES · AUDIO_KEYWORD_MATCH"),
    ("Vision", "0,15", "MULTIPLE_FACES · FORBIDDEN_OBJECT_DETECTED · VIRTUAL_DEVICE_DETECTED"),
    ("Extension navigateur", "0,10", "—"),
    ("Navigateur", "0,05", "PAGE_EXIT"),
]
for r_i, row in enumerate(data):
    for c_i, val in enumerate(row):
        cell = table.rows[r_i].cells[c_i]
        cell.text = val
        for pr in cell.paragraphs:
            for rn in pr.runs:
                if r_i == 0:
                    rn.font.bold = True
        if r_i == 0:
            for rn in cell.paragraphs[0].runs:
                rn.font.bold = True
widths = (Inches(1.55), Inches(0.85), Inches(4.1))
for row in table.rows:
    for cell, w in zip(row.cells, widths):
        cell.width = w
anchor_36._p.addprevious(table._tbl)
para(
    "À titre d'exemple, prenons une session qui contient trois signaux : un regard dérobé soutenu "
    "(GAZE_AWAY_SUSTAINED, vision, confiance 0,92), deux voix simultanées (MULTIPLE_VOICES, audio, "
    "type critique, sans confiance) et trois changements d'onglet (TAB_SWITCH, navigateur, sans "
    "confiance). Le poids du premier vaut 0,15 × (0,5 + 0,5 × 0,92) = 0,144 ; celui du second "
    "0,20 × 1,5 = 0,300 ; le troisième 3 × 0,05 = 0,150. La somme vaut S = 0,594, d'où "
    "R = 1 − e^(−0,594) ≈ 0,45 : un score « Moyen » de 45 %."
)
para(
    "Le libellé affiché au tableau de bord découle de seuils configurables (RISK_THRESHOLDS) : "
    "« Faible » si R < 0,30, « Moyen » si 0,30 ≤ R < 0,60 et « Élevé » si R ≥ 0,60. La saturation "
    "exponentielle fait en sorte que dix doublons du même signe ne poussent pas le score vers "
    "100 %, tout en garantissant qu'un événement critique isolé reste bien visible. Ce score reste "
    "CEpendant un indicateur d'aide à la décision : il oriente la relecture humaine, il ne prouve "
    "jamais rien."
)

# ============ 7. Vérification + enregistrement ============================= #
caps = []
for p in doc.paragraphs:
    m = re.match(r"^Figure[ ]*3:(\d+)", full_text(p).strip())
    if m:
        caps.append(int(m.group(1)))
print("Numéros de figures après édition :", caps)
expected = list(range(1, len(caps) + 1))
print("Séquence 1..N en ordre :", caps == expected)

try:
    doc.save(DST)
    print("SAVED ✓", DST)
except PermissionError as exc:
    print("ERREUR : le fichier est ouvert dans Word :", exc)
