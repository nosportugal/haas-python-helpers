"""Code-block language allowlist and resolution.

The map mirrors the languages Confluence's *code* macro can highlight, keyed
by the aliases authors commonly write in fenced code blocks.  Values are the
canonical Confluence language identifiers.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Optional

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
        "c#": "c#",
        "clojure": "clojure",
        "coffeescript": "coffeescript",
        "coldfusion": "coldfusion",
        "cpp": "cpp",
        "csharp": "c#",
        "css": "css",
        "cuda": "cuda",
        "d": "d",
        "dart": "dart",
        "delphi": "delphi",
        "diff": "diff",
        "dockerfile": "dockerfile",
        "elixir": "elixir",
        "erl": "erl",
        "erlang": "erl",
        "fortran": "fortran",
        "foxpro": "foxpro",
        "gherkin": "gherkin",
        "go": "go",
        "graphql": "graphql",
        "groovy": "groovy",
        "handlebars": "handlebars",
        "haskell": "haskell",
        "haxe": "haxe",
        "hcl": "hcl",
        "html": "html",
        "java": "java",
        "javafx": "javafx",
        "javascript": "js",
        "js": "js",
        "json": "json",
        "jsx": "jsx",
        "julia": "julia",
        "kotlin": "kotlin",
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
        "powershell": "powershell",
        "prolog": "prolog",
        "protobuf": "protobuf",
        "puppet": "puppet",
        "py": "py",
        "python": "py",
        "qml": "qml",
        "r": "r",
        "racket": "racket",
        "rst": "rst",
        "ruby": "ruby",
        "rust": "rust",
        "sass": "sass",
        "scala": "scala",
        "scheme": "scheme",
        "shell": "shell",
        "smalltalk": "smalltalk",
        "splunk": "splunk",
        "sql": "sql",
        "standardml": "standardml",
        "swift": "swift",
        "tcl": "tcl",
        "tex": "tex",
        "toml": "toml",
        "tsx": "tsx",
        "typescript": "typescript",
        "vala": "vala",
        "vb": "vb",
        "verilog": "verilog",
        "vhdl": "vhdl",
        "xml": "xml",
        "xquery": "xquery",
        "yaml": "yaml",
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
