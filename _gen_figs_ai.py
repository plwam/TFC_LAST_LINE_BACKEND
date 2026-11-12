"""Génère les figures techniques du Chapitre 3 :

- captures de code sourcé (style VS Code sombre) : agrégateur SDK, service worker de
  l'extension, modelLoader, normalisateur d'événements, calcul du risque (risk.py) ;
- schéma du flux de détection (capture → IA → agrégation → API → score → badge) ;
- image de la formule du score de risque.

Sortie : D:\\Live_or_Die\\TFC_realisation\\realisations 2\\memoire_captures
"""
import os
import re

from PIL import Image, ImageDraw, ImageFont

CAP = r"D:\Live_or_Die\TFC_realisation\realisations 2\memoire_captures"
S = 2  # facteur d'échelle (netteté à l'impression)

FONTS = {
    "code": r"C:\Windows\Fonts\consola.ttf",
    "codeb": r"C:\Windows\Fonts\consolab.ttf",
    "ui": r"C:\Windows\Fonts\segoeui.ttf",
    "uib": r"C:\Windows\Fonts\segoeuib.ttf",
    "math": r"C:\Windows\Fonts\cambria.ttc",
    "mathi": r"C:\Windows\Fonts\cambriai.ttf",
}


def font(name, size):
    return ImageFont.truetype(FONTS[name], int(size))


# --------------------------------------------------------------------------- #
# 1. Captures de code — rendu type VS Code
# --------------------------------------------------------------------------- #
C = {
    "bg": (30, 30, 30),
    "chrome": (38, 38, 38),
    "gutter": (110, 118, 129),
    "text": (212, 212, 212),
    "comment": (106, 153, 85),
    "string": (206, 145, 120),
    "keyword": (197, 134, 192),
    "number": (181, 206, 168),
    "bar": (60, 60, 60),
}

TS_KW = (
    "import|export|from|const|let|var|async|await|function|return|if|else|new|class|"
    "interface|type|implements|private|readonly|this|typeof|for|of|in|try|catch|throw|"
    "default|null|undefined|true|false|void"
)
PY_KW = (
    "from|import|def|class|return|for|in|if|else|None|True|False|isinstance|str|int|"
    "float|not|and|or|round|self|events|raw"
)


def render_code(lines, title, out, lang="ts"):
    """Bloc de code neutre (type documentation) — sans marque d'éditeur."""
    fcode = font("code", 14 * S)
    fkw = font("codeb", 14 * S)
    ftitle = font("ui", 12 * S)
    fbadge = font("uib", 10.5 * S)

    margin, header_h = 14 * S, 34 * S
    left, up, down = 64 * S, 38 * S, 24 * S
    ch_w = 9.2 * S
    lh = 20 * S
    maxline = max((len(l) for l in lines), default=0)
    W = int(left + maxline * ch_w + 40 * S + 2 * margin)
    H = int(2 * margin + header_h + len(lines) * lh + down)

    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    m, hm = margin, margin
    pw, ph, r = W - 2 * m, H - 2 * m, 12 * S
    # bloc arrondi + bandeau d'en-tête neutre (nom du fichier + badge langage)
    d.rounded_rectangle([m, m, m + pw, m + ph], radius=r, fill=C["bg"], outline=(60, 65, 75), width=S)
    d.rounded_rectangle([m, m, m + pw, m + hm + r], radius=r, fill=C["chrome"])
    d.rectangle([m, m + hm, m + pw, m + hm + 1], fill=C["bar"])
    tw = d.textlength(title, font=ftitle)
    d.text((m + 16 * S, m + (hm - 16 * S) / 2), title, font=ftitle, fill=(190, 193, 197))
    badge = "TypeScript" if lang == "ts" else "Python"
    bwid = d.textlength(badge, font=fbadge)
    bx = m + pw - bwid - 16 * S
    d.rounded_rectangle([bx, m + (hm - 20 * S) / 2, bx + bwid + 14 * S, m + (hm + 20 * S) / 2], radius=8 * S, fill=(51, 65, 85))
    d.text((bx + 7 * S, m + (hm - 14 * S) / 2), badge, font=fbadge, fill=(226, 232, 240))
    left += m
    up += m + hm
    # gouttière
    d.rectangle([left - 42 * S, up, left - 40 * S, m + ph], fill=C["bar"])

    pat = re.compile(
        r"(\"[^\"]*\"|'[^']*'|`[^`]*`//|\"[^\"]*\"|'[^']*')"
        r"|(#[^\"]*$|//.*$|/\*.*?\*/)"
        r"|(\b(?:%s)\b)"
        r"|(\b\d+(?:\.\d+)?\b)" % (TS_KW if lang == "ts" else PY_KW)
    )
    for n, line in enumerate(lines, start=1):
        y = up + (n - 1) * lh
        num = str(n)
        d.text((30 * S, y), num, font=fcode, fill=C["gutter"])
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        x = left + indent * ch_w

        def emit(seg, fill, f=None):
            nonlocal x
            if seg:
                d.text((x, y), seg, font=f or fcode, fill=fill)
                x += d.textlength(seg, font=f or fcode)

        intro_line_comment = (
            stripped.startswith("#")
            or stripped.startswith("//")
            or stripped.startswith("*")
            or stripped.startswith("/*")
            or stripped.startswith('"""')
            or stripped.startswith("'''")
        )
        if intro_line_comment:
            emit(line, C["comment"])
            continue
        emit(line[:indent], C["text"])
        rest = stripped
        pos = 0
        for m in pat.finditer(rest):
            if m.start() > pos:
                emit(rest[pos : m.start()], C["text"])
            if m.group(1) or m.group(2):
                # une string qui finit par // — improbable ; on reteste
                tok = m.group(0)
                if tok.startswith(("#", "//", "/*")):
                    emit(tok, C["comment"])
                else:
                    emit(tok, C["string"])
            elif m.group(3):
                emit(m.group(3), C["keyword"], f=fkw)
            else:
                emit(m.group(4), C["number"])
            pos = m.end()
        if pos < len(rest):
            emit(rest[pos:], C["text"])

    out_path = os.path.join(CAP, out)
    img.save(out_path)
    print("écrit", out, f"{W}x{H}")


def read_lines(path, a, b=None):
    with open(path, encoding="utf-8") as fh:
        all_l = fh.read().splitlines()
    return all_l[a - 1 : b] if b else all_l[a - 1 : a]


def read_ranges(path, ranges):
    out = []
    for a, b in ranges:
        if out:
            out.append("…")
        out.extend(read_lines(path, a, b))
    return out


ROOT = r"D:\Live_or_Die\TFC_realisation\realisations 2"

render_code(
    read_ranges(os.path.join(ROOT, "SDK\\src\\ai\\BehaviorAggregator.ts"), [(1, 12), (28, 61)]),
    "BehaviorAggregator.ts — SDK/src/ai",
    "fig_3_code_aggregator.png",
    "ts",
)
render_code(
    read_ranges(os.path.join(ROOT, "EXTENSION\\src\\background\\tabActivityDetector.ts"), [(13, 46)]),
    "tabActivityDetector.ts — EXTENSION/src/background",
    "fig_3_code_ext_tabs.png",
    "ts",
)
render_code(
    read_ranges(os.path.join(ROOT, "SDK\\src\\ai\\modelLoader.ts"), [(1, 11), (38, 77)]),
    "modelLoader.ts — SDK/src/ai",
    "fig_3_code_modelloader.png",
    "ts",
)
render_code(
    read_ranges(os.path.join(ROOT, "SDK\\src\\events\\EventNormalizer.ts"), [(27, 55)]),
    "EventNormalizer.ts — SDK/src/events",
    "fig_3_code_normalizer.png",
    "ts",
)
render_code(
    read_ranges(os.path.join(ROOT, "backend\\apps\\sessions\\risk.py"), [(24, 59)]),
    "risk.py — backend/apps/sessions",
    "fig_3_code_risk.png",
    "py",
)

# --------------------------------------------------------------------------- #
# 2. Schéma du flux de détection
# --------------------------------------------------------------------------- #
def draw_flow():
    f_t = font("uib", 15 * S)
    f_b = font("ui", 12.6 * S)
    f_g = font("uib", 11 * S)
    f_net = font("ui", 11.5 * S)
    W, H = 1580 * S, 700 * S
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    m, gap = 40 * S, 40 * S
    bw = (W - 2 * m - 3 * gap) / 4
    bh, top1, top2 = 150 * S, 140 * S, 460 * S
    g1_y, g2_y = top1 - 46 * S, top2 - 46 * S

    boxes = [
        (1, "Page d'examen", "consentement caméra / micro", "flux vidéo, audio, DOM, onglets"),
        (2, "Workers IA", "FaceMesh · COCO-SSD", "HandPose · Vosk → mesures brutes"),
        (3, "Agrégateur de comportement", "durée, répétition, hystérésis", "mesure brute → signal interprété"),
        (4, "Normalisation d'événement", "type, gravité, libellé FR/EN", "confidence_score, event_id"),
        (8, "Tableau de bord", "badge risque + chronologie", "détails techniques dépliables"),
        (7, "Tâche Celery", "compute_risk_score_task", "R = 1 − e^(−S) · recalcul asynchrone"),
        (6, "API Django", "signature, période, projet", "écriture immuable (table events)"),
        (5, "Requête authentifiée", "POST /machine/… + HMAC-SHA256", "file d'attente si coupure réseau"),
    ]
    for i, (num, t1, t2, t3) in enumerate(boxes):
        x = m + (i % 4) * (bw + gap)
        y = top1 if i < 4 else top2
        d.rounded_rectangle([x, y, x + bw, y + bh], radius=10 * S, fill=(248, 250, 252), outline=(51, 65, 85), width=2 * S)
        d.rounded_rectangle([x, y, x + bw, y + 8 * S], radius=4 * S, fill=(51, 65, 85))
        # badge numéroté (dessiné : les caractères ①.. ne sont pas fiables à cette police)
        rr = 11 * S
        tw = d.textlength(t1, font=f_t)
        total = rw_b = 2 * rr + 9 * S + tw
        cx0 = x + (bw - total) / 2
        cy = y + 20 * S + rr
        d.ellipse([cx0, cy - rr, cx0 + 2 * rr, cy + rr], outline=(51, 65, 85), width=2 * S, fill=(255, 255, 255))
        fs = font("uib", 13 * S)
        dn = str(num)
        d.text((cx0 + rr - d.textlength(dn, font=fs) / 2, cy - 9 * S), dn, font=fs, fill=(51, 65, 85))
        d.text((cx0 + 2 * rr + 9 * S, y + 20 * S), t1, font=f_t, fill=(15, 23, 42))
        ty = y + 20 * S + 2 * rr + 14 * S
        for seg in (t2, t3):
            w = d.textlength(seg, font=f_b)
            d.text((x + (bw - w) / 2, ty), seg, font=f_b, fill=(71, 85, 105))
            ty += 30 * S

    def group(y, label):
        d.rounded_rectangle([m - 14 * S, y, W - m + 14 * S, (top2 + bh + 30 * S) if y == g1_y else top2 + bh + 30 * S], radius=16 * S, outline=(186, 194, 203), width=1 * S)
        w = d.textlength(label, font=f_g)
        d.rounded_rectangle([m + 30 * S, y - 16 * S, m + 30 * S + w + 24 * S, y + 16 * S], radius=8 * S, fill=(255, 255, 255), outline=(186, 194, 203), width=S)
        d.text((m + 42 * S, y - 12 * S), label, font=f_g, fill=(100, 116, 139))

    group(g1_y, "SDK — navigateur de l'étudiant")
    group(g2_y, "Backend Django (serveur) + tableau de bord")

    def arrow(p1, p2):
        color, u, head = (71, 85, 105), S, 12 * S
        x1, y1, x2, y2 = *p1, *p2
        d.line([x1, y1, x2, y2], fill=color, width=3 * u)
        if abs(x2 - x1) >= abs(y2 - y1):
            s = 1 if x2 >= x1 else -1
            d.polygon([(x2, y2), (x2 - s * head, y2 - head * 0.55), (x2 - s * head, y2 + head * 0.55)], fill=color)
        else:
            s = 1 if y2 >= y1 else -1
            d.polygon([(x2, y2), (x2 - head * 0.55, y2 - s * head), (x2 + head * 0.55, y2 - s * head)], fill=color)

    for i in range(3):  # ligne 1 : →
        y = top1 + bh / 2
        arrow((m + i * (bw + gap) + bw, y), (m + (i + 1) * (bw + gap), y))
    for i in range(3):  # ligne 2 : ⑤→⑥→⑦→⑧ (droite → gauche)
        y = top2 + bh / 2
        arrow((m + (3 - i) * (bw + gap), y), (m + (3 - i) * (bw + gap) - gap, y))

    # flèche descendante ④→⑤ + étiquette réseau
    xmf = m + 3 * (bw + gap) + bw / 2
    y_mid = (top1 + bh + g2_y) / 2
    arrow((xmf, top1 + bh + 30 * S + 6 * S), (xmf, top2 - 34 * S))
    net = "réseau local — HTTP POST signé (HMAC-SHA256)"
    wnet = d.textlength(net, font=f_net)
    d.rectangle([xmf - wnet / 2 - 12 * S, y_mid - 15 * S, xmf + wnet / 2 + 12 * S, y_mid + 15 * S], fill=(255, 255, 255), outline=(176, 186, 197), width=S)
    d.text((xmf - wnet / 2, y_mid - 11 * S), net, font=f_net, fill=(100, 116, 139))

    out = os.path.join(CAP, "fig_3_flux_ia.png")
    img.save(out)
    print("écrit", "fig_3_flux_ia.png", f"{W}x{H}")


draw_flow()

# --------------------------------------------------------------------------- #
# 3. Formule du score de risque (image)
# --------------------------------------------------------------------------- #
def draw_formula():
    fm = font("math", 24 * S)
    fmi = font("mathi", 24 * S)
    fm_big = font("math", 32 * S)
    fmi_big = font("mathi", 32 * S)
    f_note = font("ui", 14 * S)
    W, H = 1240 * S, 300 * S
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)

    def draw_seg(x, y, text, style, big):
        """style : 'i' italique, 'n' normal, 'sub'/isub indice, 'sup' exposant."""
        base = (fm_big if big else fm)
        ital = (fmi_big if big else fmi)
        if style in ("sub", "isub"):
            f = font("mathi" if style == "isub" else "math", (32 if big else 24) * S * 0.72)
            d.text((x, y + 8 * S), text, font=f, fill=(15, 23, 42))
            return d.textlength(text, font=f)
        if style == "sup":
            f = font("math", (32 if big else 24) * S * 0.72)
            d.text((x + 1 * S, y - 12 * S), text, font=f, fill=(15, 23, 42))
            return d.textlength(text, font=f) + 2 * S
        f = ital if style == "i" else base
        d.text((x, y), text, font=f, fill=(15, 23, 42))
        return d.textlength(text, font=f)

    def line(y, segs, big=False):
        yy = y * S
        x = 60 * S
        for text, style in segs:
            x += draw_seg(x, yy, text, style, big)

    def note(y, text):
        d.text((W - 355 * S, y * S + 8 * S), text, font=f_note, fill=(100, 116, 139))

    line(34, [
        ("w(e) = w", "i"), ("cat", "sub"), ("(e) · m", "i"), ("conf", "sub"),
        ("(e)", "i"), ("  ×  1,5  si e est critique, sinon × 1", "n"),
    ])
    note(34, "poids par catégorie + coefficient critique")
    line(94, [
        ("m", "i"), ("conf", "sub"), ("(e) = 0,5 + 0,5 × conf(e)", "i"),
    ])
    note(94, "facteur de confiance d'un détecteur")
    line(154, [
        ("S = Σ w(e)", "i"),
    ])
    note(154, "somme sur tous les événements de la session")
    line(214, [
        ("R = 1 − e", "i"), ("−S", "sup"),
        ("    (borné dans [0, 1])", "n"),
    ], big=True)
    note(214, "saturation exponentielle → jamais 0 ou 1 brut")
    # cadre discret autour de la formule finale
    d.rounded_rectangle([48 * S, 200 * S, 720 * S, 268 * S], radius=10 * S, outline=(203, 213, 225), width=S)

    out = os.path.join(CAP, "fig_3_formule_score.png")
    img.save(out)
    print("écrit", "fig_3_formule_score.png", f"{W}x{H}")


draw_formula()
