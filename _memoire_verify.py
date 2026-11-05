"""Vérification du document complété : reste-t-il des placeholders ?"""
from docx import Document

DOC = r"D:\Live_or_Die\TFC_realisation\realisations 2\Chapitre 3 v3 complété.docx"
doc = Document(DOC)

print("== PARAGRAPHES AVEC PLACEHOLDER OU FIGURE ==")
for i, p in enumerate(doc.paragraphs):
    t = p.text.strip()
    if ("À COMPLÉTER" in t or "À INSÉRER" in t or "[FIGURE" in t
            or t.startswith("Remarque")):
        print(f"P{i:04d}: {t[:110]}")

print("\n== EXTRAIT DES PARAGRAPHES REMPLIS ==")
for i, p in enumerate(doc.paragraphs):
    tt = p.text.strip()
    if any(k in tt for k in ("EliteBook", "HP HD Camera", "microphone intégré", "Windsurf",
                             "115 tests", "poubelle")):
        print(f"P{i:04d}: {tt[:200]}")

print("\n== TABLEAUX (dernière colonne) ==")
for ti, tbl in enumerate(doc.tables):
    for ri, row in enumerate(tbl.rows[1:], start=1):
        cells = [c.text.strip()[:60] for c in row.cells]
        print(f"T{ti} R{ri}: {cells[-1]}")
