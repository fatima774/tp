# Note d'architecture — Refactorisation de FestiPlan

Schémas dans le dossier `diagrammes/` :

| Fichier | Contenu |
|---|---|
| `architecture_initiale.pdf` | Diagnostic de l'architecture de départ (étape 1) |
| `modèle_du_domaine.pdf` | Modèle du domaine DDD (étape 2) |
| `diagramme_de_composants.pdf` | **Diagramme UML de composants** (architecture finale) |
| `séquence_déplacer_un_concert.pdf` | **Diagramme UML de séquence** : déplacement d'un concert |


---

## 1. Diagnostic de l'architecture initiale

### Responsabilités et dépendances constatées

| Partie | Rôle prévu | Ce qu'elle faisait réellement |
|---|---|---|
| `api/` (contrôleurs) | Recevoir les requêtes HTTP | Requêtes SQL directes (`get_concert`, `reschedule_concert`, tout `incidents.py`), règle R1 en double, `commit` dans `incidents.py` |
| `services/` | Logique métier | Dépend de la `Session` SQLAlchemy, contourne ses repositories avec `db.query`, instancie elle-même `NotificationService` |
| `repositories/` | Accès aux données | Font le `commit` : ce sont eux qui terminent la transaction |
| `models.py` | — | Tables SQLAlchemy utilisées comme modèle métier ; statuts en texte libre, équipements en chaîne CSV |
| `utils/email_sender.py` | Envoi d'e-mails | Lit l'objet global `settings` |

### Où se trouvaient les règles métier

| Règle | Emplacement initial | Problème |
|---|---|---|
| R1 | contrôleur + service | dupliquée |
| R2, R3 | `_check_conflicts`, appelé **uniquement à la création** | absente au déplacement (défaut 1) |
| R4, R5, R6 | `create_concert` | R6 absente au déplacement |
| R7 | **nulle part** | défaut 3 |
| R8 | **nulle part** | publication d'un planning incohérent possible |
| R9 | Pydantic (`gt=0`) | protégée seulement via HTTP |
| R10 | contrôleur + Pydantic | une description composée d'espaces est acceptée |

### Exemple concret de responsabilité mal placée

`PATCH /concerts/{id}/reschedule` était réparti sur trois couches, sans qu'aucune ne soit responsable de l'ensemble :

1. le **contrôleur** cherche le concert en SQL et vérifie R1 ;
2. le **service** revérifie R1, modifie le concert, fait le **commit**, puis envoie la notification ;
3. si la notification lève `RuntimeError`, le **contrôleur** la traduit en **HTTP 500**, alors que la base est déjà modifiée.

### Problèmes de testabilité et risques d'incohérence

- Impossible de tester une règle sans démarrer SQLite : les règles sont mélangées aux requêtes.
- Impossible de remplacer la notification par un double de test : elle est instanciée en dur et lit une configuration globale.
- Chaque repository commite séparément : une opération qui touche plusieurs tables peut être enregistrée à moitié.
- Les 6 tests existants ne vérifiaient que la validation HTTP (422/400/404), aucune règle métier.

### Autres défauts relevés pendant l'exploration

| Scénario (jeu de démo) | Réponse initiale |
|---|---|
| Doublon de nom d'artiste | 500 (`IntegrityError` non gérée) |
| Dates avec fuseau (`+02:00`) | 500 (comparaison de dates avec et sans fuseau) |
| Déplacer un concert annulé | 200 |
| Annuler deux fois le même concert | 200 |
| Incident avec la description `"   "` | 201 |
| Équipement `"a,b"` | découpé en `["a", "b"]` |
| `alembic.ini` | pointe vers un dossier `migrations/` inexistant |

---

## 2. Modèle du domaine (DDD)

### Objets-valeurs

Ils sont immuables et se valident à la création : un objet invalide ne peut pas exister en mémoire.

| Objet-valeur | Règle portée | Comportement |
|---|---|---|
| `TimeSlot` (créneau) | R1 : fin > début ; dates sans fuseau | `overlaps()` |
| `FestivalPeriod` | fin > début | `contains(slot)` → R6 |
| `EquipmentSet` | noms non vides, sans doublon | `missing_from()` → R5 |
| `Capacity` | R9 : > 0 | — |

### Entités

`Festival`, `Stage`, `Concert`, `Artist`, `Incident`. Elles ont un identifiant : deux concerts aux mêmes horaires restent deux concerts distincts.

### Agrégats retenus et justification

**1. Agrégat Festival** (racine `Festival`, entités internes `Stage` et `Concert`)

C'est le seul objet qui voit **tous** les concerts du festival en même temps. Or R2, R3, R4, R6, R7 et R8 ont toutes besoin de cette vue d'ensemble. Toute modification du planning passe donc par ses méthodes : `schedule_concert`, `reschedule_concert`, `cancel_concert`, `publish`, `unpublish`, `add_stage`. Il n'existe aucun autre moyen de modifier un concert, ce qui rend impossible de contourner une règle (la cause du défaut 1).

**2. Agrégat Artist**

Un artiste existe indépendamment des festivals. Les concerts le référencent par son identifiant. Pour R5, le cas d'utilisation charge l'artiste et le passe à l'agrégat Festival.

**3. Agrégat Incident**

Il est déclaré pendant le festival, sans rapport avec la cohérence du planning. Le mettre dans Festival obligerait à charger et verrouiller tout le planning pour enregistrer un incident. Il référence le concert par son identifiant.

**Choix écartés :**
- Un agrégat par classe (Concert séparé) : impossible alors de garantir R2 et R3 sans logique dispersée.
- Un seul agrégat global : l'artiste et l'incident n'ont pas d'invariant commun avec le planning.

### Invariants et lieu de garantie

| Règle | Où elle est garantie | Pourquoi là |
|---|---|---|
| R1 | `TimeSlot` | ne dépend que du créneau lui-même |
| R2, R3, R6 | agrégat `Festival` (`_ensure_no_conflict`, `_ensure_within_period`) | demande la vue de tous les concerts |
| R4 (scène ∈ festival) | agrégat `Festival` | les scènes sont dans l'agrégat |
| R4 (festival / artiste existants) | cas d'utilisation | demande un accès au repository |
| R5 | agrégat `Festival` (reçoit l'`Artist`) | compare l'artiste et la scène |
| R7 | agrégat `Festival` (`_ensure_modifiable`) | dépend de l'état du planning |
| R8 | `Festival.publish()` → `planning_violations()` | revérifie tout le planning |
| R9 | `Capacity` | ne dépend que de la valeur |
| R10 (description) | `Incident.report()` | ne dépend que de l'incident |
| R10 (concert existant) | cas d'utilisation `ReportIncident` | demande un accès au repository |

Pydantic ne fait plus que valider le **format** des requêtes. Toutes les règles métier s'appliquent aussi sans passer par HTTP. Par exemple, `seed.py` crée les données via les cas d'utilisation, ce qui garantit que le jeu de démonstration respecte toutes les règles.

### États du planning

```
PREPARATION --publish() [R8 respectée]--> PUBLISHED
PUBLISHED   --unpublish()-------------->  PREPARATION
```

Un concert passe de `SCHEDULED` à `CANCELLED` (sans retour possible).

### Commande / cas d'utilisation / événement / réaction

| Notion | Exemple |
|---|---|
| Commande (ce qui est demandé) | `RescheduleConcertCommand(concert_id, start, end)` |
| Cas d'utilisation (qui orchestre) | `RescheduleConcert.execute()` |
| Événement (le fait accompli) | `ConcertRescheduled` (aussi `ConcertCancelled`, `PlanningPublished`, `PlanningUnpublished`) |
| Mécanisme technique (qui réagit) | `EventDispatcher` → port `Notifier` → `FakeEmailNotifier` |

---

## 3. Architecture hexagonale : responsabilités par couche

```
app/
├── domain/                  Cœur métier : AUCUN import de FastAPI, SQLAlchemy ou Pydantic
│   ├── value_objects.py     TimeSlot, FestivalPeriod, EquipmentSet, Capacity
│   ├── festival.py          Agrégat Festival (+ Stage, Concert, statuts)
│   ├── artist.py / incident.py
│   ├── events.py            Événements de domaine
│   └── errors.py            Erreurs métier (avec la référence R1..R10)
├── application/             Cas d'utilisation + ports
│   ├── ports.py             Contrats : repositories, UnitOfWork, Notifier
│   ├── use_cases/           festivals, catalog (artistes/scènes), concerts, incidents
│   ├── events.py            EventDispatcher (gestion de l'échec de notification)
│   ├── dto.py               Vues renvoyées aux adaptateurs
│   └── errors.py            NotFound, InvalidReference, AlreadyExists
├── adapters/
│   ├── inbound/http/        Contrôleurs FastAPI, schémas Pydantic, erreurs -> codes HTTP
│   └── outbound/
│       ├── persistence/     Tables SQLAlchemy, repositories, unité de travail
│       └── notifications/   FakeEmailNotifier
├── bootstrap.py             Composition root : crée et injecte les dépendances
├── config.py
├── main.py                  create_app() + app (pour uvicorn)
└── seed.py
```

**Le sens des dépendances va toujours vers l'intérieur :** adaptateurs → application → domaine. Le domaine ne dépend de rien. L'application ne dépend que des ports (des interfaces). On peut le vérifier avec `grep -rE "fastapi|sqlalchemy|pydantic" app/domain app/application`, qui ne renvoie rien.

| Couche | Responsabilité |
|---|---|
| Domaine | Règles métier et invariants, transitions d'état, production des événements |
| Application | Orchestration : construire les objets-valeurs, charger, appeler l'agrégat, enregistrer, commiter, puis notifier |
| Adaptateur HTTP | Format des requêtes, appel du cas d'utilisation, traduction erreur → code HTTP |
| Adaptateur persistance | Traduction tables ↔ objets métier, transaction |
| Adaptateur notification | Formatage et envoi du message |
| Composition root | Choix des implémentations concrètes |

---

## 4. Ports et adaptateurs

| Port (dans `application/ports.py`) | Utilité | Adaptateur de production | Double de test |
|---|---|---|---|
| `FestivalRepository` | charger et enregistrer l'agrégat Festival entier | `SqlAlchemyFestivalRepository` | `InMemoryFestivalRepository` |
| `ArtistRepository` | artistes, unicité du nom | `SqlAlchemyArtistRepository` | `InMemoryArtistRepository` |
| `IncidentRepository` | incidents | `SqlAlchemyIncidentRepository` | `InMemoryIncidentRepository` |
| `UnitOfWork` | regroupe les repositories, **décide du commit** | `SqlAlchemyUnitOfWork` | `FakeUnitOfWork` |
| `Notifier` | réagir aux événements de domaine | `FakeEmailNotifier` | `RecordingNotifier` (peut simuler une panne) |

**Port entrant :** les cas d'utilisation eux-mêmes (`RescheduleConcert.execute(command)`, etc.). Le contrôleur FastAPI est l'**adaptateur entrant** qui les appelle ; il n'est pas le port.

**Assemblage des dépendances :** `bootstrap.py` crée l'engine, la fabrique de sessions et le notifier (en panne si `FESTIPLAN_FAIL_NOTIFICATIONS=true`), puis fournit les cas d'utilisation. Les contrôleurs obtiennent ce conteneur via `Depends(get_container)`. Les cas d'utilisation n'instancient jamais eux-mêmes un repository SQL ou un client de notification.

**Pourquoi une unité de travail :** dans la version initiale, chaque repository faisait `commit()`. Ici les repositories font au plus un `flush` (pour obtenir les identifiants), et c'est le cas d'utilisation qui appelle `uow.commit()`. Si une règle échoue, la sortie du bloc `with uow:` annule tout.

---

## 5. Correction des trois défauts

### Défaut 1 : chevauchement de concerts

- **Cause :** le déplacement ne passait pas par `_check_conflicts`.
- **Correction :** `Festival.reschedule_concert()` applique les mêmes contrôles que la programmation (R2, R3, R6, R7). Le concert déplacé est exclu de la comparaison avec lui-même. Les concerts annulés ne bloquent pas de créneau, et un concert annulé ne peut plus être déplacé.
- **Réponses :** 409 pour R2 et R3, 400 pour R6, avec le champ `rule` dans le corps de la réponse.

### Défaut 2 : échec de notification après modification

- **Règle retenue :** la notification est un **effet secondaire**. L'opération métier réussit dès que le commit est fait.
- **Correction :** le cas d'utilisation commite, **puis** transmet les événements à `EventDispatcher`. Celui-ci attrape toute erreur du notifier, la journalise et renvoie `FAILED`. L'API répond **200** avec `notification_status: "failed"` : le client sait que la modification est enregistrée et que la notification n'est pas partie.
- La même correction s'applique à la publication, à la dépublication et à l'annulation, qui avaient le même défaut.
- **Pourquoi ce choix :** il est proportionné au projet. Une solution « outbox » avec renvoi asynchrone serait plus robuste (voir les limites), mais elle demande une table et un processus en plus.

### Défaut 3 : modification d'un planning publié

- **Règle retenue :** un planning publié est **verrouillé**. Programmer, déplacer et annuler sont refusés (409, R7). La procédure explicite est la **dépublication préalable** : `POST /festivals/{id}/unpublish` → modification → `POST /festivals/{id}/publish`, qui revérifie tout le planning (R8).
- **Pourquoi la dépublication** plutôt qu'une procédure de modification spécifique : c'est la transition la plus simple à comprendre et à tester. Elle produit un événement `PlanningUnpublished` qui prévient l'équipe que le planning public n'est plus figé, et elle force une nouvelle validation complète avant la republication.
- Ajouter une scène reste possible après publication, car cela ne modifie pas le planning des concerts.
- **R8 :** `publish()` refuse un planning incohérent et renvoie la liste des violations. C'est utile pour les bases remplies par l'ancienne version, qui peuvent contenir des chevauchements.

### Preuve avant / après

Scénarios rejoués par l'API sur le jeu de démonstration.

| Scénario | Version initiale | Version refactorisée |
|---|---|---|
| Déplacer Crimson Engine (#2) sur 18h30-19h15, Mainstage occupée | **200** (chevauchement créé) | 409 R2 |
| Déplacer Iron Vow J2 (#13) le 18/06 à 18h, pendant son autre concert | **200** | 409 |
| Déplacer un concert en 2030 | **200** | 400 R6 |
| Publier un planning contenant des chevauchements | **200** | 409 R8 + liste des violations |
| Déplacer un concert après publication | **200** | 409 R7 |
| Annuler / créer un concert après publication | **200 / 201** | 409 R7 |
| Déplacer avec le service de notification en panne | **500**, alors que la modification est enregistrée | 200 + `notification_status: "failed"` |
| Publier avec le service de notification en panne | **500**, alors que le statut est `published` | 200 + `notification_status: "failed"` |
| Incident avec la description `"   "` | **201** | 400 R10 |
| Doublon d'artiste | **500** | 409 |
| Dates avec fuseau horaire | **500** | 400 |

Ces scénarios sont automatisés dans `tests/regression/test_known_defects.py`.

---

## 6. Stratégie de tests

`pytest` : **105 tests**, environ 7 secondes.

| Niveau | Dossier | Contenu | Dépendances |
|---|---|---|---|
| Unitaires du domaine | `tests/domain/` | créneaux invalides, chevauchements, R1 à R10, transitions d'état, événements produits | **aucune** (ni FastAPI ni SQLite) |
| Cas d'utilisation | `tests/application/` | programmation, déplacement, publication, gestion des erreurs, commit ou pas, appels au notifier, panne de notification | doubles en mémoire (`tests/fakes.py`) |
| Adaptateurs | `tests/adapters/` | routes HTTP et codes de retour, aller-retour de l'agrégat en base, pas d'écriture sans commit, lecture de l'ancien format CSV, faux e-mail | SQLite temporaire (une base par test) |
| Non-régression | `tests/regression/` | les 3 défauts + R8 sur des données incohérentes | API + SQLite + jeu de démo |

Les 6 tests de la version initiale sont conservés tels quels dans `tests/adapters/test_http_api.py` et passent toujours.

Les fixtures (`tests/conftest.py`) créent l'application avec `create_app(settings, notifier)`. On peut donc injecter une base temporaire et un notifier en panne, sans variable d'environnement ni objet global.

---

## 7. Limites restantes et compromis

- **Taille de l'agrégat :** chaque opération charge tout le festival (scènes et concerts). C'est acceptable pour quelques dizaines de concerts. Pour des milliers, il faudrait découper (par exemple un agrégat par jour ou par scène) et déplacer R3 dans un service de domaine.
- **Concurrence :** deux déplacements simultanés pourraient chacun passer la vérification puis être enregistrés. Correction possible : verrouillage optimiste (colonne `version` sur `festivals`, `version_id_col` de SQLAlchemy).
- **R3 limitée à un festival :** un artiste programmé au même moment dans deux festivals différents n'est pas détecté (même comportement que la version initiale).
- **Notifications perdues :** un échec est journalisé et signalé au client, mais pas renvoyé automatiquement. Évolution possible : pattern *outbox* (enregistrer les événements dans la même transaction, puis les envoyer depuis une tâche séparée avec des tentatives successives).
- **Choix des codes HTTP :** les conflits passent de 400 à **409**, et une référence inexistante dans le corps (festival ou concert) renvoie **400** au lieu de 404 pour les incidents. C'est un changement de contrat, documenté ici. Les tests hérités passent toujours.
- **Réponses enrichies :** déplacer, annuler, publier et dépublier ajoutent le champ `notification_status`. L'ajout d'un champ ne casse pas les clients existants.
- **Migrations :** le schéma de la base est inchangé (mêmes tables, mêmes colonnes). Les équipements sont maintenant stockés en JSON, et l'ancien format CSV reste lu. `alembic.ini`, qui pointait vers un dossier inexistant, a été supprimé, ainsi que la dépendance `alembic`.
- **Dates :** le domaine utilise l'heure locale du festival, sans fuseau. Les dates avec fuseau sont refusées plutôt que converties.
