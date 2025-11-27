# enums/categories.py
from enum import Enum


class CreateProduct(str, Enum):
    """
    Универсальный Enum для работы с categories, с удобными методами.
    Подходит для генерации кнопок, валидации данных и отображения текста.
    """

    ONE = "one"
    MORE = "more"

    @property
    def label(self):
        return {
            CreateProduct.ONE: "всі фото ➜ 1 новий товар",
            CreateProduct.MORE: "кожне фото ➜ 1 новий товар",
        }[self]

    @property
    def emoji(self) -> str:
        """
        Возвращает эмодзи, подходящий для сезона (по желанию).
        """
        return {
            CreateProduct.ONE: "",
            CreateProduct.MORE: ""
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
