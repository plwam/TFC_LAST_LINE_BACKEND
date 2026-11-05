"""Extrait les images embarquées du docx et les sauvegarde nommées selon leur figure."""
import os

from docx import Document

DOC = r"D:\Live_or_Die\TFC_realisation\realisations 2\Chapitre 3 v3 complété.docx"
OUT = r"D:\Live_or_Die\TFC_realisation\realisations 2\memoire_captures\_docx_imgs"
os.makedirs(OUT, exist_ok=True)

doc = Document(DOC)
ns = "{http://schemas.openxmlformats.org/drawingml/2006/main}"

for i, p in enumerate(doc.paragraphs):
    blips = p._element.findall(f".//{ns}blip")
    if not blips:
        continue
    caption = doc.paragraphs[i + 1].text.strip()[:40] if i + 1 < len(doc.paragraphs) else "?"
    legende = caption.replace(":", "_").replace(" ", "_").replace("/", "_") or "sans_legende"
    rid = blips[0].get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")
    part = doc.part.related_parts[rid]
    name = f"{legende}.png"
    with open(os.path.join(OUT, name), "wb") as f:
        f.write(part.blob)
    print(f"P{i:04d} -> {name} ({len(part.blob)//1024} Ko)")

print("terminé →", OUT)
