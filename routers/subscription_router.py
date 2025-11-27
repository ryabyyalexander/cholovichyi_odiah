import json
from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.types import CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext

from data_base.models import data_base
from keyboards.kb import NavigationCallback
from enums import RegisteredMainMenu
from utils.message_manager import MessageManager
from fsm.states import StateSubscription
from enums.sizes_enums import JacketSizes, JerseySizes, JeansSizes

router = Router(name="subscription_router")


async def get_subscription_menu(user_id: int, state: FSMContext) -> InlineKeyboardBuilder:
    """Generates the subscription management keyboard."""
    all_topics = data_base.get_subscription_topics()
    user_subscriptions = data_base.get_user_subscriptions(user_id)

    builder = InlineKeyboardBuilder()
    for topic in all_topics:
        is_subscribed = any(sub['subscription_id'] == topic['id'] for sub in user_subscriptions)
        status_emoji = "✅" if is_subscribed else "☑️"
        builder.button(
            text=f"{status_emoji} {topic['description']}",
            callback_data=f"toggle_subscription:{topic['id']}"
        )
    
    builder.button(
        text="← Назад до профілю",
        callback_data=NavigationCallback(action="main", current_level=RegisteredMainMenu.PROFILE, breadcrumbs="").pack()
    )
    builder.adjust(1)
    return builder


@router.callback_query(F.data == "manage_subscriptions")
async def handle_manage_subscriptions(callback: CallbackQuery, manager: MessageManager, state: FSMContext):
    """Displays the subscription management menu."""
    await callback.answer()
    await state.clear()
    
    user_id = callback.from_user.id
    builder = await get_subscription_menu(user_id, state)
    text = "<b>🔔 Керування підписками</b>\n\nОберіть теми, на які хочете підписатися:"
    await manager.edit(text, reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("toggle_subscription:"))
async def toggle_subscription(callback: CallbackQuery, manager: MessageManager, state: FSMContext):
    """Toggles a user's subscription to a topic or starts the configuration flow."""
    await callback.answer()
    try:
        subscription_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("Помилка!", show_alert=True)
        return

    user_id = callback.from_user.id
    topic = next((t for t in data_base.get_subscription_topics() if t['id'] == subscription_id), None)
    if not topic:
        await callback.answer("Тема не знайдена!", show_alert=True)
        return

    user_subscriptions = data_base.get_user_subscriptions(user_id)
    is_subscribed = any(sub['subscription_id'] == subscription_id for sub in user_subscriptions)

    if is_subscribed:
        data_base.unsubscribe_user(user_id, subscription_id)
        await callback.answer("Ви відписалися.")
        await handle_manage_subscriptions(callback, manager, state)
    else:
        if topic['topic_key'] == 'size_discounts':
            await start_size_subscription_flow(callback, manager, state, subscription_id)
        elif topic['topic_key'] == 'brand_news':
            await start_brand_subscription_flow(callback, manager, state, subscription_id)
        else:
            data_base.subscribe_user(user_id, subscription_id)
            await callback.answer("Ви підписалися.")
            await handle_manage_subscriptions(callback, manager, state)

async def start_size_subscription_flow(callback: CallbackQuery, manager: MessageManager, state: FSMContext, subscription_id: int):
    """Starts the flow for subscribing to discounts on user's sizes."""
    await state.update_data(subscription_id=subscription_id, selected_sizes={})
    user_id = callback.from_user.id
    user_sizes_json = data_base.sql_get_user(user_id, 'size')[0]

    if user_sizes_json and user_sizes_json != '{}':
        try:
            user_sizes = json.loads(user_sizes_json)

            size_type_labels = {'jacket': 'Куртка', 'jersey': 'Трикотаж', 'jeans': 'Джинси'}
            sizes_list = [f"{size_type_labels.get(k, k)}: {v}" for k, v in user_sizes.items() if v]

            if sizes_list:
                sizes_str = "\n".join(sizes_list)
                text = f"Ваші збережені розміри:\n<b>{sizes_str}</b>\n\nХочете використовувати їх для підписки на знижки?"
                builder = InlineKeyboardBuilder()
                builder.button(text="✅ Так, використати ці", callback_data="sub_use_profile_sizes")
                builder.button(text="✏️ Обрати інші розміри", callback_data="sub_choose_new_sizes")
                builder.button(text="Скасувати", callback_data="manage_subscriptions")
                builder.adjust(1)
                await manager.edit(text, reply_markup=builder.as_markup())
                return
        except (json.JSONDecodeError, AttributeError):
            pass

    await state.set_state(StateSubscription.choosing_size_type)
    await show_size_type_selection(callback, manager, state)

@router.callback_query(F.data == "sub_use_profile_sizes")
async def sub_use_profile_sizes(callback: CallbackQuery, manager: MessageManager, state: FSMContext):
    """Subscribes user with their existing profile sizes."""
    user_id = callback.from_user.id
    data = await state.get_data()
    subscription_id = data['subscription_id']
    user_sizes_json = data_base.sql_get_user(user_id, 'size')[0]
    user_sizes = json.loads(user_sizes_json)

    data_base.subscribe_user(user_id, subscription_id, filters=user_sizes)
    await callback.answer("Ви підписалися на знижки для ваших розмірів!", show_alert=True)
    await handle_manage_subscriptions(callback, manager, state)

@router.callback_query(F.data == "sub_choose_new_sizes")
async def sub_choose_new_sizes(callback: CallbackQuery, manager: MessageManager, state: FSMContext):
    await callback.answer()
    await state.set_state(StateSubscription.choosing_size_type)
    await show_size_type_selection(callback, manager, state)

async def show_size_type_selection(callback: CallbackQuery, manager: MessageManager, state: FSMContext):
    data = await state.get_data()
    selected_sizes = data.get('selected_sizes', {})
    
    text = "Оберіть тип розміру для підписки. Обрані розміри:\n"
    text += f"<code>Куртка: {selected_sizes.get('jacket', '-')}</code>\n"
    text += f"<code>Трикотаж: {selected_sizes.get('jersey', '-')}</code>\n"
    text += f"<code>Джинси: {selected_sizes.get('jeans', '-')}</code>"

    builder = InlineKeyboardBuilder()
    builder.button(text="🧥 Куртка", callback_data="sub_select_size:jacket")
    builder.button(text="👕 Трикотаж", callback_data="sub_select_size:jersey")
    builder.button(text="👖 Джинси", callback_data="sub_select_size:jeans")
    if any(selected_sizes.values()):
        builder.button(text="✅ Готово", callback_data="sub_confirm_sizes")
    builder.button(text="Скасувати", callback_data="manage_subscriptions")
    builder.adjust(3, 1, 1)
    await manager.edit(text, reply_markup=builder.as_markup())

async def get_size_keyboard(size_enum, callback_prefix: str, current_size: str = None) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    for value, label in size_enum.choices():
        text = f"{('✅ ' if value == current_size else '')}{label}"
        builder.button(text=text, callback_data=f"{callback_prefix}:{value}")
    builder.adjust(4)
    builder.row(InlineKeyboardButton(text="← Назад", callback_data="sub_choose_new_sizes"))
    return builder

@router.callback_query(F.data.startswith("sub_select_size:"), StateFilter(StateSubscription.choosing_size_type))
async def select_size_type_for_subscription(callback: CallbackQuery, manager: MessageManager, state: FSMContext):
    await callback.answer()
    size_type = callback.data.split(":")[1]
    await state.update_data(size_type=size_type)
    
    data = await state.get_data()
    selected_sizes = data.get('selected_sizes', {})
    
    if size_type == 'jacket':
        current_size = selected_sizes.get('jacket')
        await manager.edit("Оберіть розмір куртки:", reply_markup=(await get_size_keyboard(JacketSizes, "sub_set_size", current_size)).as_markup())
        await state.set_state(StateSubscription.choosing_jacket_size)
    elif size_type == 'jersey':
        current_size = selected_sizes.get('jersey')
        await manager.edit("Оберіть розмір трикотажу:", reply_markup=(await get_size_keyboard(JerseySizes, "sub_set_size", current_size)).as_markup())
        await state.set_state(StateSubscription.choosing_jersey_size)
    elif size_type == 'jeans':
        current_size = selected_sizes.get('jeans')
        await manager.edit("Оберіть розмір джинсів:", reply_markup=(await get_size_keyboard(JeansSizes, "sub_set_size", current_size)).as_markup())
        await state.set_state(StateSubscription.choosing_jeans_size)

@router.callback_query(F.data.startswith("sub_set_size:"), StateFilter(
    StateSubscription.choosing_jacket_size,
    StateSubscription.choosing_jersey_size,
    StateSubscription.choosing_jeans_size
))
async def set_size_for_subscription(callback: CallbackQuery, manager: MessageManager, state: FSMContext):
    await callback.answer()
    size_value = callback.data.split(":")[1]
    data = await state.get_data()
    size_type = data.get("size_type")
    
    selected_sizes = data.get('selected_sizes', {})
    selected_sizes[size_type] = size_value
    await state.update_data(selected_sizes=selected_sizes)
    
    await state.set_state(StateSubscription.choosing_size_type)
    await show_size_type_selection(callback, manager, state)

@router.callback_query(F.data == "sub_confirm_sizes", StateFilter(StateSubscription.choosing_size_type))
async def sub_confirm_sizes(callback: CallbackQuery, manager: MessageManager, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    selected_sizes = data.get('selected_sizes', {})
    if not any(selected_sizes.values()):
        await callback.answer("Ви не обрали жодного розміру!", show_alert=True)
        return

    size_type_labels = {'jacket': 'Куртка', 'jersey': 'Трикотаж', 'jeans': 'Джинси'}
    sizes_list = [f"{size_type_labels.get(k, k)}: {v}" for k, v in selected_sizes.items() if v]
    sizes_str = "\n".join(sizes_list)
    text = f"Підписатися на знижки для розмірів:\n<b>{sizes_str}</b>?"
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Так, підписатися", callback_data="sub_execute_subscribe")
    builder.button(text="Скасувати", callback_data="manage_subscriptions")
    builder.adjust(1)
    await manager.edit(text, reply_markup=builder.as_markup())
    await state.set_state(StateSubscription.confirming_subscription_sizes)

@router.callback_query(F.data == "sub_execute_subscribe", StateFilter(StateSubscription.confirming_subscription_sizes))
async def sub_execute_subscribe(callback: CallbackQuery, manager: MessageManager, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    data = await state.get_data()
    
    subscription_id = data.get('subscription_id')
    if not subscription_id:
        await callback.answer("Сталася помилка, ID підписки не знайдено. Спробуйте знову.", show_alert=True)
        await handle_manage_subscriptions(callback, manager, state)
        return

    selected_sizes = data.get('selected_sizes', {})

    data_base.subscribe_user(user_id, subscription_id, filters=selected_sizes)
    await callback.answer("Ви успішно підписалися!", show_alert=True)

    # Ask to update profile
    text = "Хочете зберегти ці розміри у вашому основному профілі?"
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Так, зберегти", callback_data="sub_update_profile_sizes")
    builder.button(text="Ні, дякую", callback_data="manage_subscriptions")
    builder.adjust(1)
    await manager.edit(text, reply_markup=builder.as_markup())
    await state.set_state(StateSubscription.confirming_profile_update)

@router.callback_query(F.data == "sub_update_profile_sizes", StateFilter(StateSubscription.confirming_profile_update))
async def sub_update_profile_sizes(callback: CallbackQuery, manager: MessageManager, state: FSMContext):
    user_id = callback.from_user.id
    data = await state.get_data()
    selected_sizes = data.get('selected_sizes', {})

    user_sizes_json = data_base.sql_get_user(user_id, 'size')[0]
    user_sizes = json.loads(user_sizes_json) if user_sizes_json and user_sizes_json != '{}' else {}
    user_sizes.update(selected_sizes)
    
    data_base.execute_query("UPDATE users SET size = ? WHERE user_id = ?", (json.dumps(user_sizes), user_id))
    await callback.answer("Розміри в профілі оновлено!", show_alert=True)
    await handle_manage_subscriptions(callback, manager, state)


# --- Brand Subscription Flow ---

async def get_brand_subscription_keyboard(state: FSMContext) -> InlineKeyboardBuilder:
    """Creates the keyboard for brand selection."""
    all_brands = data_base.get_all_brands()
    data = await state.get_data()
    selected_brands = data.get('selected_brands', [])

    builder = InlineKeyboardBuilder()
    for brand in all_brands:
        is_selected = brand in selected_brands
        text = f"{('✅ ' if is_selected else '')}{brand}"
        builder.button(text=text, callback_data=f"sub_toggle_brand:{brand}")
    
    builder.adjust(2)
    if selected_brands:
        builder.row(InlineKeyboardButton(text="✅ Готово", callback_data="sub_confirm_brands"))
    builder.row(InlineKeyboardButton(text="Скасувати", callback_data="manage_subscriptions"))
    return builder

async def start_brand_subscription_flow(callback: CallbackQuery, manager: MessageManager, state: FSMContext, subscription_id: int):
    """Starts the flow for subscribing to brand news."""
    user_id = callback.from_user.id
    user_subscriptions = data_base.get_user_subscriptions(user_id)
    current_subscription = next((sub for sub in user_subscriptions if sub['subscription_id'] == subscription_id), None)
    
    initial_brands = []
    if current_subscription and current_subscription['filters']:
        try:
            initial_brands = json.loads(current_subscription['filters']).get('brands', [])
        except (json.JSONDecodeError, AttributeError):
            pass

    await state.update_data(subscription_id=subscription_id, selected_brands=initial_brands)
    await state.set_state(StateSubscription.choosing_brands)

    text = "Оберіть бренди, на новини яких хочете підписатися:"
    builder = await get_brand_subscription_keyboard(state)
    await manager.edit(text, reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("sub_toggle_brand:"), StateFilter(StateSubscription.choosing_brands))
async def handle_brand_selection(callback: CallbackQuery, manager: MessageManager, state: FSMContext):
    """Handles selection of a brand for subscription."""
    brand_name = callback.data.split(":")[1]
    data = await state.get_data()
    selected_brands = data.get('selected_brands', [])

    if brand_name in selected_brands:
        selected_brands.remove(brand_name)
    else:
        selected_brands.append(brand_name)
    
    await state.update_data(selected_brands=selected_brands)
    
    # Refresh the keyboard
    builder = await get_brand_subscription_keyboard(state)
    await manager.edit_reply_markup(reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data == "sub_confirm_brands", StateFilter(StateSubscription.choosing_brands))
async def handle_confirm_brand_subscription(callback: CallbackQuery, manager: MessageManager, state: FSMContext):
    """Saves the brand subscription."""
    user_id = callback.from_user.id
    data = await state.get_data()
    subscription_id = data['subscription_id']
    selected_brands = data.get('selected_brands', [])

    if not selected_brands:
        await callback.answer("Ви не обрали жодного бренду!", show_alert=True)
        return

    filters = {'brands': selected_brands}
    data_base.subscribe_user(user_id, subscription_id, filters=filters)
    await callback.answer("Підписку на новини брендів збережено!", show_alert=True)
    await handle_manage_subscriptions(callback, manager, state)
