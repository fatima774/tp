# Preuve avant / après

Les mêmes requêtes HTTP ont été rejouées sur la **version initiale** fournie et sur la **version refactorisée**, chacune avec son jeu de démonstration (`python -m app.seed`), dans le même ordre.

| Scénario | Version initiale | Version refactorisée |
|---|---|---|
| D1 — Crimson Engine (#2) déplacé sur la Mainstage déjà occupée (18h30-19h15) | **200** (chevauchement créé) | 409 (R2) |
| D1 — Iron Vow J2 (#13) déplacé pendant son concert du 18/06 | **200** | 409 |
| R6 — concert déplacé en 2030, hors festival | **200** | 400 (R6) |
| R8 — publication du planning | **200**, alors que le planning contient les conflits créés ci-dessus | 200 (les conflits ont été refusés, le planning est valide) |
| D3 — déplacement après publication | **200** | 409 (R7) |
| D3 — annulation après publication | **200** | 409 (R7) |
| D2 — déplacement avec le service d'e-mail en panne | **500**, alors que le concert est bien déplacé en base | 200 + `notification_status: "failed"` (concert déplacé) |
| R10 — incident avec une description faite d'espaces | **201** | 400 (R10) |
| Doublon de nom d'artiste | **500** (erreur SQL non gérée) | 409 |

En gras : les comportements incorrects de la version initiale.

La publication d'un planning **incohérent** (R8) ne peut plus être provoquée par l'API, puisque les conflits sont refusés en amont. Elle est donc testée en insérant directement un chevauchement en base, comme l'aurait laissé l'ancienne version : `tests/regression/test_known_defects.py::test_r8_inconsistent_legacy_planning_cannot_be_published` (réponse 409 + liste des violations).

## Tests automatisés correspondants

Chaque ligne du tableau est couverte par un test de `tests/regression/test_known_defects.py` ou de `tests/adapters/test_http_api.py`. Sur la version initiale, ces scénarios produisaient les codes en gras ci-dessus : les tests correspondants auraient échoué.

```bash
pytest tests/regression -v
```
