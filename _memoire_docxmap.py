"""Extraction structurelle du Chapitre 3 v3.docx (paragraphes + tableaux)."""
import sys

from docx import Document

DOC = r"D:\Live_or_Die\TFC_realisation\realisations 2\Chapitre 3 v3.docx"
doc = Document(DOC)

out = open(r"D:\Live_or_Die\TFC_realisation\realisations 2\memoire_captures\docx_map.txt", "w", encoding="utf-8")

for i, p in enumerate(doc.paragraphs):
    st = p.style.name
    txt = p.text.strip()
    if txt or "Heading" in st:
        out.write(f"P{i:04d} [{st}] {txt}\n")

out.write("\n===== TABLEAUX =====\n")
for ti, tbl in enumerate(doc.tables):
    out.write(f"\n--- TABLE {ti} ({len(tbl.rows)}x{len(tbl.columns)}) ---\n")
    for ri, row in enumerate(tbl.rows):
        cells = [c.text.strip().replace("\n", " / ")[:80] for c in row.cells]
        out.write(f"R{ri}: {cells}\n")
out.close()
print("OK map écrite")
