from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

class DbConfig(BaseModel):
    """Конфигурация базы данных"""
    user: str
    password: str
    host: str
    port: int
    name: str

    def build_connection_str(self) -> str:
        """Строит строку подключения к PostgreSQL"""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

class BotConfig(BaseModel):
    """Конфигурация телеграм-бота"""
    token: str

class Config(BaseSettings):
    """Основной класс конфигурации"""
    db: DbConfig
    bot: BotConfig

    # Pydantic-settings v2+ uses model_config
    # For older versions, it would be `class Config:`
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding='utf-8',
        env_nested_delimiter='_',
        # The prefix for the main model, not the nested one.
        # We will need to adjust the .env file accordingly.
        # Let's assume DB_USER, DB_PASSWORD etc. and BOT_TOKEN
    )

# To make this work with the planned .env structure, we need to load parts separately
# as pydantic-settings doesn't handle prefixes for nested models as one might expect.

class AppConfig(BaseSettings):
    bot_token: str
    
    db_user: str
    db_password: str
    db_host: str
    db_port: int
    db_name: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding='utf-8'
    )

def load_config() -> AppConfig:
    """Loads the application configuration from .env file."""
    return AppConfig()

# A more structured way to use it in the app
class BotSettings(BaseModel):
    token: str

class DbSettings(BaseModel):
    user: str
    password: str
    host: str
    port: int
    name: str

    def build_connection_str(self) -> str:
        """Строит строку подключения к PostgreSQL"""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

class Settings(BaseModel):
    bot: BotSettings
    db: DbSettings

def get_settings() -> Settings:
    """
    Reads the environment variables from the .env file and returns a populated Settings object.
    """
    env_config = load_config()
    
    return Settings(
        bot=BotSettings(token=env_config.bot_token),
        db=DbSettings(
            user=env_config.db_user,
            password=env_config.db_password,
            host=env_config.db_host,
            port=env_config.db_port,
            name=env_config.db_name
        )
    )

settings = get_settings()

