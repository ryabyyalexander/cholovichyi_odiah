# enums/categories.py
from enums.base_enum import BaseCategoryEnum


class Categories(BaseCategoryEnum):
    """
    Универсальный Enum для работы с categories, с удобными методами.
    Подходит для генерации кнопок, валидации данных и отображения текста.
    """

    JACKETS = "куртки"
    JEANS = "джинси"
    JERSEY = "трикотаж"

    @property
    def label(self):
        return {
            Categories.JACKETS: "Куртки",
            Categories.JEANS: "Джинси",
            Categories.JERSEY: "Трикотаж"
        }[self]

    @property
    def emoji(self) -> str:
        """
        Возвращает эмодзи, подходящий для сезона (по желанию).
        """
        return {
            Categories.JACKETS: "🧥  ",
            Categories.JEANS: "👖  ",
            Categories.JERSEY: "👕  "
        }[self]


class JacketsCategory(BaseCategoryEnum):
    """
    Enum для категорий верхней одежды.
    """
    PARKA = "довгі"
    BOMBER = "короткі"
    VESTS = "жилетки"
    JACKETS = "середньої довжини"

    @property
    def label(self) -> str:
        return {
            JacketsCategory.JACKETS: "середньої довжини",
            JacketsCategory.BOMBER: "короткі",
            JacketsCategory.PARKA: "довгі",
            JacketsCategory.VESTS: "жилетки"
        }[self]

    @property
    def emoji(self) -> str:
        return {
            JacketsCategory.JACKETS: "",
            JacketsCategory.VESTS: "",
            JacketsCategory.PARKA: "",
            JacketsCategory.BOMBER: ""
        }[self]


class JeansCategory(BaseCategoryEnum):
    """
    Enum для категорий джинсов и брюк.
    """
    JEANS = "класичні"
    TROUSERS = "брючні"
    SHORTS = "шорти"
    BELTS = "ремені"

    @property
    def label(self) -> str:
        return {
            JeansCategory.JEANS: "класичні",
            JeansCategory.TROUSERS: "брючні",
            JeansCategory.SHORTS: "шорти",
            JeansCategory.BELTS: "ремені"
        }[self]

    @property
    def emoji(self) -> str:
        return {
            JeansCategory.JEANS: "",
            JeansCategory.TROUSERS: "",
            JeansCategory.SHORTS: "",
            JeansCategory.BELTS: ""
        }[self]


class JerseyCategory(BaseCategoryEnum):
    """
    Enum для категорий трикотажа и других вещей.
    """
    SWEATERS = "светри"
    SWEATSHIRTS = "кофти"
    BLASER = "піджак"
    SHIRTS = "батники"
    TRACKSUITS = "спорт костюми"
    TROUSERS = "штани"
    POLOS = "поло"
    T_SHIRTS = "футболки"
    DRESS_SHIRTS = "рубашки"
    HATS = "головні убори"

    @property
    def label(self) -> str:
        return {
            JerseyCategory.SWEATERS: "светри",
            JerseyCategory.SWEATSHIRTS: "кофти",
            JerseyCategory.TRACKSUITS: "спорт костюми",
            JerseyCategory.TROUSERS: "штани",
            JerseyCategory.SHIRTS: "батники",
            JerseyCategory.DRESS_SHIRTS: "рубашки",
            JerseyCategory.POLOS: "поло",
            JerseyCategory.T_SHIRTS: "футболки",
            JerseyCategory.HATS: "головні убори",
            JerseyCategory.BLASER: "піджак"
        }[self]

    @property
    def emoji(self) -> str:
        return {
            JerseyCategory.SWEATERS: "",
            JerseyCategory.SWEATSHIRTS: "",
            JerseyCategory.TRACKSUITS: "",
            JerseyCategory.TROUSERS: "",
            JerseyCategory.SHIRTS: "",
            JerseyCategory.DRESS_SHIRTS: "",
            JerseyCategory.POLOS: "",
            JerseyCategory.T_SHIRTS: "",
            JerseyCategory.HATS: "",
            JerseyCategory.BLASER: ""
        }[self]


