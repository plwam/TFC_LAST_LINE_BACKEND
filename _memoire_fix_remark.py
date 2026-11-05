"""Supprime la 'Remarque pour l'auteur' du document complété (apostrophe typographique)."""
from docx import Document

DOC = r"D:\Live_or_Die\TFC_realisation\realisations 2\Chapitre 3 v3 complété.docx"
doc = Document(DOC)

removed = 0
for p in list(doc.paragraphs):
    t = p.text.strip().replace("\u2019", "'")
    if t.startswith("Remarque pour l'auteur"):
        p._element.getparent().remove(p._element)
        removed += 1

doc.save(DOC)
print("remarques supprimées:", removed)
