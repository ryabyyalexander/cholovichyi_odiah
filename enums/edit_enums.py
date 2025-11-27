# enums/edit_enums.py
from enum import Enum


class Edit(str, Enum):
    CATEGORY = "edit_category"
    SEASON = "edit_season"
    NAME = "edit_name"
    BRAND = "edit_brand"
    DESC = "edit_desc"
    PRICE = "edit_price"
    DISCOUNT = "edit_discount"
    SIZES = "edit_sizes"
    PHOTOS = "edit_photos"

    @property
    def label(self) -> str:
        return {
            Edit.CATEGORY: "Категорія",
            Edit.SEASON: "Сезон",
            Edit.NAME: "Назва",
            Edit.BRAND: "Бренд",
            Edit.DESC: "Опис",
            Edit.PRICE: "Ціна",
            Edit.DISCOUNT: "Знижка",
            Edit.SIZES: "Розміри",
            Edit.PHOTOS: "Фото",
        }[self]

    @property
    def emoji(self) -> str:
        return {
            Edit.CATEGORY: "📂 ",
            Edit.SEASON: "🌦 ",
            Edit.NAME: "✏️ ",
            Edit.BRAND: "™️ ",
            Edit.DESC: "📝 ",
            Edit.PRICE: "💰 ",
            Edit.DISCOUNT: "🔥 ",
            Edit.SIZES: "📏 ",
            Edit.PHOTOS: "🖼 ",
        }[self]

