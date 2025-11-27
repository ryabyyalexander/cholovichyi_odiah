# enums/profile_enum.py
from enum import Enum


class Profile(str, Enum):
    CART = "cart"
    FAVORITES = "favorites"
    ORDERS = "orders"
    SETTINGS = "settings"
    SIZE = "size"

    @property
    def label(self):
        return {
            Profile.CART: "Ваш кошик",
            Profile.ORDERS: "Мої попередні замовлення",
            Profile.FAVORITES: "Моє обране",
            Profile.SETTINGS: "Hалаштування слайдера",
            Profile.SIZE: "Мії розмір"
        }[self]

    @property
    def emoji(self) -> str:
        return {
            Profile.CART: "🛍  ",
            Profile.ORDERS: "📝  ",
            Profile.FAVORITES: "❤️  ",
            Profile.SETTINGS: "ᐅ  ",
            Profile.SIZE: "🅰️  "
        }[self]

class LoyaltyLevelEnum(Enum):
    BRONZE = 'bronze'
    SILVER = 'silver'
    GOLD = 'gold'
    DIAMOND = 'diamond'

class LoyaltyEventEnum(Enum):
    PURCHASE = 'purchase'
    REDEEM = 'redeem'
    REFERRAL = 'referral'
    PROMO = 'promo'
    SEASONAL = 'seasonal'
    MISSION = 'mission'
