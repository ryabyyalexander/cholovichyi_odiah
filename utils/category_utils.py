from enums.categories_enum import JacketsCategory, JeansCategory, JerseyCategory, Categories


def get_subcategory_label(category: str, subcategory_value: str) -> str:
    """
    Получает отображаемое название подкатегории по значению из БД.
    
    Args:
        category: Категория товара (куртки, джинси, трикотаж)
        subcategory_value: Значение подкатегории из БД
    
    Returns:
        Отображаемое название подкатегории
    """
    try:
        if category == "куртки":
            return JacketsCategory(subcategory_value).label.strip()
        elif category == "джинси":
            return JeansCategory(subcategory_value).label.strip()
        elif category == "трикотаж":
            return JerseyCategory(subcategory_value).label.strip()
        else:
            return subcategory_value
    except Exception:
        return subcategory_value


def get_category_label(category_value: str) -> str:
    """
    Получает отображаемое название категории.
    
    Args:
        category_value: Значение категории из БД
    
    Returns:
        Отображаемое название категории
    """
    try:
        return Categories(category_value).label
    except Exception:
        return category_value


def get_subcategory_choices(category: str) -> list[tuple[str, str]]:
    """
    Получает список подкатегорий для категории.
    
    Args:
        category: Категория товара
    
    Returns:
        Список кортежей (label, value) для подкатегорий
    """
    if category == "куртки":
        return [(item.label.strip(), item.value) for item in JacketsCategory]
    elif category == "джинси":
        return [(item.label.strip(), item.value) for item in JeansCategory]
    elif category == "трикотаж":
        return [(item.label.strip(), item.value) for item in JerseyCategory]
    else:
        return []


def get_subcategory_value_by_label(category: str, subcategory_label: str) -> str:
    """
    Получает value подкатегории по label для поиска в БД.
    
    Args:
        category: Категория товара (куртки, джинси, трикотаж)
        subcategory_label: Отображаемое название подкатегории
    
    Returns:
        Value подкатегории для поиска в БД
    """
    try:
        if category == "куртки":
            for item in JacketsCategory:
                if item.label.strip() == subcategory_label:
                    return item.value
        elif category == "джинси":
            for item in JeansCategory:
                if item.label.strip() == subcategory_label:
                    return item.value
        elif category == "трикотаж":
            for item in JerseyCategory:
                if item.label.strip() == subcategory_label:
                    return item.value
        return subcategory_label
    except Exception:
        return subcategory_label 