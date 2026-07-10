"""Sphinx configuration for RowGuard documentation."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

project = "RowGuard"
author = "RowGuard Contributors"
copyright = f"{datetime.now(tz=timezone.utc).year}, {author}"
release = "0.4.0"
version = "0.4"

extensions = [
    "myst_parser",
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
]

myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "fieldlist",
    "tasklist",
]
myst_heading_anchors = 3

source_suffix = {
    ".md": "markdown",
    ".rst": "restructuredtext",
}

master_doc = "index"

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_title = "RowGuard documentation"
html_short_title = "RowGuard"
html_show_sourcelink = True
html_copy_source = False

# Prefer the Read the Docs canonical URL when building on RTD.
html_baseurl = os.environ.get("READTHEDOCS_CANONICAL_URL", "/")

html_theme_options = {
    "collapse_navigation": False,
    "navigation_depth": 3,
    "titles_only": False,
}

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    # Current Pydantic docs inventory location (avoids intersphinx redirect noise).
    "pydantic": ("https://docs.pydantic.dev/latest/", "https://pydantic.dev/docs/validation/latest/objects.inv"),
    "sqlalchemy": ("https://docs.sqlalchemy.org/en/20/", None),
}

# Keep signatures readable without unresolved cross-ref warnings for TypeVars /
# internal plan types that are not part of the published autodoc surface.
autodoc_typehints = "none"
autodoc_member_order = "bysource"
autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
}
napoleon_google_docstring = True
napoleon_numpy_docstring = False

# Markdown docs use relative paths; do not fail the build on unresolved MyST xrefs.
suppress_warnings = ["myst.xref_missing"]

# Generic TypeVars appear in class signatures; ignore them under nitpicky builds.
nitpick_ignore_regex = [
    (r"py:.*", r"(^T$|.*\.T$)"),
]
