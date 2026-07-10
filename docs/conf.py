"""Sphinx configuration for RowGuard documentation."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sphinx.application import Sphinx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

project = "RowGuard"
author = "RowGuard Contributors"
copyright = f"{datetime.now(tz=timezone.utc).year}, {author}"
release = "0.5.0"
version = "0.5"

myst_substitutions = {
    "release": release,
    "python_min": "3.10+",
}

extensions = [
    "myst_parser",
    "sphinx_copybutton",
    "sphinx_design",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
]

templates_path = ["_templates"]
exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    "requirements.txt",
    "README.md",
    "READTHEDOCS.md",
    "readme.md",  # root README wrapper; linked from GitHub, not RTD nav
    # Prefer project/* wrappers; keep legacy root wrappers out of the toctree.
    "changelog.md",
    "roadmap.md",
]

myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "fieldlist",
    "substitution",
    "tasklist",
]
myst_heading_anchors = 4
myst_url_schemes = ("http", "https", "mailto")

source_suffix = {
    ".md": "markdown",
    ".rst": "restructuredtext",
}

root_doc = "index"

html_theme = "furo"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_favicon = "_static/favicon.svg"
html_title = "RowGuard"
html_copy_source = False
html_baseurl = os.environ.get("READTHEDOCS_CANONICAL_URL", "/")

html_theme_options = {
    "light_logo": "logo.svg",
    "dark_logo": "logo-dark.svg",
    "source_repository": "https://github.com/eddiethedean/rowguard/",
    "source_branch": "main",
    "source_directory": "docs/",
    "sidebar_hide_name": True,
    "top_of_page_buttons": ["view", "edit"],
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/eddiethedean/rowguard",
            "html": '<span aria-hidden="true">◆</span> GitHub',
            "class": "",
        },
        {
            "name": "PyPI",
            "url": "https://pypi.org/project/rowguard/",
            "html": '<span class="rg-footer-pypi">PyPI</span>',
            "class": "",
        },
    ],
    "light_css_variables": {
        "color-brand-primary": "#0f766e",
        "color-brand-content": "#0d9488",
        "color-brand-visited": "#0f766e",
        "color-background-primary": "#fafbfc",
        "color-background-secondary": "#f1f5f9",
        "color-background-hover": "#e2e8f0",
        "color-background-border": "#e2e8f0",
        "color-foreground-primary": "#0f172a",
        "color-foreground-secondary": "#475569",
        "color-foreground-muted": "#64748b",
        "color-foreground-border": "#cbd5e1",
        "color-api-background": "#f8fafc",
        "color-api-background-hover": "#f1f5f9",
        "color-api-overall": "#ccfbf1",
        "color-api-keyword": "#0f766e",
        "color-api-name": "#0f172a",
        "color-api-pre-name": "#64748b",
        "font-stack": (
            "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, "
            "'Helvetica Neue', Arial, sans-serif"
        ),
        "font-stack--monospace": (
            "ui-monospace, 'SF Mono', 'Cascadia Code', 'Segoe UI Mono', "
            "Menlo, Consolas, monospace"
        ),
    },
    "dark_css_variables": {
        "color-brand-primary": "#2dd4bf",
        "color-brand-content": "#5eead4",
        "color-brand-visited": "#99f6e4",
        "color-background-primary": "#0b1120",
        "color-background-secondary": "#111827",
        "color-background-hover": "#1e293b",
        "color-background-border": "#334155",
        "color-foreground-primary": "#f1f5f9",
        "color-foreground-secondary": "#94a3b8",
        "color-foreground-muted": "#64748b",
        "color-foreground-border": "#475569",
        "color-api-background": "#0f172a",
        "color-api-background-hover": "#1e293b",
        "color-api-overall": "#134e4a",
        "color-api-keyword": "#2dd4bf",
        "color-api-name": "#f8fafc",
        "color-api-pre-name": "#94a3b8",
    },
}

pygments_style = "sphinx"
pygments_dark_style = "monokai"

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "pydantic": (
        "https://docs.pydantic.dev/latest/",
        "https://pydantic.dev/docs/validation/latest/objects.inv",
    ),
    "sqlalchemy": ("https://docs.sqlalchemy.org/en/20/", None),
}

autodoc_typehints = "none"
autodoc_member_order = "bysource"
autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
}
napoleon_google_docstring = True
napoleon_numpy_docstring = False

copybutton_prompt_text = r">>> |\.\.\. |\$ "
copybutton_prompt_is_regexp = True

suppress_warnings = ["myst.xref_missing"]

nitpick_ignore_regex = [
    (r"py:.*", r"(^T$|.*\.T$)"),
]


def _apply_myst_substitutions_in_source(
    _app: Sphinx,
    _docname: str,
    source: list[str],
) -> None:
    """Expand myst_substitutions before parse (including raw HTML blocks)."""
    text = source[0]
    for key, value in myst_substitutions.items():
        token = f"{{{{ {key} }}}}"
        if token in text:
            text = text.replace(token, value)
    source[0] = text


def setup(app: Sphinx) -> dict[str, bool]:
    app.connect("source-read", _apply_myst_substitutions_in_source)
    return {"version": "1.0", "parallel_read_safe": True}
