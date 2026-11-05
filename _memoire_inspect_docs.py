"""Inspecte et corrige le bloc 3.4.6 (texte des paragraphes + styles)."""
from docx import Document

DOC = r"D:\Live_or_Die\TFC_realisation\realisations 2\Chapitre 3 v3 complété.docx"
doc = Document(DOC)

for i in range(104, 118):
    p = doc.paragraphs[i]
    print(f"P{i:04d} [{p.style.name}] {p.text.strip()[:150]!r}")
