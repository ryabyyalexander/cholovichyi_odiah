# --- FSM-состояния меню---
from aiogram.fsm.state import StatesGroup, State


class Registration(StatesGroup):
    start = State()


class State_add_photo(StatesGroup):
    start = State()
    close = State()


class StateEditProduct(StatesGroup):
    editing = State()
    editing_name = State()
    editing_description = State()
    editing_price = State()
    editing_purchase_price = State()
    editing_discount = State()
    editing_quontity = State()
    editing_loyalty_tiers = State()


class StateEditMedia(StatesGroup):
    viewing = State()      # Просмотр сетки фото
    adding_photos = State() # Загрузка новых фото
    confirming_delete = State() # Подтверждение удаления
    editing_caption = State() # Редактирование caption


class SlideShowState(StatesGroup):
    viewing = State()


class DetailViewState(StatesGroup):
    viewing = State()  # Детальный просмотр товара


class StateMailing(StatesGroup):
    waiting_for_message = State()
    waiting_for_recipient_group = State()
    waiting_for_confirmation = State()
    waiting_for_brand_for_subscription_mailing = State()


class StateSubscription(StatesGroup):
    choosing_size_type = State()
    choosing_jacket_size = State()
    choosing_jersey_size = State()
    choosing_jeans_size = State()
    confirming_subscription_sizes = State()
    confirming_profile_update = State()
    choosing_brands = State()