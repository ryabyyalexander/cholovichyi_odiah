# enums/seasons_action.py
from enums.base_enum import BaseCategoryEnum


class Seasons(BaseCategoryEnum):
    """
    Универсальный Enum для работы с сезонами, с удобными методами.
    Подходит для генерации кнопок, валидации данных и отображения текста.
    """

    NEW = "надходження"
    AUTUMN_WINTER = "осінь-зима"
    SPRING_SUMMER = "весна-літо"

    @property
    def label(self) -> str:
        """
        Возвращает текстовое название сезона для пользователя.
        """
        return {
            Seasons.SPRING_SUMMER: "Весна - Літо",
            Seasons.AUTUMN_WINTER: "Осінь - Зима",
            Seasons.NEW: "Надходження"
        }[self]

    @property
    def emoji(self) -> str:
        """
        Возвращает эмодзи, подходящий для сезона (по желанию).
        """
        return {
            Seasons.SPRING_SUMMER: "☀️  ",
            Seasons.AUTUMN_WINTER: "❄️  ",
            Seasons.NEW: "✈️  "
        }[self]

    @property
    def color(self) -> str:
        """
        Возвращает условный цвет (для будущего использования в UI).
        """
        return {
            Seasons.SPRING_SUMMER: "green",
            Seasons.AUTUMN_WINTER: "blue"
        }[self]
