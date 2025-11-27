# enums/main_section.py
from enum import Enum

class Filters(str, Enum):
    CATEGORIES = "categories"
    SEASONS = "seasons"
    BRANDS = "brands"
    SIZES = "sizes"


    @property
    def label(self):
        return {
            Filters.CATEGORIES: "Категорії",
            Filters.SEASONS: "Сезони",
            Filters.BRANDS: "Бренди",
            Filters.SIZES: "Розміри",

        }[self]

    @property
    def emoji(self) -> str:
        """
        Возвращает эмодзи, подходящий для сезона (по желанию).
        """
        return {
            Filters.CATEGORIES: "📂  ",
            Filters.SEASONS: "🌦  ",
            Filters.BRANDS: "™️  ",
            Filters.SIZES: "📏  ",
        }[self]

