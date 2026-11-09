# FestiPlan — version refactorisée

API FastAPI de gestion d'un festival metal fictif, réorganisée en **architecture hexagonale** avec un modèle **DDD**.

- Note d'architecture (diagnostic, modèle, choix, tests, limites) : [`docs/NOTE_ARCHITECTURE.md`](docs/NOTE_ARCHITECTURE.md)
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
```

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
│   └── outbound/persistence/      SQLAlchemy
│   └── outbound/notifications/    Faux e-mail
├── bootstrap.py   Assemblage des dépendances
├── main.py        Application FastAPI
└── seed.py        Données de démonstration
tests/
├── domain/  application/  adapters/  regression/
├── fakes.py       Doubles en mémoire (repositories, unité de travail, notifier)
└── builders.py    Fabriques d'objets pour les tests
```
