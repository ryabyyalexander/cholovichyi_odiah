from enums import Seasons, Weather, Categories, Filters
from enums.categories_enum import JacketsCategory, JeansCategory, JerseyCategory
from utils.category_utils import get_subcategory_label, get_category_label


# Утилиты для кодирования/декодирования хлебных крошек
def encode_breadcrumbs(breadcrumbs: str) -> str:
    return breadcrumbs.replace(":", "%3A")


def decode_breadcrumbs(breadcrumbs: str) -> str:
    return breadcrumbs.replace("%3A", ":")


# Преобразование хлебных крошек в читаемый вид
def format_breadcrumbs(breadcrumbs: str) -> str:
    if not breadcrumbs:
        return "🔍 Фільтри"
    names = []
    for part in breadcrumbs.split(":"):
        # Проверяем основные категории
        for enum_group in (Filters, Seasons, Weather, Categories):
            try:
                item = enum_group(part)
                names.append(f"{item.emoji} {item.label}")
                break
            except ValueError:
                continue
        else:
            # Если не нашли в основных категориях, проверяем подкатегории
            # Пытаемся определить категорию из контекста breadcrumbs
            category = None
            for cat_part in breadcrumbs.split(":"):
                try:
                    Categories(cat_part)
                    category = cat_part
                    break
                except ValueError:
                    continue
            
            if category:
                try:
                    label = get_subcategory_label(category, part)
                    # Находим соответствующий enum для эмодзи
                    if category == "куртки":
                        emoji = JacketsCategory(part).emoji
                    elif category == "джинси":
                        emoji = JeansCategory(part).emoji
                    elif category == "трикотаж":
                        emoji = JerseyCategory(part).emoji
                    else:
                        emoji = "📂"
                    names.append(f"{emoji} {label}")
                except Exception:
                    names.append(part)
            else:
                names.append(part)
    return " : ".join(names)


# Получение предыдущего уровня (для кнопки "Назад")
def get_previous_level(crumbs: list[str]) -> str:
    if not crumbs:
        return ""
    if len(crumbs) == 1:
        return ""
    return crumbs[-2] if len(crumbs) >= 2 else ""