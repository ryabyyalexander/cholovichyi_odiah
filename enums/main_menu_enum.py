# enums/main_menu_enum.py
from enum import Enum

class MainMenu(str, Enum):
    # First row buttons
    CATALOG = "catalog"
    FILTERS = "filters"
    # Second row button
    PHONE = "phone"

    @property
    def label(self):
        return {
            MainMenu.CATALOG: "Каталог",
            MainMenu.FILTERS: "Фільтри",
            MainMenu.PHONE: "Надіслати"
        }[self]

    @property
    def emoji(self) -> str:
        return {
            MainMenu.CATALOG: "✅ ",
            MainMenu.FILTERS: "🔍 ",
            MainMenu.PHONE: "📞 "
        }[self]

class RegisteredMainMenu(str, Enum):
    CATALOG = "catalog"
    FILTERS = "filters"
    PROFILE = "profile"
    MY_SIZE = "my_size"

    @property
    def label(self):
        return {
            RegisteredMainMenu.CATALOG: "",
            RegisteredMainMenu.FILTERS: "Фільтри",
            RegisteredMainMenu.PROFILE: "Профіль",
            RegisteredMainMenu.MY_SIZE: "Для мене"
        }[self]

    @property
    def emoji(self) -> str:
        return {
            RegisteredMainMenu.CATALOG: "▶️ ",
            RegisteredMainMenu.FILTERS: "🔍 ",
            RegisteredMainMenu.PROFILE: "👤 ",
            RegisteredMainMenu.MY_SIZE: "✓  "
        }[self]