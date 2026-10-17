"""
Filtres de gabarit pour l'affichage de code — coloration syntaxique CÔTÉ SERVEUR.

Pourquoi côté serveur plutôt que highlight.js (CDN) : le rendu en couleurs doit être garanti
partout et hors-ligne, sans dépendre d'un script tiers qui peut être bloqué par le navigateur
(extension de confidentialité, réseau restreint). Pygments est déjà présent dans l'environnement
(dépendance transitive) et émet des styles **en ligne** : aucune feuille de style à charger,
donc aucun conflit avec Tailwind.

Usage dans un gabarit :

    {% load code_extras %}
    <pre><code>{% filter highlight:"python" %}print("bonjour"){% endfilter %}</code></pre>
"""

from django import template
from django.utils.html import escape, format_html
from django.utils.safestring import mark_safe

register = template.Library()

try:  # Pygments est optionnel : sans lui, on retombe sur du texte échappé (jamais de 500).
    from pygments import highlight as _pyg_highlight
    from pygments.formatters import HtmlFormatter
    from pygments.lexers import get_lexer_by_name
    from pygments.util import ClassNotFound

    _PYGMENTS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PYGMENTS_AVAILABLE = False


@register.filter(name="highlight")
def highlight(code, language="text"):
    """Colore `code` selon `language` et renvoie du HTML sûr (styles en ligne).

    - `noclasses=True` : Pygments pose la couleur dans un attribut `style`, pas dans une classe
      CSS — le rendu ne dépend donc d'aucun CSS externe.
    - `nowrap=True` : pas de conteneur `<pre>`/`<div>` ajouté ; le gabarit fournit le sien.
    - `stripnl=False` : on préserve les retours à la ligne internes à l'extrait.
    En cas de langage inconnu ou de Pygments absent, on échappe simplement le texte : le code
    reste lisible, jamais exécuté.
    """
    code = code.strip("\n")
    if not _PYGMENTS_AVAILABLE:
        return escape(code)
    try:
        lexer = get_lexer_by_name(language, stripnl=False)
    except ClassNotFound:
        return escape(code)
    formatter = HtmlFormatter(nowrap=True, noclasses=True, style="monokai")
    return mark_safe(_pyg_highlight(code, lexer, formatter))


@register.tag("code_block")
def do_code_block(parser, token):
    """Bloc de code « façon éditeur » réutilisable (fenêtre + bouton copier).

    Usage ::

        {% code_block "snippet-install" "html" "index.html" %}
        <script src="https://..."></script>
        {% endcode_block %}

    Arguments : identifiant unique (utilisé comme ancre du bouton copier), langage Pygments,
    et libellé de fenêtre facultatif (le langage sert de repli). Le corps est du texte
    LITTÉRAL — il n'est pas HTML-échappé avant la coloration, on peut donc y écrire du
    HTML/JavaScript sans que les chevrons soient transformés en entités.
    """
    bits = token.split_contents()
    if len(bits) < 3:
        raise template.TemplateSyntaxError(
            "'code_block' attend au moins un identifiant et un langage."
        )
    block_id = parser.compile_filter(bits[1])
    language = parser.compile_filter(bits[2])
    filename = parser.compile_filter(bits[3]) if len(bits) > 3 else None
    nodelist = parser.parse(("endcode_block",))
    parser.delete_first_token()
    return CodeBlockNode(block_id, language, filename, nodelist)


class CodeBlockNode(template.Node):
    """Nœud du tag `code_block` (voir `do_code_block`)."""

    # En-tête commun à tous les blocs : pastilles de fenêtre + libellé + bouton copier.
    # Le bouton porte DEUX icônes (copier / validé) que dashboard.js permute, et une étiquette
    # masquée lue par les lecteurs d'écran (mise à jour en « Copié » au moment du clic).
    def __init__(self, block_id, language, filename, nodelist):
        self.block_id = block_id
        self.language = language
        self.filename = filename
        self.nodelist = nodelist

    def render(self, context):
        block_id = self.block_id.resolve(context)
        language = self.language.resolve(context)
        filename = self.filename.resolve(context) if self.filename else language
        code = self.nodelist.render(context)
        highlighted = highlight(code, language)
        return format_html(
            '<div class="mt-3 overflow-hidden rounded-lg border border-g-800 bg-g-950">'
            '<div class="flex items-center gap-1.5 border-b border-g-800 bg-g-900 px-4 py-2">'
            '<span class="h-3 w-3 rounded-full bg-red-500/80"></span>'
            '<span class="h-3 w-3 rounded-full bg-amber-400/80"></span>'
            '<span class="h-3 w-3 rounded-full bg-green-500/80"></span>'
            '<span class="ml-2 font-mono text-xs text-g-faint">{filename}</span>'
            '<button type="button" data-copy-code-target="{block_id}"'
            ' class="ml-auto rounded-md p-1.5 text-g-muted hover:bg-g-800 hover:text-g-text"'
            ' aria-label="Copier le code">'
            '<svg data-copy-icon class="h-4 w-4" viewBox="0 0 24 24" fill="none"'
            ' stroke="currentColor" stroke-width="1.5" aria-hidden="true">'
            '<rect x="9" y="9" width="11" height="11" rx="2"/>'
            '<path stroke-linecap="round" stroke-linejoin="round" d="M5 15V5a2 2 0 0 1 2-2h10"/></svg>'
            '<svg data-copy-check class="hidden h-4 w-4" viewBox="0 0 24 24" fill="none"'
            ' stroke="currentColor" stroke-width="1.5" aria-hidden="true">'
            '<path stroke-linecap="round" stroke-linejoin="round" d="m5 13 4 4L19 7"/></svg>'
            '<span data-copy-label class="sr-only">Copier le code</span>'
            '</button>'
            '</div>'
            '<pre id="{block_id}" class="overflow-x-auto p-4 text-xs leading-relaxed">'
            '<code>{code}</code></pre>'
            '</div>',
            filename=filename,
            block_id=block_id,
            code=highlighted,
        )
