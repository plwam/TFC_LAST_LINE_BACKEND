"""Ajoute la sous-section 3.4.6 La documentation du système au document complété."""
import copy

from docx import Document

DOC = r"D:\Live_or_Die\TFC_realisation\realisations 2\Chapitre 3 v3 complété.docx"
doc = Document(DOC)

# repère l'insertion : juste avant le titre « 3.5 Tests et validation du système »
ancre = None
for p in doc.paragraphs:
    if p.text.strip().startswith("3.5 Tests et validation du système") and p.style.name.startswith("Heading"):
        ancre = p
        break
assert ancre is not None, "ancre 3.5 introuvable"

def quote_template():
    """Prend un paragraphe Style='Quote' existant comme gabriol (vide son texte)."""
    src = None
    for q in doc.paragraphs:
        if q.text.strip().startswith("[FIGURE") and q.style.name == "Quote":
            src = q
            break
    return src

gabriol_quote = quote_template()
gabriol_caption = None
for i, p in enumerate(doc.paragraphs):
    if p.text.strip().startswith("Figure 3:14"):
        gabriol_caption = doc.paragraphs[i]
        break
gabriol_norm = None
for p in doc.paragraphs:
    if p.text.strip().startswith("L'extension observe") or p.text.strip().startswith("Cet onglet (Figure 3:14)"):
        gabriol_norm = p
        break
if gabriol_norm is None:
    for p in doc.paragraphs:
        if p.style.name == "Normal" and len(p.text) > 80:
            gabriol_norm = p
            break

def ins_after(new_elem, before_elem):
    """Insère new_elem immédiatement avant before_elem."""
    before_elem.addprevious(copy.deepcopy(new_elem))

# clone vierges
def clone_cleaned(src):
    el = copy.deepcopy(src._element)
    # supprime tous les fils <w:r> (runs)
    for r in el.findall("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r"):
        el.remove(r)
    return el

q_tmpl = clone_cleaned(gabriol_quote)
cap_tmpl = clone_cleaned(gabriol_caption)
norm_tmpl = clone_cleaned(gabriol_norm)
h_tmpl = clone_cleaned(ancre)  # gabarit Heading 3 : utiliser un vrai Heading 3 existant

# trouver un vrai Heading 3 (sinon ancre est Heading 2)
for p in doc.paragraphs:
    if p.text.strip().startswith("3.4.4") :
        h_tmpl = clone_cleaned(p)
        break

def add_text(el, text):
    from docx.oxml.ns import qn
    r = el.makeelement(qn("w:r"), {})
    t = el.makeelement(qn("w:t"), {qn("xml:space"): "preserve"})
    t.text = text
    r.append(t)
    el.append(r)
    return el

BLOC = [
    ("h", None, "3.4.6 La documentation du système"),
    ("n", None, "L'application web comprend enfin une documentation intégrée au système. La page "
     "« Documentation API », accessible depuis le menu latéral du tableau de bord, explique "
     "comment intégrer la surveillance : l'installation du SDK JavaScript dans la page d'examen, "
     "l'appel d'initialisation avec ses options de configuration (seuils, détecteurs activés, "
     "langue, mots-clés), puis les événements envoyés et le journal de fonctionnement. Elle documente "
     "ensuite les points d'API machine, utilisés par le SDK et par une plateforme d'examen : signature "
     "des requêtes avec la clés secrète, ouverture et clôture d'une session d'examen, envoi et lecture "
     "des événements, journal de fonctionnement du SDK. Chaque point est présenté avec sa méthode, son "
     "adresse, un exemple de requête et un exemple de réponse, prêts à copier. La page est rendue côté "
     "serveur : elle fonctionne même si un site de documentation externe est inaccessible. Des liens "
     "vers les interfaces Swagger et ReDoc permettent aussi de parcourir la spécification technique de l'API."),
    ("q", "Page « Documentation API » du tableau de bord : présentation du SDK et des points d'API machine avec des exemples.", None),
    ("c", None, "Figure 3:19 : Documentation API"),
    ("n", None, "Cette documentation (Figure 3:19) est organisée par sections : SDK JavaScript, "
     "intégration machine (SDK / LMS) avec la méthode de signature, et, pour l'administrateur, la "
     "gestion des projets et des sessions. Elle relie le format des événements présenté au chapitre "
     "précédent au code concret de l'application réalisée."),
    ("q", "Onglet « Intégration » d'un projet : extrait de code d'intégration et points d'API machine prêts à copier.", None),
    ("c", None, "Figure 3:20 : Intégration d'un projet"),
    ("n", None, "Dans l'espace du développeur, l'onglet « Intégration » (Figure 3:20) de chaque projet "
     "affiche la même documentation adaptée à ce projet : les adresses réelles du serveur, la clés "
     "publique déjà mentionnée dans les extraits et la liste des demandes d'autorisation reçues. "
     "Le développeur peut ainsi raccorder sa page d'examen et sa plateforme sans quitter le tableau de bord."),
]

next_el = ancre._element
for kind, qtext, ctext in BLOC:
    if kind == "h":
        el = add_text(copy.deepcopy(h_tmpl), ctext)
    else:
        el = copy.deepcopy(norm_tmpl if kind == "n" else q_tmpl)
        el = add_text(el, qtext or ctext)
    next_el.addprevious(el)

doc.save(DOC)
print("section 3.4.6 ajoutée : La documentation du système (Figures 3:19 et 3:20)")
