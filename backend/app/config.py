from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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
    GRAPH_ARTIFACTS_PATH: str = "./graph_data"
    MAX_UPLOAD_FILE_SIZE_MB: int = 1024
    MAX_PDF_PAGES: int = 1200

settings = Settings()
