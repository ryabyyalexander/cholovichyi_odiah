"""
Централизованная система навигации для слайдеров
Управляет возвратом слайдеров к исходным страницам
"""

from typing import Dict, Optional, Tuple
from aiogram.types import InlineKeyboardButton
from keyboards.kb import NavigationCallback
from utils import logger
from utils.lexicon import btn


class SliderNavigation:
    """Централизованное управление навигацией слайдеров"""
    
    # Маппинг типов слайдеров к их возможным источникам
    SLIDER_SOURCES = {
        "main": ["main"],           # Каталог - только с главной
        "filters": ["filters"],     # Фильтр - только с фильтров
        "sizes": ["main"],          # Мои размеры - только с главной
        "favorites": ["main", "filters", "profile"],  # Избранное - со всех страниц
        "cart": ["main", "filters", "profile"]        # Корзина - со всех страниц
    }
    
    # Маппинг источников к их обработчикам возврата
    RETURN_HANDLERS = {
        "main": {
            "handler": "process_main_menu",
            "module": "routers.navigation_router",
            "callback_data": NavigationCallback(action="main", current_level="main", breadcrumbs="")
        },
        "filters": {
            "handler": "process_filters_menu", 
            "module": "routers.navigation_router",
            "callback_data": NavigationCallback(action="filters", current_level="filters", breadcrumbs="")
        },
        "profile": {
            "handler": "handle_profile_menu",
            "module": "routers.profile_router", 
            "callback_data": NavigationCallback(action="profile", current_level="profile", breadcrumbs="")
        }
    }
    
    @classmethod
    def get_slider_source_info(cls, source: str) -> Dict:
        """Получает информацию о типе слайдера"""
        return {
            "name": cls._get_slider_name(source),
            "valid_sources": cls.SLIDER_SOURCES.get(source, []),
            "description": cls._get_slider_description(source)
        }
    
    @classmethod
    def _get_slider_name(cls, source: str) -> str:
        """Возвращает название слайдера"""
        names = {
            "main": "Каталог",
            "filters": "Фильтр", 
            "sizes": "Мої розміри",
            "favorites": "Обране",
            "cart": "Кошик"
        }
        return names.get(source, "Неизвестный слайдер")
    
    @classmethod
    def _get_slider_description(cls, source: str) -> str:
        """Возвращает описание слайдера"""
        descriptions = {
            "main": "Основной каталог всех товаров",
            "filters": "Товары, отфильтрованные по критериям",
            "sizes": "Товары, подходящие по вашим размерам", 
            "favorites": "Ваши избранные товары",
            "cart": "Товары в вашей корзине"
        }
        return descriptions.get(source, "")
    
    @classmethod
    def validate_source_combination(cls, slider_source: str, return_source: str) -> bool:
        """Проверяет, может ли слайдер быть запущен с указанного источника"""
        valid_sources = cls.SLIDER_SOURCES.get(slider_source, [])
        return return_source in valid_sources
    
    @classmethod
    def get_return_callback_data(cls, return_source: str) -> str:
        """Получает callback_data для возврата к указанному источнику"""
        handler_info = cls.RETURN_HANDLERS.get(return_source)
        if handler_info:
            return handler_info["callback_data"].pack()
        # Fallback к главному меню
        return NavigationCallback(action="main", current_level="main", breadcrumbs="").pack()
    
    @classmethod
    def get_return_handler_info(cls, return_source: str) -> Optional[Dict]:
        """Получает информацию о обработчике возврата"""
        return cls.RETURN_HANDLERS.get(return_source)
    
    @classmethod
    def create_slider_keyboard_close_button(cls, slider_source: str, return_source: str) -> InlineKeyboardButton:
        """Создает кнопку закрытия слайдера с правильным возвратом"""
        if not cls.validate_source_combination(slider_source, return_source):
            logger.warning(f"Invalid source combination: slider_source={slider_source}, return_source={return_source}")
            # Fallback к главному меню
            return_source = "main"
        
        callback_data = cls.get_return_callback_data(return_source)
        return InlineKeyboardButton(text=btn['x'], callback_data=callback_data)
    
    @classmethod
    async def save_navigation_context(cls, state, slider_source: str, return_source: str) -> None:
        """Сохраняет контекст навигации в FSM"""
        if not cls.validate_source_combination(slider_source, return_source):
            logger.warning(f"Invalid source combination: slider_source={slider_source}, return_source={return_source}")
            return_source = "main"
        
        navigation_data = {
            "slider_source": slider_source,
            "return_source": return_source,
            "slider_name": cls._get_slider_name(slider_source),
            "return_handler_info": cls.get_return_handler_info(return_source)
        }
        
        # Сохраняем в FSM
        await state.update_data(**navigation_data)
        logger.debug(f"Saved navigation context: {navigation_data}")
    
    @classmethod
    async def get_navigation_context(cls, state) -> Dict:
        """Получает контекст навигации из FSM"""
        data = await state.get_data()
        return {
            "slider_source": data.get("slider_source", "main"),
            "return_source": data.get("return_source", "main"),
            "slider_name": data.get("slider_name", "Каталог"),
            "return_handler_info": data.get("return_handler_info")
        }
    
    @classmethod
    async def execute_return(cls, callback, state, manager) -> bool:
        """Выполняет возврат к исходной странице"""
        try:
            context = await cls.get_navigation_context(state)
            return_source = context["return_source"]
            handler_info = context["return_handler_info"]
            
            if not handler_info:
                logger.error("No return handler info found")
                return False
            
            # Импортируем нужный модуль
            module_name = handler_info["module"]
            handler_name = handler_info["handler"]
            
            # Динамический импорт
            if module_name == "routers.navigation_router":
                from routers.navigation_router import process_main_menu, process_filters_menu
                if handler_name == "process_main_menu":
                    await process_main_menu(callback, handler_info["callback_data"], state, manager)
                elif handler_name == "process_filters_menu":
                    await process_filters_menu(callback, state, manager)
            elif module_name == "routers.profile_router":
                from routers.profile_router import handle_profile_menu
                await handle_profile_menu(callback, state, manager)
            else:
                logger.error(f"Unknown module: {module_name}")
                return False
            
            # Очищаем контекст навигации
            await state.update_data(
                slider_source=None,
                return_source=None,
                slider_name=None,
                return_handler_info=None
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error executing return: {e}")
            return False
    
    @classmethod
    def get_all_valid_combinations(cls) -> Dict[str, list]:
        """Возвращает все валидные комбинации слайдер-источник"""
        return cls.SLIDER_SOURCES.copy()
    
    @classmethod
    def get_slider_summary(cls) -> str:
        """Возвращает сводку по всем слайдерам"""
        summary = "📋 Сводка по слайдерам:\n\n"
        
        for source, valid_sources in cls.SLIDER_SOURCES.items():
            name = cls._get_slider_name(source)
            description = cls._get_slider_description(source)
            sources_str = ", ".join(valid_sources)
            
            summary += f"🎯 **{name}** (`{source}`)\n"
            summary += f"   {description}\n"
            summary += f"   📍 Источники: {sources_str}\n\n"
        
        return summary 