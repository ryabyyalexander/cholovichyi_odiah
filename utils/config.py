from dataclasses import dataclass
from environs import Env


@dataclass
class TgBot:
    token: str


@dataclass
class Config:
    tg_bot: TgBot


def load_config(path: str | None = None) -> Config:
    env = Env()
    env.read_env(path)
    return Config(tg_bot=TgBot(token=env('BOT_TOKEN')))


def get_admin():
    env = Env()
    env.read_env()
    return env('ADMIN_IDS')
admin = int(get_admin())


def get_ellis():
    env = Env()
    env.read_env()
    return env('ELLIS')
ellis = int(get_ellis())

def get_anastasiya():
    env = Env()
    env.read_env()
    return env('ANASTASIYA')
anastasiya = int(get_anastasiya())

def get_dasha():
    env = Env()
    env.read_env()
    return env('DASHA')
dasha = int(get_dasha())

def get_vlad():
    env = Env()
    env.read_env()
    return env('VLAD')
vlad = int(get_vlad())

admins = [admin]
viewers = [admin, anastasiya, ellis, dasha, vlad] # , anastasiya, ellis
vip_users = [admin] # список для ручного додавання user_id
