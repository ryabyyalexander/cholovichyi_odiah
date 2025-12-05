from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

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

class RedisSettings(BaseModel):
    host: str
    port: int

class Settings(BaseModel):
    bot: BotSettings
    db: DbSettings
    redis: RedisSettings

class EnvConfig(BaseSettings):
    """
    Reads environment variables from the .env file.
    """
    bot_token: str
    
    db_user: str
    db_password: str
    db_host: str
    db_port: int
    db_name: str

    redis_host: str = "127.0.0.1"
    redis_port: int = 6379

    model_config = SettingsConfigDict(
        env_file="m158bot/.env",
        env_file_encoding='utf-8'
    )

def get_settings() -> Settings:
    """
    Creates a populated Settings object.
    """
    env_config = EnvConfig()
    
    return Settings(
        bot=BotSettings(token=env_config.bot_token),
        db=DbSettings(
            user=env_config.db_user,
            password=env_config.db_password,
            host=env_config.db_host,
            port=env_config.db_port,
            name=env_config.db_name
        ),
        redis=RedisSettings(
            host=env_config.redis_host,
            port=env_config.redis_port
        )
    )

settings = get_settings()

