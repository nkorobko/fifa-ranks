"""Application configuration"""
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings"""
    
    # Database
    DATABASE_URL: str = "sqlite:///./fifa.db"
    
    # TrueSkill defaults (openskill)
    TRUESKILL_MU: float = 25.0
    TRUESKILL_SIGMA: float = 8.333
    TRUESKILL_BETA: float = 4.167  # sigma / 2
    TRUESKILL_TAU: float = 0.083   # sigma / 100 (skill decay per match)
    
    # App
    APP_NAME: str = "FIFA Ranks"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
