"""Code-block language allowlist and resolution.

The map mirrors the languages Confluence's *code* macro can highlight, keyed
by the aliases authors commonly write in fenced code blocks.  Values are the
canonical Confluence language identifiers.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Optional

_PLAIN_TEXT_ALIASES: frozenset[str] = frozenset(
    ("none", "output", "plain", "plaintext", "text", "txt")
)

# Constants for language IDs that appear 4+ times as dict values (WPS226).
_LANG_C_SHARP = "c#"
_LANG_KOTLIN = "kotlin"
_LANG_POWERSHELL = "powershell"
_LANG_SHELL = "shell"

_LANGUAGES = MappingProxyType(
    {
        "abap": "abap",
        "actionscript3": "actionscript3",
        "ada": "ada",
        "applescript": "applescript",
        "arduino": "arduino",
        "autoit": "autoit",
        "bash": "bash",
        "c": "c",
        "c#": _LANG_C_SHARP,
        "c++": "cpp",
        "clojure": "clojure",
        "coffeescript": "coffeescript",
        "coldfusion": "coldfusion",
        "cpp": "cpp",
        "cs": _LANG_C_SHARP,
        "csharp": _LANG_C_SHARP,
        "css": "css",
        "cuda": "cuda",
        "d": "d",
        "dart": "dart",
        "delphi": "delphi",
        "diff": "diff",
        "docker": "dockerfile",
        "dockerfile": "dockerfile",
        "elixir": "elixir",
        "erl": "erl",
        "erlang": "erl",
        "fortran": "fortran",
        "foxpro": "foxpro",
        "gherkin": "gherkin",
        "go": "go",
        "golang": "go",
        "graphql": "graphql",
        "gql": "graphql",
        "groovy": "groovy",
        "handlebars": "handlebars",
        "haskell": "haskell",
        "haxe": "haxe",
        "hbs": "handlebars",
        "hcl": "hcl",
        "hs": "haskell",
        "html": "html",
        "java": "java",
        "javafx": "javafx",
        "javascript": "js",
        "jl": "julia",
        "js": "js",
        "json": "json",
        "jsx": "jsx",
        "julia": "julia",
        "kotlin": _LANG_KOTLIN,
        "kt": _LANG_KOTLIN,
        "kts": _LANG_KOTLIN,
        "livescript": "livescript",
        "lua": "lua",
        "mathematica": "mathematica",
        "matlab": "matlab",
        "objectivec": "objectivec",
        "objectivej": "objectivej",
        "ocaml": "ocaml",
        "octave": "octave",
        "pascal": "pascal",
        "perl": "perl",
        "php": "php",
        "pl": "perl",
        "powershell": _LANG_POWERSHELL,
        "prolog": "prolog",
        "protobuf": "protobuf",
        "ps": _LANG_POWERSHELL,
        "ps1": _LANG_POWERSHELL,
        "puppet": "puppet",
        "py": "py",
        "python": "py",
        "qml": "qml",
        "r": "r",
        "racket": "racket",
        "rb": "ruby",
        "rs": "rust",
        "rst": "rst",
        "ruby": "ruby",
        "rust": "rust",
        "sass": "sass",
        "scala": "scala",
        "scheme": "scheme",
        "sh": _LANG_SHELL,
        "shell": _LANG_SHELL,
        "shellscript": _LANG_SHELL,
        "smalltalk": "smalltalk",
        "splunk": "splunk",
        "sql": "sql",
        "standardml": "standardml",
        "swift": "swift",
        "tcl": "tcl",
        "tex": "tex",
        "toml": "toml",
        "ts": "typescript",
        "tsx": "tsx",
        "typescript": "typescript",
        "vala": "vala",
        "vb": "vb",
        "verilog": "verilog",
        "vhdl": "vhdl",
        "xml": "xml",
        "xquery": "xquery",
        "yaml": "yaml",
        "yml": "yaml",
        "zsh": _LANG_SHELL,
    }
)


def resolve_language(name: Optional[str], *, force_valid: bool) -> Optional[str]:
    """Resolve a fenced-block language alias to a Confluence language id.

    Returns the canonical id for a known alias.  For an unknown alias, returns
    ``None`` when *force_valid* is set (the block renders without a language),
    otherwise the original *name* is passed through unchanged.
    """
    if name is None:
        return None
    canonical = _LANGUAGES.get(name.lower())
    if canonical is not None:
        return canonical
    return None if force_valid else name
