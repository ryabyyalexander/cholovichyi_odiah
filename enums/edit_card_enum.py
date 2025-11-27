# enums/categories.py
from enum import Enum


class EditCard(str, Enum):
    """
    Универсальный Enum для работы с categories, с удобными методами.
    Подходит для генерации кнопок, валидации данных и отображения текста.
    """

    CATEGORY = "edit_category"
    SEASON = "edit_season"
    NAME = "edit_name"
    BRAND = "edit_brand"
    COUNTRY = "edit_country"
    DESC = "edit_desc"
    PRICE = "edit_price"
    DISCOUNT = "edit_discount"
    SIZES = "edit_sizes"
    PHOTOS = "edit_photos"

    @property
    def label(self):
        return {
            EditCard.CATEGORY: "Категорія",
            EditCard.SEASON: "Сезон",
            EditCard.NAME: "Назва",
            EditCard.BRAND: "Бренд",
            EditCard.COUNTRY: "Країна",
            EditCard.DESC: "Опис",
            EditCard.PRICE: "Ціна",
            EditCard.DISCOUNT: "Знижка",
            EditCard.SIZES: "Розміри",
            EditCard.PHOTOS: "Фото",
        }[self]

    @property
    def emoji(self) -> str:
        """
        Возвращает эмодзи, подходящий для сезона (по желанию).
        """
        return {
            EditCard.CATEGORY: "📂",
            EditCard.SEASON: "🌦",
            EditCard.NAME: "✏️",
            EditCard.BRAND: "™️",
            EditCard.COUNTRY: "🌍",
            EditCard.DESC: "📝",
            EditCard.PRICE: "💰",
            EditCard.DISCOUNT: "🔥",
            EditCard.SIZES: "📏",
            EditCard.PHOTOS: "🖼",
        }[self]

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        """
        Возвращает список кортежей (value, label), например:
        [('spring_summer', 'Весна - Літо'), ('autumn_winter', 'Осінь - Зима')]
        Полезно для select-полей в админке.
        """
        return [(item.value, item.label) for item in cls]

    @classmethod
    def from_value(cls, value: str) -> "Edit card | None":
        """
        Безопасно преобразует строку в Seasons или возвращает None.
        Удобно при разборе данных из callback_data.
        """
        try:
            return cls(value)
        except ValueError:
            return None
