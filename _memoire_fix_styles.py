"""Corrige le style des légendes 3:19 et 3:20 (Quote -> Normal)."""
from docx import Document

DOC = r"D:\Live_or_Die\TFC_realisation\realisations 2\Chapitre 3 v3 complété.docx"
doc = Document(DOC)

fixed = 0
for p in doc.paragraphs:
    t = p.text.strip()
    if p.style.name == "Quote" and (t.startswith("Figure 3:19") or t.startswith("Figure 3:20")):
        p.style = doc.styles["Normal"]
        fixed += 1

doc.save(DOC)
print("légendes corrigées:", fixed)
