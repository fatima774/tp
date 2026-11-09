"""Tests d'architecture : vérifient automatiquement le sens des dépendances.

Règle de l'architecture hexagonale : les dépendances vont vers l'intérieur.
    adaptateurs -> application -> domaine
Si quelqu'un importe SQLAlchemy dans le domaine, ou un adaptateur dans un
cas d'utilisation, ce test échoue : la règle est protégée, pas seulement documentée.
"""

import ast
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parent.parent / "app"
TECHNICAL = ("fastapi", "sqlalchemy", "pydantic", "pydantic_settings", "starlette", "uvicorn")


def imported_modules(package: str) -> list[tuple[str, str]]:
    """(fichier, module importé) pour chaque import d'un paquet de app/."""
    found = []
    for path in sorted((APP / package).rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found += [(path.name, alias.name) for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.append((path.name, node.module))
    return found


def offending(package: str, forbidden: tuple[str, ...]) -> list[str]:
    return [
        f"{file} importe {module}"
        for file, module in imported_modules(package)
        if module.split(".")[0] in forbidden or module.startswith(forbidden)
    ]


@pytest.mark.parametrize("package", ["domain", "application"])
def test_core_does_not_depend_on_technical_frameworks(package):
    assert offending(package, TECHNICAL) == []


def test_domain_depends_on_nothing_outside_itself():
    assert offending("domain", ("app.application", "app.adapters", "app.bootstrap", "app.config", "app.main")) == []


def test_application_does_not_depend_on_adapters():
    assert offending("application", ("app.adapters", "app.bootstrap", "app.main")) == []
