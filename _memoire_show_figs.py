"""Affiche les légendes de figures et leurs paragraphes d'invite."""
from docx import Document

DOC = r"D:\Live_or_Die\TFC_realisation\realisations 2\Chapitre 3 v3 complété.docx"
doc = Document(DOC)
for i, p in enumerate(doc.paragraphs):
    t = p.text.strip()
    if t.startswith("Figure 3:"):
        import re
        m = re.match(r"^Figure 3:(\d+)", t)
        if m and int(m.group(1)) in {2, 5, 6, 7, 9, 11, 12, 14, 18, 19, 20}:
            prev = doc.paragraphs[i - 1]
            prevtxt = prev.text.strip().replace("\n", " | ")[:150]
            has_pic = len(prev._element.findall(
                ".//{http://schemas.openxmlformats.org/drawingml/2006/main}blip")) > 0
            print(f"[P{i:04d}] {t[:100]}")
            print(f"   holder P{i-1:04d} style={prev.style.name!r} pic={has_pic}: {prevtxt!r}")
