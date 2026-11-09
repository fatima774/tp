from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration lue dans les variables d'environnement (préfixe FESTIPLAN_) ou le fichier .env.

    Elle n'est plus un objet global importé partout : seul le module de
    composition (`bootstrap.py`) la lit pour construire les dépendances.
    """

    app_name: str = "FestiPlan"
    database_url: str = "sqlite:///./festiplan.db"
    fail_notifications: bool = False
    model_config = SettingsConfigDict(env_prefix="FESTIPLAN_", env_file=".env", extra="ignore")
