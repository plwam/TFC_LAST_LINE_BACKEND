"""Passe finale : insère/remplace les figures restantes du document complété.

- 2, 6, 11 : composite/crop, paragraphe d'invite texte -> remplacé par l'image.
- 5, 7, 9, 12, 14, 18, 19, 20 : nouvelle capture ; l'image existante est écrasée
  si présente, sinon insérée dans le paragraphe qui précède la légende.
"""
import os
import re

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches

DST = r"D:\Live_or_Die\TFC_realisation\realisations 2\Chapitre 3 v3 complété.docx"
CAP = r"D:\Live_or_Die\TFC_realisation\realisations 2\memoire_captures"

FIGURES = {
    2: ("fig_3_2_composite.png", 6.0),
    5: ("fig_3_05_apercu.png", 5.8),
    6: ("fig_3_06_bandeau.png", 4.6),
    7: ("fig_3_07_page_test_sdk.png", 5.8),
    9: ("fig_3_09_indicateur_popup.png", 2.8),
    11: ("fig_3_11_composite.png", 6.0),
    12: ("fig_3_12_sessions_live.png", 5.8),
    14: ("fig_3_14_journal.png", 5.8),
    18: ("fig_3_18_teacher_live.png", 5.8),
    19: ("fig_3_19_docs.png", 5.8),
    20: ("fig_3_20_integration.png", 5.8),
}

BLIP = ".//{http://schemas.openxmlformats.org/drawingml/2006/main}blip"


def clear_paragraph(p):
    for r in list(p.runs):
        r._element.getparent().remove(r._element)
    # retire aussi les drawings hors runs
    for pic in p._element.findall(
        ".//{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}inline"
    ):
        pic.getparent().remove(pic)


doc = Document(DST)
targets_svg = []
for i, p in enumerate(doc.paragraphs):
    t = p.text.strip().replace("\u2019", "'")
    m = re.match(r"^Figure 3:(\d+)", t)
    if not m or i == 0:
        continue
    n = int(m.group(1))
    if n not in FIGURES:
        continue
    fname, width = FIGURES[n]
    path = os.path.join(CAP, fname)
    if not os.path.exists(path):
        targets_svg.append((n, None, fname, width))
        continue
    holder = doc.paragraphs[i - 1]
    has_pic = len(holder._element.findall(BLIP)) > 0
    texts = (n != 19 and n != 20)  # 19/20 : holder = texte descriptif à conserver
    targets_svg.append((n, holder, fname, width, texts, has_pic))

done, missing = [], {}
for item in targets_svg:
    n = item[0]
    holder, fname, width, keep_text, has_pic = item[1], item[2], item[3], item[4], item[5]
    path = os.path.join(CAP, fname)
    if not os.path.exists(path):
        missing[n] = fname
        continue
    if keep_text:
        clear_paragraph(holder)
    else:
        # lemonde 19/20 : nouveau paragraphe image entre le texte et la légende
        holder = holder.insert_paragraph_before("")
    holder.alignment = WD_ALIGN_PARAGRAPH.CENTER
    holder.add_run().add_picture(path, width=Inches(width))
    done.append(n)

ranks = [n for n in sorted(FIGURES)]
print("figures insérées:", sorted(done), "sur", ranks)
if missing:
    print("manquantes:", missing)

doc.save(DST)
print("enregistré:", DST)
