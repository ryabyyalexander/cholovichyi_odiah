from enum import Enum

class BaseCategoryEnum(str, Enum):
    """Базовый Enum с общими методами."""

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        """Возвращает список кортежей (value, label)."""
        return [(item.value, item.label) for item in cls]

    @classmethod
    def from_value(cls, value: str) -> "BaseCategoryEnum | None":
        """Безопасно преобразует строку в Enum или возвращает None."""
        try:
            return cls(value)
        except ValueError:
            return None
