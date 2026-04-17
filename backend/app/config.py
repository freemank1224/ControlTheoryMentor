from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # API
    API_PREFIX: str = "/api"

    # Storage
    PDF_STORAGE_PATH: str = "./pdfs"
    MAX_PDF_PAGES: int = 1200

    class Config:
        env_file = ".env"

settings = Settings()
