# FestiPlan — version refactorisée (FATIMA BOUGRIN - NOLAN SERLAINE)

API FastAPI de gestion d'un festival metal fictif, réorganisée en **architecture hexagonale** avec un modèle **DDD**.

- Note d'architecture (diagnostic, modèle, choix, tests, limites) : [`docs/NOTE_ARCHITECTURE.md`](docs/NOTE_ARCHITECTURE.md)
- Preuve avant / après des corrections : [`docs/PREUVE_AVANT_APRES.md`](docs/PREUVE_AVANT_APRES.md)
- Diagrammes UML (composants, séquence, domaine, architecture initiale) : [`diagrammes/`](diagrammes/)

## Fonctionnalités
- Festivals, artistes, scènes et concerts
- Planning chronologique, déplacement et annulation de concerts
- Publication et **dépublication** du planning (un planning publié est verrouillé)
- Déclaration d'incidents
- Notifications simulées, avec panne configurable (une panne n'annule plus l'opération)

## Installation (Python 3.11+)

```bash
python -m venv .venv
# Windows PowerShell : .venv\Scripts\Activate.ps1
# macOS / Linux      : source .venv/bin/activate
pip install -r requirements.txt
```

## Initialisation des données de démonstration

```bash
python -m app.seed
```

Attention : cette commande **réinitialise** la base configurée (suppression puis recréation des tables). À utiliser uniquement en développement.

Données chargées : festival **Hellforge Open Air** (18 au 20 juin 2027), 4 scènes (Mainstage, Warzone, Valley, Temple), 12 artistes, 14 concerts. Toutes les données sont fictives.

## Lancement

```bash
uvicorn app.main:app --reload
```

Documentation interactive : http://127.0.0.1:8000/docs

## Configuration

Copier `.env.example` vers `.env` si nécessaire.

| Variable | Défaut | Rôle |
|---|---|---|
| `FESTIPLAN_DATABASE_URL` | `sqlite:///./festiplan.db` | Base de données |
| `FESTIPLAN_FAIL_NOTIFICATIONS` | `false` | Simule une panne du service de notification |
| `FESTIPLAN_APP_NAME` | `FestiPlan` | Titre de l'API |

## Tests

```bash
pytest            # toute la suite
pytest tests/domain        # règles métier seules (sans FastAPI ni SQLite)
pytest tests/application   # cas d'utilisation avec doubles en mémoire
pytest tests/adapters      # routes HTTP et persistance SQLAlchemy
pytest tests/regression    # les 3 défauts initiaux
pytest tests/test_architecture.py  # le sens des dépendances (domaine sans framework)
```

Qualité du code (optionnel) : `pip install ruff` puis `ruff check app tests` et `ruff format --check app tests`.

## Démonstration rapide des corrections

Après `python -m app.seed` et `uvicorn app.main:app --reload`, dans http://127.0.0.1:8000/docs :

1. `PATCH /concerts/2/reschedule` avec `{"start_time": "2027-06-18T18:30:00", "end_time": "2027-06-18T19:15:00"}` → **409**, règle R2 (défaut 1).
2. `POST /festivals/1/publish` → 200, puis `PATCH /concerts/4/reschedule` avec `{"start_time": "2027-06-18T16:00:00", "end_time": "2027-06-18T16:45:00"}` → **409**, règle R7 (défaut 3).
3. `POST /festivals/1/unpublish` → le même déplacement est accepté.
4. Arrêter le serveur, relancer avec `FESTIPLAN_FAIL_NOTIFICATIONS=true`, déplacer un concert → **200** avec `"notification_status": "failed"`, et `GET /concerts/{id}` montre bien le nouveau créneau (défaut 2).

Comparaison complète avec la version initiale : [`docs/PREUVE_AVANT_APRES.md`](docs/PREUVE_AVANT_APRES.md).

## Endpoints

| Méthode | Route | Description |
|---|---|---|
| GET / POST | `/festivals` | Lister / créer un festival |
| GET | `/festivals/{id}` | Consulter un festival |
| POST | `/festivals/{id}/publish` | Publier le planning (refusé s'il est incohérent, R8) |
| POST | `/festivals/{id}/unpublish` | Repasser en préparation pour pouvoir modifier (R7) |
| GET / POST | `/artists` | Lister / enregistrer un artiste |
| GET / POST | `/stages` | Lister (`?festival_id=`) / créer une scène |
| GET / POST | `/concerts` | Planning (`?festival_id=`) / programmer un concert |
| GET | `/concerts/schedule/{festival_id}` | Planning chronologique |
| GET | `/concerts/{id}` | Consulter un concert |
| PATCH | `/concerts/{id}/reschedule` | Déplacer un concert |
| POST | `/concerts/{id}/cancel` | Annuler un concert |
| GET / POST | `/incidents` | Lister (`?concert_id=`) / déclarer un incident |

Codes d'erreur : **400** donnée invalide ou référence inexistante, **404** ressource de l'URL introuvable, **409** conflit avec l'état actuel (chevauchement, planning publié, transition interdite, doublon). Les erreurs métier indiquent la règle concernée : `{"detail": "...", "rule": "R2"}`.

Déplacer, annuler, publier et dépublier renvoient aussi `notification_status` : `sent`, `failed` (l'opération est quand même enregistrée) ou `none`.

## Organisation du code

```
app/
├── domain/        Règles métier (aucune dépendance technique)
├── application/   Cas d'utilisation + ports (interfaces)
├── adapters/
│   ├── inbound/http/              FastAPI (contrôleurs, schémas, erreurs)
│   ├── outbound/persistence/      SQLAlchemy
│   └── outbound/notifications/    Faux e-mail
├── bootstrap.py   Assemblage des dépendances
├── main.py        Application FastAPI
└── seed.py        Données de démonstration
tests/
├── domain/  application/  adapters/  regression/
├── test_architecture.py   Vérifie le sens des dépendances
├── fakes.py       Doubles en mémoire (repositories, unité de travail, notifier)
└── builders.py    Fabriques d'objets pour les tests
docs/
├── NOTE_ARCHITECTURE.md     Note d'architecture
└── PREUVE_AVANT_APRES.md    Comparaison avec la version initiale
diagrammes/        Diagrammes UML (composants, séquence, domaine, architecture initiale)
```
