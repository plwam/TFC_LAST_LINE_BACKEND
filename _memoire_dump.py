"""Dump de la structure du document complété (titres, placeholders, images)."""
import sys

from docx import Document

DOC = r"D:\Live_or_Die\TFC_realisation\realisations 2\Chapitre 3 v3 complété.docx"
doc = Document(DOC)

print("== TITRES ET PARAGRAPHES FIGURES ==")
for i, p in enumerate(doc.paragraphs):
    t = p.text.strip()
    style = p.style.name if p.style else ""
    if style.startswith("Heading") or "[FIGURE" in t or t.startswith("Figure 3:"):
        print(f"P{i:04d} [{style}] {t[:120]}")

print("\n== IMAGES PRESENTES (inline) ==")
ns = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
for i, p in enumerate(doc.paragraphs):
    if p._element.findall(f".//{ns}blip"):
        print(f"P{i:04d} [image] (paragraphes autour: '{doc.paragraphs[i+1].text.strip()[:80]}' puis '{doc.paragraphs[i+2].text.strip()[:60]}')")

print("\n== TABLEAUX ==")
for ti, tbl in enumerate(doc.tables):
    print(f"TABLE {ti}: {len(tbl.rows)}x{len(tbl.columns)} | 1re ligne: {[c.text.strip()[:25] for c in tbl.rows[0].cells]}")
