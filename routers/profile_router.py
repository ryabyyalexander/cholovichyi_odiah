from aiogram import Router, F
from filters.is_admin import IsAdmin
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
import json
from data_base.constants import USER_FIELDS
from data_base.models import data_base
from keyboards.kb import NavigationCallback
from enums import RegisteredMainMenu, Profile
from utils import logger, admins, viewers
from utils.message_manager import MessageManager
from services.loyalty_service import LoyaltyService
from utils.lexicon import LOYALTY_LEXICON, HELP_TEXT, btn
from aiogram.utils.keyboard import InlineKeyboardBuilder
from enums.sizes_enums import JacketSizes, JerseySizes, JeansSizes
from utils.view_tracker import view_tracker
from utils.slider_manager import SliderManager
from utils.functions import get_cart_block_profile

router = Router()
@router.callback_query(
    NavigationCallback.filter(F.action == "main"),
    NavigationCallback.filter(F.current_level == RegisteredMainMenu.PROFILE),
)
async def handle_profile(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    await callback.answer()
    data = await state.get_data()
    if "animation_task" in data and not data["animation_task"].done():
        data["animation_task"].cancel()
        logger.debug("Анимация остановлена")

    user_id = callback.from_user.id
    user = data_base.sql_get_user(user_id)
    is_active = user[USER_FIELDS['is_active']]
    phone = user[USER_FIELDS['phone']]
    first_name = user[USER_FIELDS['first_name']] or ''
    last_name = user[USER_FIELDS['last_name']] or ''
    name = first_name + (' ' + last_name if last_name else '')
    
    # Получаем скорость слайдера из базы данных
    slider_speed = data_base.get_slider_speed(user_id)
    if slider_speed is None:
        slider_speed = 2  # Значение по умолчанию

    # --- Лояльность ---
    loyalty = LoyaltyService(data_base)
    points = loyalty.get_purchase_points(user_id)
    activity = int(user[USER_FIELDS['restart_count']])
    total_views = data_base.get_user_total_views(user_id)  # Общее количество просмотров
    referral_points = loyalty.get_referral_points(user_id)
    progress_points = points + (activity / 10) + referral_points
    level = loyalty.get_user_level(user_id)

    # Карта иконок для уровней
    level_emojis = {
        'bronze': '🥉',
        'silver': '🥈',
        'gold': '🥇',
        'diamond': '💎',
    }
    level_icon = level_emojis.get(level.lower(), '')
    
    # Проверяем, не пора ли повысить уровень (по сумме баллов и активности)
    level_up_notification = loyalty.update_user_level(user_id, progress_points=progress_points)
    if level_up_notification:
        # Если произошло повышение уровня, обновляем данные
        points = loyalty.get_purchase_points(user_id)
        activity = int(user[USER_FIELDS['restart_count']])
        progress_points = points + (activity / 10)
        level = loyalty.get_user_level(user_id)
        level_icon = level_emojis.get(level.lower(), '')
        await manager.send(level_up_notification)

    # Получаем прогресс до следующего уровня (по сумме баллов, активности и реферальных баллов)
    points_needed, next_level = loyalty.get_next_level_progress(user_id, progress_points=progress_points)
    next_level_icon = level_emojis.get(next_level.lower(), '')
    progress_text = (
        f"До рівня {next_level_icon} {next_level}: {points_needed} балів"
        if points_needed > 0
        else "Максимальний рівень"
    )

    # --- Флаги для отображения кнопок профиля ---
    # Показываем кнопку корзины только если в корзине есть товары
    cart_items = data_base.get_cart(user_id)
    show_cart = False # bool(cart_items)
    show_favorites = False  # Включаем кнопку избранного
    orders = data_base.get_user_orders(user_id)
    show_orders = bool(orders)
    show_settings = True

    # Собираем список разрешённых enum
    profile_buttons = []
    from enums.profile_enum import Profile
    if show_cart:
        profile_buttons.append(Profile.CART)
    if show_favorites:
        profile_buttons.append(Profile.FAVORITES)
    if show_orders:
        profile_buttons.append(Profile.ORDERS)
    if show_settings:
        profile_buttons.append(Profile.SETTINGS)

    # Клавиатура профиля только с нужными кнопками
    builder = InlineKeyboardBuilder()
    for item in profile_buttons:
        builder.button(
            text=f"{item.emoji} {item.label}",
            callback_data=NavigationCallback(
                action="main",
                current_level=item.value,
                breadcrumbs="profile" if item == Profile.CART else ""
            )
        )
    builder.adjust(1)
    profile_kb = builder.as_markup()

    # Кнопка выбора размеров профиля
    profile_kb.inline_keyboard.insert(0, [
        InlineKeyboardButton(text="🎯    Мої розміри", callback_data="profile_select_sizes")
    ])

    # Кнопка админ панели (только для админов)
    if user_id in viewers:
        profile_kb.inline_keyboard.insert(0, [
            InlineKeyboardButton(text="🅰️   Адмін панель", callback_data="admin_panel")
        ])

    # Кнопка статистики просмотров
    # profile_kb.inline_keyboard.append([
    #     InlineKeyboardButton(text="📊  Статистика переглядів", callback_data='profile_view_stats')
    # ])

    # Кнопка управления подписками
    profile_kb.inline_keyboard.append([
        InlineKeyboardButton(text="🔔  Керування підписками", callback_data="manage_subscriptions")
    ])

    # Кнопка архива сообщений (только если архив не пуст для данного пользователя)
    if data_base.get_archived_messages_for_user(user_id):
        profile_kb.inline_keyboard.append([
            InlineKeyboardButton(text="🌀  Архів повідомлень", callback_data="user_message_archive")
        ])

    # Кнопка реферальной ссылки
    profile_kb.inline_keyboard.append([
        InlineKeyboardButton(text="🔗  Реферальне посилання", callback_data='profile_referral_link')
    ])

    # Кнопка помощи
    if user_id in admins:
        profile_kb.inline_keyboard.append([
            InlineKeyboardButton(text="❓ Як користуватись ботом", callback_data="user_show_help")
        ])

    # Получаем все три размера из JSON size
    user_size_json = user[USER_FIELDS.get('size', -1)] if 'size' in USER_FIELDS else None
    jacket_size = jersey_size = jeans_size = None
    if user_size_json:
        try:
            size_obj = json.loads(user_size_json)
            jacket_size = size_obj.get('jacket')
            jersey_size = size_obj.get('jersey')
            jeans_size = size_obj.get('jeans')
        except Exception:
            pass
    # Получаем количество товаров для каждого размера
    jacket_count = data_base.get_filtered_product_count(size=jacket_size) if jacket_size else None
    jersey_count = data_base.get_filtered_product_count(size=jersey_size) if jersey_size else None
    jeans_count = data_base.get_filtered_product_count(size=jeans_size) if jeans_size else None
    jacket_count_str = f"  ({jacket_count} мод)" if jacket_size else ""
    jersey_count_str = f"  ({jersey_count} мод)" if jersey_size else ""
    jeans_count_str = f"  ({jeans_count} мод)" if jeans_size else ""
    jacket_size_line = f"<code>| Розмір куртки : <b>{jacket_size if jacket_size else 'не вказано'}</b>{jacket_count_str}</code>\n"
    jersey_size_line = f"<code>| Розмір трикотажу : <b>{jersey_size if jersey_size else 'не вказано'}</b>{jersey_count_str}</code>\n"
    jeans_size_line = f"<code>| Джинсовий розмір : <b>{jeans_size if jeans_size else 'не вказано'}</b>{jeans_count_str}</code>\n"

    # --- БЛОК КОРЗИНЫ ---
    cart_block = get_cart_block_profile(user_id)

    # Убираем блок персональной скидки, так как она теперь отображается в корзине
    discount_block = ""

    if not is_active:
        if phone:
            profile_text = (
                f"""
👤 <b>Особистий кабінет</b>                                              

<code>Ім'я: {name}
Номер: {phone}</code>

{jeans_size_line}{jacket_size_line}{jersey_size_line}
{cart_block}

<code>{level_icon} {level.capitalize() if level != 'Користувач' else level}

{progress_text}
{LOYALTY_LEXICON['profile_points'].format(points=int(points))}
{LOYALTY_LEXICON['profile_referral_points'].format(points=referral_points)}</code>

Активність:   <b>{activity + total_views}</b>

{discount_block}

{LOYALTY_LEXICON['profile_status_inactive']}
Ваш номер вже надіслано. Очікуйте підтвердження адміністратора.

"""
            )
        else:
            profile_kb.inline_keyboard.append(
                [InlineKeyboardButton(text="📞  Надіслати номер", callback_data="profile_add_phone")]
            )
            profile_text = (
                f"""
👤 <b>Особистий кабінет</b>                                              

<code>Ім'я: {name}
Номер: не додано</code>

{jacket_size_line}{jersey_size_line}{jeans_size_line}
{cart_block}

<code>Рівень: Користувач</code>

{LOYALTY_LEXICON['profile_status_inactive']}

ℹ️  Для активації профілю додайте номер телефону


"""
            )
    else:
        profile_text = (
            f"""
👤 <b>Особистий кабінет</b>                                                                                       

<code>Ім'я: {name}
Номер: {phone}</code>

{jeans_size_line}{jacket_size_line}{jersey_size_line}
{cart_block}

<code>{level_icon} {level.capitalize() if level != 'Користувач' else level}

{progress_text}
{LOYALTY_LEXICON['profile_points'].format(points=int(points))}
{LOYALTY_LEXICON['profile_referral_points'].format(points=referral_points)}</code>

Активність:   <b>{activity + total_views}</b>
<code>Час показу слайдів  <b>{slider_speed}</b> сек.</code>

{discount_block}

"""
        )

    # Кнопка close - всегда последняя
    profile_kb.inline_keyboard.append([
        InlineKeyboardButton(text=btn['x'],
                                         callback_data=NavigationCallback(action="main",
                                                                          current_level="main",
                                                                          breadcrumbs="").pack())
    ])

    await manager.edit(profile_text, reply_markup=profile_kb)

@router.callback_query(F.data == 'profile_referral_link')
async def handle_referral_link(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    await callback.answer()
    user_id = callback.from_user.id
    bot_username = (await callback.bot.me()).username
    ref_link = f"https://t.me/{bot_username}?start={user_id}"
    await manager.edit(f"<b>Ваше реферальне посилання:</b>\n{ref_link}", reply_markup=None)


@router.message(F.text == "/help", IsAdmin(admins))
async def handle_help_command(message: Message, state: FSMContext):
    """Отправляет справку по боту для всех пользователей по команде /help."""
    manager = MessageManager(message.bot, state, message.chat.id)
    await show_help_menu(manager)
    try:
        await message.delete()
    except TelegramBadRequest:
        pass


@router.callback_query(F.data == "user_show_help")
async def handle_show_help_from_profile(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    """Показывает меню помощи из профиля."""
    await show_help_menu(manager, callback)


async def show_help_menu(manager: MessageManager, callback: CallbackQuery = None):
    """Показывает главное меню помощи."""
    builder = InlineKeyboardBuilder()
    builder.button(text="❓ Ідеальна інструкція для пошуку товарів", callback_data="user_help:size_guide")
    builder.button(text="❓ Як користуватися слайдером", callback_data="user_help:slider_guide")
    builder.button(text="❓ Як користуватися профілем", callback_data="user_help:profile_guide")
    builder.button(text="👑 Програма лояльності", callback_data="user_help:loyalty_guide")
    # Добавляем кнопку "Назад в профиль", если мы пришли не из команды /help
    if callback:
        builder.button(text="← Назад до профілю", callback_data="show_profile_from_help")
    builder.adjust(1)

    if callback:
        await manager.edit(HELP_TEXT, reply_markup=builder.as_markup())
        await callback.answer()
    else:
        await manager.send(HELP_TEXT, reply_markup=builder.as_markup())


@router.callback_query(F.data == "show_profile_from_help")
async def show_profile_from_help(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    """Возвращает в профиль из меню помощи."""
    await handle_profile(callback, state, manager)


@router.callback_query(F.data.startswith("user_help:"))
async def show_instruction(callback: CallbackQuery, manager: MessageManager):
    """Показывает выбранную инструкцию."""
    instruction_type = callback.data.split(":")[1]

    instructions = {
        "size_guide": """
<b>Гід для Експертів</b>

Вітаємо у нашому магазині! Щоб ви могли легко та швидко знаходити саме те, що вам потрібно, ми створили систему "розумних" фільтрів.

<b>Ваш розумний помічник у покупках!</b>
Забудьте про складні пошуки! Бот сам прибирає все зайве і показує тільки те, що вам потрібно. Він ховає кнопки, які ведуть на порожні сторінки. Якщо у бренду немає вашого розміру, ви навіть не побачите цю кнопку. Економимо ваш час та нерви!

<b>Головна порада:</b> Не бійтеся комбінувати! Ви можете почати з розміру, категорії або бренду — фільтри спрацюють однаково коректно.

<b>Маленький секрет для ідеальної посадки:</b>
Сумніваєтесь між 52-м та 54-м? Оберіть один розмір, і бот запропонує «Додати сусідній». Натисніть — і ми покажемо речі відразу у двох розмірах. Прямо як у примірочній!

<b>Починайте сміливо!</b>
Натисніть на те, що для вас найважливіше — чи то розмір, чи то тип одягу. Це як гра: просто натискайте на кнопки, а наш розумний помічник сам знайде для вас ідеальну річ.

- - - - - - - - - - - - - - -

<b>⚙️ Внутрішня кухня: Як це працює?</b>

В основі системи лежить ваш персональний "список фільтрів", який оновлюється після кожного вашого натискання. Він зберігає все: обрану категорію, бренд, сезон і, що найголовніше, окремий детальний список для розмірів. Саме завдяки цьому центральному "мозку" система миттєво реагує на ваші дії.

<b>🧠 Правила Ієрархії: Як фільтри взаємодіють</b>

Фільтри мають строгу ієрархію, щоб відсікати зайве і попереджати помилкові комбінації.

1.  <b>Зміна <code>Категорії</code></b> (<code>куртки</code> → <code>джинси</code>) автоматично <b>скидає</b> вибір <code>Підкатегорії</code> та <code>Розміру</code>. Це логічно, адже у джинсів свої підкатегорії та розмірні сітки.
2.  <b>Зміна <code>Підкатегорії</code></b> скидає вибір <code>Розміру</code>.

<blockquote><b>Приклад:</b> Ви обрали <code>Категорія: куртки</code> та <code>Підкатегорія: вітрівка</code>. Якщо після цього змінити категорію на <code>джинси</code>, поле підкатегорії очиститься, і система запропонує вам обрати її заново, вже зі списку для джинсів.</blockquote>

<b>✨ Жива Клавіатура: Ваші фільтри в дії</b>

Клавіатура не статична — вона "живе" і реагує на ваш вибір, щоб зробити пошук інтуїтивним.

•   <b>Динамічна поява:</b> Кнопка <code>Підкатегорія</code> з'являється лише після вибору <code>Категорії</code>.
•   <b>"Розумні" кнопки:</b> Система постійно аналізує наявність товарів. Вона <b>ховає кнопки, які ведуть в глухий кут</b>. Якщо ви обрали бренд, у якого немає зимових речей, кнопка сезону "Осінь-Зима" просто не з'явиться.
•   <b>Інтерактивний лічильник:</b> Кнопка <code>▶️ X мод.</code> миттєво показує, скільки саме товарів знайдено за вашим запитом.

<b>🚀 Найцікавіше: Усе про фільтр розмірів</b>

Це найпотужніший інструмент у системі.

1.  <b>Два режими роботи:</b>
    *   <b>Простий:</b> Якщо ви вже обрали <code>Категорію</code> (напр. "куртки"), то фільтр розмірів покаже вам кнопки тільки для курток (<code>46, 48, 50...</code>).
    *   <b>Експертний:</b> Якщо ви заходите у фільтр розмірів, не обравши категорію, ви бачите панель, де розміри згруповані за типом одягу (<code>🧥 Куртки</code>, <code>👕 Трикотаж</code>, <code>👖 Джинси</code>). Це дозволяє обрати розміри для різних речей за один раз.

2.  <b>"Розумне" визначення режиму:</b> Система аналізує ваші дії. Якщо ви обрали <code>Сезон: весна-літо</code> та <code>Бренд: a-style</code>, і в наявності є тільки джинси, то фільтр розмірів автоматично відкриється в <b>простому режимі</b> з джинсовими розмірами.

3.  <b>Механізм вибору:</b>
    *   <b>Перший клік</b> на розмір — обирає його.
    *   <b>Повторний клік</b> на той самий розмір — <b>скасовує вибір для всієї категорії</b> цього розміру.
    *   Клік на інший розмір в тій самій категорії — <b>замінює</b> попередній вибір.

4.  <b>Pro-Tip: Функція "Додати сусідній"</b>
    *   Якщо ви обрали <b>один</b> розмір в категорії (напр. <code>50</code>), під ним з'являється кнопка <code>✅ Додати сусідній</code>.
    *   Натиснувши її, ви додаєте до пошуку наступний розмір (<code>52</code>). Це ідеально для пошуку речей "розмір в розмір" та "з невеликим запасом".
""",
        "slider_guide": """
<b>Інструкція: Як користуватися слайдером товарів</b>

Слайдер — це основний екран для перегляду товарів. Він може запускатися автоматично або управлятися вручную.

<b>1. Навігація і управління переглядом</b>

*   **`←` та `→`**: Використовуйте ці стрілки для ручного перемикання між товарами.
*   **`1/10`**: Цей лічильник показує номер поточної моделі та загальну кількість знайдених товарів.
*   **`||` (Пауза)**: Натисніть, щоб зупинити автоматичне перегортання слайдів.
*   **`ᐅ` (Відтворити)**: Натисніть, щоб відновити автоматичне перегортання.

<b>2. Основні дії з товаром</b>

Ряд кнопок під фотографією дозволяє управляти товаром:

*   **`+ 🛍` (Додати в кошик)**:
    1.  При першому натисканні під товаром з'являться кнопки з доступними розмірами.
    2.  Виберіть потрібний розмір, і товар додасться до кошика.
*   **`– 🛍` (Прибрати з кошика)**: Якщо товар вже в кошику, ця кнопка прибере його.
*   **`🤍 / ❤️` (В обране)**: Додає товар до вашого особистого списку обраного або видаляє з нього.
*   **`+ ℹ️` (Детальніше)**: Показує повний опис, характеристики та всі фотографії товару.
*   **`╳` (Закрити)**: Закриває слайдер і повертає вас у попереднє меню (в головне меню або до фільтрів).

<b>3. Додаткові кнопки</b>

*   **`🧹 Очистити фільтри`**: Ця кнопка з'являється внизу, якщо ви переглядаєте товари із застосованими фільтрами. Натисніть її, щоб скинути всі фільтри і побачити повний каталог.
""",
        "profile_guide": "\n<b>Інструкція: Розділ \"👤 Профіль\"</b>\n\nПрофіль — це ваш особистий кабінет, де зібрана вся інформація про вас, вашу активність, бонуси та налаштування.\n\n<b>1. Що ви бачите в профілі?</b>\n\nНа головному екрані профілю відображається зведена інформація:\n\n*   <b>Особисті дані</b>: Ваше ім'я та номер телефону.\n*   <b>Ваші розміри</b>: Збережені розміри для різних типів одягу (`🧥 Куртки`, `👕 Трикотаж`, `👖 Джинси`). Поруч у дужках зазначено, скільки моделей вашого розміру зараз є.\n*   <b>Кошик</b>: Коротка інформація про товари у вашому кошику.\n*   <b>Система лояльності</b>:\n    *   <b>Рівень</b>: Ваш поточний статус (наприклад, `🥉 Bronze`, `🥈 Silver`) та прогрес у балах до наступного рівня.\n    *   <b>Бали</b>: Окремо показані бали за покупки та за запрошених друзів.\n    *   <b>Активність</b>: Загальний лічильник ваших дій у боті.\n*   <b>Налаштування</b>: Вказана поточна швидкість прокрутки слайдера.\n\n<b>2. Кнопки управління та їх функції</b>\n\nПід основною інформацією знаходяться кнопки для управління вашим профілем:\n\n*   <b>`🎯 Мої розміри`</b>:\n    *   Дозволяє вказати, змінити або скинути ваші розміри для курток, трикотажу та джинсів.\n    *   Зберігши розміри, ви зможете швидко знаходити відповідні товари через кнопку `🎯 Для мене` в головному меню.\n*   <b>`🔔 Керування підписками`</b>:\n    *   Тут ви можете підписатися на повідомлення про нові надходження, знижки або новини брендів, у тому числі на товари певних розмірів.\n*   <b>`🌀 Архів повідомлень`</b>:\n    *   Відкриває доступ до вашого особистого архіву всіх розсилок та повідомлень, які ви отримували від бота.\n*   <b>`🔗 Реферальне посилання`</b>:\n    *   Натисніть, щоб отримати ваше унікальне посилання для запрошення друзів. Коли друг зайде в бот за вашим посиланням, ви отримаєте реферальні бали, які збільшать вашу персональну знижку.\n*   <b>`⚙️ Налаштування`</b>:\n    *   У цьому меню можна змінити <b>швидкість автопрокрутки слайдера</b>, вибравши комфортний для вас час показу (від 2 до 7 секунд).\n*   <b>`📞 Надіслати номер`</b>:\n    *   Ця кнопка з'являється, якщо ви ще не активували профіль. Натисніть її, щоб поділитися контактом, і після підтвердження адміністратором вам стануть доступні всі функції бота, включаючи оформлення замовлень.\n*   <b>`╳` (Закрити)</b>:\n    *   Закриває профіль і повертає в головне меню.\n"    }

    text = instructions.get(instruction_type, "Інструкція не знайдена.")

    builder = InlineKeyboardBuilder()
    builder.button(text="← Назад до опису", callback_data="user_help_main")

    await manager.edit(text, reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "user_help_main")
async def back_to_main_help(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    await show_help_menu(manager, callback)


@router.callback_query(NavigationCallback.filter(F.current_level == Profile.SETTINGS))
async def handle_settings_menu(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    await callback.answer()
    data = await state.get_data()
    user_id = callback.from_user.id
    from data_base.models import data_base
    slider_speed = data.get('slider_speed')
    if slider_speed is None:
        db_speed = data_base.get_slider_speed(user_id)
        slider_speed = db_speed if db_speed else 2
        await state.update_data(slider_speed=slider_speed)

    kb = InlineKeyboardBuilder()
    for sec in [2, 3, 4, 5, 7]:
        selected = '✅' if slider_speed == sec else ''
        kb.button(
            text=f"{selected} {sec} сек.",
            callback_data=f"settings_slider_speed_{sec}"
        )
    # Кнопка назад
    kb.button(
        text="← Назад",
        callback_data="settings_back_to_profile"
    )
    kb.adjust(5, 1)

    text = (
        "<b>Налаштування слайдера</b>\n"
        "\n"
        "• <b>Час показу слайда</b> — скільки секунд показувати кожний слайд\n"
    )
    await manager.edit(text, reply_markup=kb.as_markup())

@router.callback_query(F.data == "settings_back_to_profile")
async def handle_settings_back_to_profile(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    await callback.answer()
    # Просто повторно вызываем handle_profile для возврата в профиль
    await handle_profile(callback, state, manager)

# Обработка смены скорости
@router.callback_query(F.data.startswith("settings_slider_speed_"))
async def handle_slider_speed_change(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    await callback.answer()
    user_id = callback.from_user.id
    from data_base.models import data_base
    sec = int(callback.data.split('_')[-1])
    await state.update_data(slider_speed=sec)
    data_base.set_slider_speed(user_id, sec)
    await handle_settings_menu(callback, state, manager)

# --- Выбор размеров профиля ---
@router.callback_query(F.data == "profile_select_sizes")
async def handle_select_sizes(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    await callback.answer()
    user_id = callback.from_user.id
    user = data_base.sql_get_user(user_id, 'size')
    size_json = user[0] if user and user[0] else '{}'
    try:
        size_obj = json.loads(size_json)
    except Exception:
        size_obj = {}
    has_any_size = bool(size_obj.get('jacket') or size_obj.get('jersey') or size_obj.get('jeans'))

    builder = InlineKeyboardBuilder()
    builder.button(text="👖 Джинсовий розмір", callback_data="profile_select_jeans_size")
    builder.button(text="🧥 Розмір куртки", callback_data="profile_select_jacket_size")
    builder.button(text="👕 Розмір трикотажу", callback_data="profile_select_jersey_size")
    if has_any_size:
        builder.button(text="❌ Очистити мої розміри", callback_data="clear_all_user_sizes")
    builder.button(text="← Назад", callback_data="sizes_back_to_profile")
    builder.adjust(1)
    
    await manager.edit("<b>Оберіть тип розміру для налаштування:</b>", reply_markup=builder.as_markup())

@router.callback_query(F.data == "sizes_back_to_profile")
async def handle_sizes_back_to_profile(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    await callback.answer()
    await handle_profile(callback, state, manager)

# --- Выбор размера (верх) ---
@router.callback_query(F.data == "profile_select_top_size")
async def handle_select_top_size(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    await callback.answer()
    builder = InlineKeyboardBuilder()
    for value, label in JacketSizes.choices():
        builder.button(text=f"🧥 {label}", callback_data=f"set_user_top_size:{value}")
    for value, label in JerseySizes.choices():
        builder.button(text=f"👕 {label}", callback_data=f"set_user_top_size:{value}")
    builder.adjust(4)
    builder.button(text="❌ Скасувати", callback_data="cancel_user_size")
    await manager.edit("<b>Оберіть ваш розмір (верх):</b>", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("set_user_top_size:"))
async def handle_set_user_top_size(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    user_id = callback.from_user.id
    size_value = callback.data.split(":")[1]
    user = data_base.sql_get_user(user_id, 'size')
    size_json = user[0] if user and user[0] else '{}'
    try:
        size_obj = json.loads(size_json)
    except Exception:
        size_obj = {}
    size_obj['top'] = size_value
    data_base.execute_query("UPDATE users SET size = ? WHERE user_id = ?", (json.dumps(size_obj, ensure_ascii=False), user_id))
    await handle_profile(callback, state, manager)
    await callback.answer("Розмір збережено!")

# --- Выбор размера куртки ---
@router.callback_query(F.data == "profile_select_jacket_size")
async def handle_select_jacket_size(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    await callback.answer()
    builder = InlineKeyboardBuilder()
    for value, label in JacketSizes.choices():
        builder.button(text=f"🧥 {label}", callback_data=f"set_user_jacket_size:{value}")
    builder.adjust(4)
    # Кнопка сброса размера отдельным рядом внизу
    kb = builder.as_markup()
    kb.inline_keyboard.append([
        InlineKeyboardButton(text="❌ Скинути розмір куртки", callback_data="clear_user_jacket_size")
    ])
    await manager.edit("<b>Оберіть ваш розмір куртки:</b>", reply_markup=kb)

@router.callback_query(F.data.startswith("set_user_jacket_size:"))
async def handle_set_user_jacket_size(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    user_id = callback.from_user.id
    size_value = callback.data.split(":")[1]
    user = data_base.sql_get_user(user_id, 'size')
    size_json = user[0] if user and user[0] else '{}'
    try:
        size_obj = json.loads(size_json)
    except Exception:
        size_obj = {}
    size_obj['jacket'] = size_value
    data_base.execute_query("UPDATE users SET size = ? WHERE user_id = ?", (json.dumps(size_obj, ensure_ascii=False), user_id))
    await handle_select_sizes(callback, state, manager)
    await callback.answer("Розмір куртки збережено!")

# --- Выбор размера трикотажа ---
@router.callback_query(F.data == "profile_select_jersey_size")
async def handle_select_jersey_size(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    await callback.answer()
    builder = InlineKeyboardBuilder()
    for value, label in JerseySizes.choices():
        builder.button(text=f"👕 {label}", callback_data=f"set_user_jersey_size:{value}")
    builder.adjust(4)
    kb = builder.as_markup()
    kb.inline_keyboard.append([
        InlineKeyboardButton(text="❌ Скинути розмір трикотажу", callback_data="clear_user_jersey_size")
    ])
    await manager.edit("<b>Оберіть ваш розмір трикотажу:</b>", reply_markup=kb)

@router.callback_query(F.data.startswith("set_user_jersey_size:"))
async def handle_set_user_jersey_size(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    user_id = callback.from_user.id
    size_value = callback.data.split(":")[1]
    user = data_base.sql_get_user(user_id, 'size')
    size_json = user[0] if user and user[0] else '{}'
    try:
        size_obj = json.loads(size_json)
    except Exception:
        size_obj = {}
    size_obj['jersey'] = size_value
    data_base.execute_query("UPDATE users SET size = ? WHERE user_id = ?", (json.dumps(size_obj, ensure_ascii=False), user_id))
    await handle_select_sizes(callback, state, manager)
    await callback.answer("Розмір трикотажу збережено!")

# --- Выбор джинсового размера ---
@router.callback_query(F.data == "profile_select_jeans_size")
async def handle_select_jeans_size(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    await callback.answer()
    builder = InlineKeyboardBuilder()
    for value, label in JeansSizes.choices():
        builder.button(text=f"👖 {label}", callback_data=f"set_user_jeans_size:{value}")
    builder.adjust(3)
    kb = builder.as_markup()
    kb.inline_keyboard.append([
        InlineKeyboardButton(text="❌ Скинути джинсовий розмір", callback_data="clear_user_jeans_size")
    ])
    await manager.edit("<b>Оберіть ваш джинсовий розмір:</b>", reply_markup=kb)

@router.callback_query(F.data.startswith("set_user_jeans_size:"))
async def handle_set_user_jeans_size(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    user_id = callback.from_user.id
    size_value = callback.data.split(":")[1]
    user = data_base.sql_get_user(user_id, 'size')
    size_json = user[0] if user and user[0] else '{}'
    try:
        size_obj = json.loads(size_json)
    except Exception:
        size_obj = {}
    size_obj['jeans'] = size_value
    data_base.execute_query("UPDATE users SET size = ? WHERE user_id = ?", (json.dumps(size_obj, ensure_ascii=False), user_id))
    await handle_select_sizes(callback, state, manager)
    await callback.answer("Джинсовий розмір збережено!")

@router.callback_query(F.data == "cancel_user_size")
async def handle_cancel_user_size(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    await callback.answer("Вибір розміру скасовано")
    await handle_select_sizes(callback, state, manager)

# --- Сброс размера куртки ---
@router.callback_query(F.data == "clear_user_jacket_size")
async def handle_clear_user_jacket_size(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    user_id = callback.from_user.id
    user = data_base.sql_get_user(user_id, 'size')
    size_json = user[0] if user and user[0] else '{}'
    try:
        size_obj = json.loads(size_json)
    except Exception:
        size_obj = {}
    if 'jacket' in size_obj:
        del size_obj['jacket']
    data_base.execute_query("UPDATE users SET size = ? WHERE user_id = ?", (json.dumps(size_obj, ensure_ascii=False), user_id))
    await handle_select_sizes(callback, state, manager)
    await callback.answer("Розмір куртки скинуто!")

# --- Сброс размера трикотажу ---
@router.callback_query(F.data == "clear_user_jersey_size")
async def handle_clear_user_jersey_size(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    user_id = callback.from_user.id
    user = data_base.sql_get_user(user_id, 'size')
    size_json = user[0] if user and user[0] else '{}'
    try:
        size_obj = json.loads(size_json)
    except Exception:
        size_obj = {}
    if 'jersey' in size_obj:
        del size_obj['jersey']
    data_base.execute_query("UPDATE users SET size = ? WHERE user_id = ?", (json.dumps(size_obj, ensure_ascii=False), user_id))
    await handle_select_sizes(callback, state, manager)
    await callback.answer("Розмір трикотажу скинуто!")

# --- Сброс джинсового размера ---
@router.callback_query(F.data == "clear_user_jeans_size")
async def handle_clear_user_jeans_size(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    user_id = callback.from_user.id
    user = data_base.sql_get_user(user_id, 'size')
    size_json = user[0] if user and user[0] else '{}'
    try:
        size_obj = json.loads(size_json)
    except Exception:
        size_obj = {}
    if 'jeans' in size_obj:
        del size_obj['jeans']
    data_base.execute_query("UPDATE users SET size = ? WHERE user_id = ?", (json.dumps(size_obj, ensure_ascii=False), user_id))
    await handle_select_sizes(callback, state, manager)
    await callback.answer("Джинсовий розмір скинуто!")

# --- Очистка всех размеров пользователя ---
@router.callback_query(F.data == "clear_all_user_sizes")
async def handle_clear_all_user_sizes(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    user_id = callback.from_user.id
    # Очищаем все размеры, устанавливая пустой JSON
    data_base.execute_query("UPDATE users SET size = '{}' WHERE user_id = ?", (user_id,))
    await handle_profile(callback, state, manager)
    await callback.answer("Всі розміри очищено!")

# --- Статистика просмотров ---
@router.callback_query(F.data == 'profile_view_stats')
async def handle_view_stats(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    await callback.answer()
    user_id = callback.from_user.id
    
    # Получаем статистику пользователя
    user_stats = view_tracker.get_user_stats(user_id)
    view_history = view_tracker.get_user_unique_view_history(user_id, limit=10)
    
    # Формируем текст статистики
    stats_text = f"""<code><b>📊 Статистика ваших переглядів</b>

Загальна статистика:
• Всього переглядів: <b>{user_stats['total_views']}</b>
• Унікальних товарів: <b>{user_stats['unique_products']}</b>
• Середня тривалість: <b>{user_stats['avg_duration']:.1f} сек</b>
• Загальний час переглядів: <b>{user_stats['total_duration']} сек</b>

Розподіл за типами:
• Слайдер: <b>{user_stats['slider_views']}</b>
• Одиночні: <b>{user_stats['single_views']}</b>
• Галерея: <b>{user_stats['gallery_views']}</b></code>"""

    # Добавляем историю просмотров
    if view_history:
        stats_text += "\n\n<code>Останні перегляди:</code>"
        for i, view in enumerate(view_history[:5], 1):
            product_name = view.get('product_name', f'Товар {view["product_id"]}')
            view_type_emoji = {
                'slider': '👁‍🗨 ',
                'single': '👁 ',
                'gallery': '🖼 '
            }.get(view['view_type'], '👁')
            stats_text += f"\n<code>{i}. {view_type_emoji} {product_name}"
            if view['view_duration'] > 0:
                stats_text += f" ({view['view_duration']}с)"
            stats_text += "</code>"
    
    # Кнопка возврата в профиль
    kb = InlineKeyboardBuilder()
    kb.button(
        text="← Назад до профілю",
        callback_data=NavigationCallback(
            action="main",
            current_level=RegisteredMainMenu.PROFILE,
            breadcrumbs=""
        )
    )
    
    try:
        await manager.edit(stats_text, reply_markup=kb.as_markup())
    except TelegramBadRequest:
        await manager.send(stats_text, reply_markup=kb.as_markup())

# --- Обработчики избранного ---

@router.callback_query(NavigationCallback.filter(F.current_level == Profile.FAVORITES))
async def handle_favorites(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    await callback.answer()
    """Показывает список избранных товаров пользователя"""
    user_id = callback.from_user.id
    
    # Получаем избранные товары
    favorites = data_base.get_user_favorites(user_id)
    favorites_count = data_base.get_favorite_product_count(user_id)
    
    if not favorites:
        # Если избранное пустое
        kb = InlineKeyboardBuilder()
        kb.button(
            text="← Назад до профілю",
            callback_data=NavigationCallback(
                action="main",
                current_level=RegisteredMainMenu.PROFILE,
                breadcrumbs=""
            )
        )
        
        text = """<b>❤️ Моє обране</b>

У вас поки немає товарів у обраному.

Щоб додати товар до обраного, натисніть на 🤍 біля товару в каталозі."""
        
        await manager.edit(text, reply_markup=kb.as_markup())
        return
    
    # Формируем список товаров
    text = f"<b>❤️ Моє обране</b>\n\n"
    text += f"<code>Всього товарів: {favorites_count}</code>\n\n"
    
    for i, item in enumerate(favorites[:10], 1):  # Показываем первые 10
        product_name = item['name']
        brand = item['brand'] or 'Без бренду'
        price = item['sale_price']
        category = item['category'] or 'Без категорії'
        
        text += f"<b>{i}.</b> {product_name}\n"
        text += f"<code>Бренд: {brand} | Категорія: {category} | Ціна: {price} грн</code>\n"
        text += f"<code>Додано: {item['added_at'][:10]}</code>\n\n"
    
    if len(favorites) > 10:
        text += f"<code>... та ще {len(favorites) - 10} товарів</code>\n\n"
    
    # Кнопки управления
    kb = InlineKeyboardBuilder()
    
    # Кнопка очистки избранного (показываем только если больше одного товара)
    if favorites_count > 1:
        kb.button(
            text="🧹  Очистити обране",
            callback_data="favorites_clear_all"
        )
    
    # Кнопка просмотра всех избранных
    kb.button(
        text="👁  Переглянути всі",
        callback_data="favorites_view_all"
    )
    
    # Кнопка запуска слайдера избранного
    # kb.button(
    #     text="🖼 Мої збережені",
    #     callback_data="favorites_slider"
    # )
    
    # Кнопка возврата
    kb.button(
        text="← Назад до профілю",
        callback_data=NavigationCallback(
            action="main",
            current_level=RegisteredMainMenu.PROFILE,
            breadcrumbs=""
        )
    )
    
    kb.adjust(1)
    
    await manager.edit(text, reply_markup=kb.as_markup())

@router.callback_query(F.data == "favorites_clear_all")
async def handle_clear_favorites(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    await callback.answer()
    """Показывает подтверждение очистки избранного (из профиля и слайдера)"""
    user_id = callback.from_user.id
    
    # Получаем данные о том, откуда пришли
    data = await state.get_data()
    slider_source = data.get("slider_source", "")
    slider_breadcrumbs = data.get("slider_breadcrumbs", "")
    
    # Подтверждение очистки
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Так, очистити", callback_data="favorites_confirm_clear")
    kb.button(text="❌ Скасувати", callback_data="favorites_cancel_clear")
    kb.adjust(2)
    
    text = """<b>🗑 Очищення обраного</b>

Ви впевнені, що хочете видалити всі товари з обраного?

Цю дію неможливо скасувати."""
    
    await manager.edit(text, reply_markup=kb.as_markup())

@router.callback_query(F.data == "favorites_confirm_clear")
async def handle_confirm_clear_favorites(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    """Подтверждает очистку избранного"""
    user_id = callback.from_user.id
    
    # Очищаем избранное
    deleted_count = data_base.clear_user_favorites(user_id)
    
    # Получаем данные о том, откуда пришли
    data = await state.get_data()
    slider_source = data.get("slider_source", "")
    slider_breadcrumbs = data.get("slider_breadcrumbs", "")
    
    # Если мы в слайдере избранного, возвращаемся в зависимости от breadcrumbs
    if slider_source == "favorites":
        from keyboards.kb import create_main_menu_keyboard
        from utils.functions import get_caption
        from utils.filter_manager import FilterManager
        
        # Определяем куда возвращаться на основе breadcrumbs
        if slider_breadcrumbs == "filters":
            # Возвращаемся к фильтрам
            from utils.filter_manager import FilterManager
            
            # Показываем меню фильтров
            active_filters = await FilterManager.get_active_filters(state)
            text = FilterManager.create_beautiful_caption(active_filters)
            # Устанавливаем "filters" как корневой уровень breadcrumbs
            filters_breadcrumbs = "filters"
            markup = await FilterManager.create_simple_filters_keyboard(filters_breadcrumbs, active_filters, user_id=callback.from_user.id, state=state)
            
            await manager.edit(text, reply_markup=markup)
        else:
            # Возвращаемся в главное меню
            active_filters = await FilterManager.get_active_filters(state)
            start_kb = create_main_menu_keyboard(callback.from_user.id, "", "main", active_filters)
            await state.update_data(user_id=callback.from_user.id)
            caption = await get_caption(state)
            try:
                await manager.edit(caption, reply_markup=start_kb)
            except Exception as e:
                logger.error(f"Ошибка при редактировании сообщения: {e}")
                return
    else:
        # Возвращаемся к избранному в профиле (будет показано пустое состояние)
        await handle_favorites(callback, state, manager)
    
    await callback.answer(f"Видалено {deleted_count} товарів з обраного!")

@router.callback_query(F.data == "favorites_cancel_clear")
async def handle_cancel_clear_favorites(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    await callback.answer("Очищення скасовано")
    """Отменяет очистку избранного - возврат к предыдущему состоянию"""
    data = await state.get_data()
    slider_source = data.get("slider_source", "")
    slider_breadcrumbs = data.get("slider_breadcrumbs", "")
    
    # Если мы в слайдере избранного, возвращаемся к слайдеру
    if slider_source == "favorites":
        # Возвращаемся к слайдеру избранного
        user_id = callback.from_user.id
        favorites = data_base.get_user_favorites(user_id)
        if favorites:
            # Создаем фейковый callback для возврата к слайдеру
            class FakeCallback:
                def __init__(self, from_user, data):
                    self.from_user = from_user
                    self.data = data
                async def answer(self, text=None, show_alert=False, **kwargs):
                    pass
            
            fake_callback = FakeCallback(callback.from_user, f"favorites_slider:{slider_breadcrumbs}")
            await handle_favorites_slider(fake_callback, state, manager)
        else:
            # Если избранное пусто, возвращаемся в главное меню
            from keyboards.kb import create_main_menu_keyboard
            from utils.functions import get_caption
            from utils.filter_manager import FilterManager
            
            active_filters = await FilterManager.get_active_filters(state)
            start_kb = create_main_menu_keyboard(callback.from_user.id, "", "main", active_filters)
            await state.update_data(user_id=callback.from_user.id)
            caption = await get_caption(state)
            await manager.edit(caption, reply_markup=start_kb)
    else:
        # Если не в слайдере, возвращаемся к избранному в профиле
        await handle_favorites(callback, state, manager)

@router.callback_query(F.data == "favorites_view_all")
async def handle_view_all_favorites(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    await callback.answer()
    """Показывает все избранные товары с возможностью удаления"""
    user_id = callback.from_user.id
    
    # Получаем все избранные товары
    favorites = data_base.get_user_favorites(user_id)
    
    if not favorites:
        await handle_favorites(callback, state, manager)
        return
    
    # Показываем первые 5 товаров с кнопками удаления
    text = "<b>❤️ Всі обрані товари</b>\n\n"
    
    kb = InlineKeyboardBuilder()
    
    for i, item in enumerate(favorites[:5], 1):
        product_name = item['name']
        brand = item['brand'] or 'Без бренду'
        price = item['sale_price']
        
        text += f"<b>{i}.</b> {product_name}\n"
        text += f"<code>Бренд: {brand} | Ціна: {price} грн</code>\n\n"
        
        # Кнопка удаления для каждого товара
        kb.button(
            text=f"❌ Видалити {i}",
            callback_data=f"favorites_remove:{item['product_id']}"
        )
    
    if len(favorites) > 5:
        text += f"<code>... та ще {len(favorites) - 5} товарів</code>\n\n"
    
    # Кнопка возврата
    kb.button(
        text="← Назад до обраного",
        callback_data=NavigationCallback(
            action="main",
            current_level=Profile.FAVORITES,
            breadcrumbs=""
        )
    )
    
    kb.adjust(1)
    
    await manager.edit(text, reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("favorites_remove:"))
async def handle_remove_from_favorites(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    """Удаляет товар из избранного"""
    user_id = callback.from_user.id
    product_id = int(callback.data.split(":")[1])
    
    # Удаляем из избранного
    removed = data_base.remove_from_favorites(user_id, product_id)
    
    if removed:
        await callback.answer("Товар видалено з обраного!")
        # Обновляем список
        await handle_view_all_favorites(callback, state, manager)
    else:
        await callback.answer("Товар не знайдено в обраному")

@router.callback_query(F.data.startswith("favorites_slider"))
async def handle_favorites_slider(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    """Запускает слайдер с избранными товарами (папка избранных с отметкой favorite)"""
    user_id = callback.from_user.id
    # Определяем источник запуска
    if ":" in callback.data:
        _, source = callback.data.split(":", 1)
    else:
        source = "profile"
    
    # Определяем breadcrumbs на основе источника
    if source == "filters":
        breadcrumbs = "filters"
    elif source == "profile":
        breadcrumbs = "profile"
    else:
        breadcrumbs = "main"
    # Получаем избранные товары
    favorites = data_base.get_user_favorites(user_id)
    if not favorites:
        await callback.answer("У вас немає товарів у обраному!", show_alert=True)
        return
    # Получаем медиа для каждого избранного товара
    media_list = []
    product_ids = []
    for favorite in favorites:
        product_id = favorite['product_id']
        product_media = data_base.get_product_media(product_id)
        if product_media:
            main_media = None
            for media in product_media:
                if media[3]:
                    main_media = media
                    break
            if not main_media and product_media:
                main_media = product_media[0]
            if main_media:
                orig_caption = main_media[4] or ""
                caption = f"⭐ favorite\n{orig_caption}" if orig_caption else "⭐ favorite"
                media_list.append({
                    "path": main_media[1],
                    "media_type": main_media[2],
                    "caption": caption
                })
                product_ids.append(product_id)
    if not media_list:
        await callback.answer("У обраних товарів немає медіа!", show_alert=True)
        return
    
    await callback.answer(f"Запущено слайдер з {len(media_list)} обраними товарами!")

    # Сохраняем данные для возврата к избранному
    await state.update_data(
        return_to_favorites=True,
        favorites_source=source
    )
    # Запускаем слайдер с избранными товарами
    cart_items = data_base.get_cart(user_id)
    await state.update_data(cart_items=cart_items)
    slider_manager = SliderManager(manager, state)
    # Для слайдера избранного всегда используем source="favorites"
    slider_source = "favorites"
    await slider_manager.start_slider(
        media_list=media_list,
        product_ids=product_ids,
        source=slider_source,
        user_id=user_id,
        breadcrumbs=breadcrumbs
    )


@router.callback_query(F.data.startswith("toggle_favorite:"))
async def handle_toggle_favorite(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    """Добавляет или удаляет товар из избранного (в слайдере избранного обновляет список)"""
    user_id = callback.from_user.id
    product_id = int(callback.data.split(":")[1])
    
    # Проверяем, есть ли товар в избранном
    is_favorite = data_base.is_product_in_favorites(user_id, product_id)
    
    if is_favorite:
        # Удаляем из избранного
        removed = data_base.remove_from_favorites(user_id, product_id)
        if removed:
            await callback.answer("Видалено з обраного ❌")
        else:
            await callback.answer("Помилка видалення")
    else:
        # Добавляем в избранное
        added = data_base.add_to_favorites(user_id, product_id)
        if added:
            await callback.answer("Додано до обраного ⭐")
        else:
            await callback.answer("Товар вже в обраному")

    # === ОБНОВЛЯЕМ ДАННЫЕ В FSM ===
    try:
        data = await state.get_data()
        favorites_data = data.get("favorites_data", {})
        # Обновляем статус избранного для данного товара
        favorites_data[product_id] = not is_favorite  # Инвертируем статус
        await state.update_data(favorites_data=favorites_data)
        logger.debug(f"handle_toggle_favorite: updated favorites_data for product_id={product_id}, new_status={favorites_data[product_id]}")
    except Exception as e:
        logger.error(f"Error updating favorites_data in FSM: {e}")
    
    # Обновляем слайдер избранного с новым списком
    try:
        data = await state.get_data()
        slider_source = data.get("slider_source", "main")
        # Только если это слайдер избранного
        if slider_source == "favorites":
            # В слайдере избранного просто обновляем текущий слайд с новым статусом избранного
            # Получаем текущие данные слайдера
            media_list = data.get("media_list", [])
            product_ids = data.get("product_ids", [])
            current_index = data.get("index", 0)
            
            # Просто обновляем текущий слайд с новым статусом избранного
            if media_list and product_ids and current_index < len(product_ids):
                slider_manager = SliderManager(manager, state)
                await slider_manager.update_photo(
                    current_index,
                    paused=not data.get("playing", False),
                    expanded=data.get("expanded", True),
                    user_id=user_id
                )
        else:
            # Обычное поведение для других слайдеров
            media_list = data.get("media_list", [])
            product_ids = data.get("product_ids", [])
            current_index = data.get("index", 0)
            expanded = data.get("expanded", True)
            if media_list and product_ids and current_index < len(product_ids):
                slider_manager = SliderManager(manager, state)
                await slider_manager.update_photo(
                    current_index,
                    paused=not data.get("playing", False),
                    expanded=expanded,
                    user_id=user_id
                )
    except Exception as e:
        logger.error(f"Error updating slider after favorite toggle: {e}")
        pass

# --- Обработчики слайдера корзины ---

@router.callback_query(F.data.startswith("cart_slider"))
async def handle_cart_slider(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    await callback.answer()
    """Запускает слайдер с товарами из корзины (папка корзины с отметкой cart)"""
    user_id = callback.from_user.id
    # Определяем источник запуска
    if ":" in callback.data:
        _, source = callback.data.split(":", 1)
    else:
        source = "profile"
    
    # Определяем breadcrumbs на основе источника
    if source == "filters":
        breadcrumbs = "filters"
    elif source == "profile":
        breadcrumbs = "profile"
    else:
        breadcrumbs = "main"
    
    # Получаем товары из корзины
    cart_items = data_base.get_cart(user_id)
    if not cart_items:
        await callback.answer("Ваш кошик порожній!", show_alert=True)
        return
    
    # Получаем медиа для каждого товара из корзины
    media_list = []
    product_ids = []
    for item in cart_items:
        product_id = item.get("product_id")
        product_media = data_base.get_product_media(product_id)
        if product_media:
            main_media = None
            for media in product_media:
                if media[3]:
                    main_media = media
                    break
            if not main_media and product_media:
                main_media = product_media[0]
            if main_media:
                orig_caption = main_media[4] or ""
                size = item.get("size_value")
                qty = item.get("quantity", 1)
                caption = f"🛍 корзина\n"
                if size:
                    caption += f"Розмір: {size}\n"
                caption += f"Кількість: {qty}\n"
                if orig_caption:
                    caption += f"{orig_caption}"
                media_list.append({
                    "path": main_media[1],
                    "media_type": main_media[2],
                    "caption": caption
                })
                product_ids.append(product_id)
    
    if not media_list:
        await callback.answer("У товарів з кошика немає медіа!", show_alert=True)
        return
    
    # Сохраняем данные для возврата к корзине
    await state.update_data(
        return_to_cart=True,
        cart_source=source
    )
    
    # Запускаем слайдер с товарами из корзины
    slider_manager = SliderManager(manager, state)
    # Для слайдера корзины всегда используем source="cart"
    slider_source = "cart"
    await slider_manager.start_slider(
        media_list=media_list,
        product_ids=product_ids,
        source=slider_source,
        user_id=user_id,
        cart_items=cart_items,
        breadcrumbs=breadcrumbs
    )
    await callback.answer(f"Запущено слайдер з {len(media_list)} товарами з кошика!", show_alert=True)


@router.callback_query(NavigationCallback.filter(F.current_level == Profile.CART))
async def handle_cart(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    await callback.answer()
    """
    Обработчик кнопки корзины. На главной и в фильтрах — слайдер, в профиле — старый текстовый вид.
    """
    from keyboards.kb import NavigationCallback
    callback_data = NavigationCallback.unpack(callback.data)
    breadcrumbs = callback_data.breadcrumbs if callback_data.breadcrumbs else "main"
    user_id = callback.from_user.id
    cart_items = data_base.get_cart(user_id)
    if not cart_items:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.answer("Ваш кошик порожній!", show_alert=True)
        return

    if breadcrumbs == "main" or breadcrumbs == "":
        # --- Слайдер корзины (главная и фильтры) ---
        # Создаем фейковый callback для запуска слайдера корзины
        class FakeCallback:
            def __init__(self, from_user, data):
                self.from_user = from_user
                self.data = data
            async def answer(self, text=None, show_alert=False, **kwargs):
                pass
        
        fake_callback = FakeCallback(callback.from_user, f"cart_slider:{breadcrumbs}")
        await handle_cart_slider(fake_callback, state, manager)
        return

    # --- Старый вид для профиля ---
    await state.update_data(cart_source="profile")
    from utils.functions import get_cart_block_profile
    text = get_cart_block_profile(user_id)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    data = await state.get_data()
    cart_source = data.get("cart_source", "profile")
    remove_buttons = []
    for i, item in enumerate(cart_items):
        if len(cart_items) == 1:
            break
        cart_id = item.get("id")
        name = item.get("name")
        size = item.get("size_value")
        product_id = item.get("product_id")
        btn_text = f"╳ Видалити: ID {product_id} {name}"
        if size:
            btn_text += f" ({size})"
        remove_buttons.append([
            InlineKeyboardButton(text=btn_text, callback_data=f"cart_remove:{cart_id}")
        ])
    back_text = "⬅️  До профілю"
    back_callback = NavigationCallback(action="main", current_level="profile", breadcrumbs="").pack()
    
    # Показываем кнопку очистки только если в корзине есть товары
    keyboard_buttons = remove_buttons.copy()
    if cart_items:
        keyboard_buttons.append([
            InlineKeyboardButton(text="❌  Очистити кошик", callback_data="cart_clear"),
            InlineKeyboardButton(text=back_text, callback_data=back_callback)
        ])
    else:
        keyboard_buttons.append([
            InlineKeyboardButton(text=back_text, callback_data=back_callback)
        ])
    
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await manager.send(text, reply_markup=kb)

# Обработчик для очистки корзины (из профиля и слайдера)
@router.callback_query(F.data == "cart_clear")
async def handle_cart_clear_confirm(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    await callback.answer()
    """Показывает подтверждение очистки корзины"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    # Получаем данные о том, откуда пришли
    data = await state.get_data()
    slider_source = data.get("slider_source", "")
    slider_breadcrumbs = data.get("slider_breadcrumbs", "")
    
    # Кнопки подтверждения
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Так, очистити", callback_data="cart_clear_confirm"),
            InlineKeyboardButton(text="❌ Скасувати", callback_data="cart_clear_cancel")
        ]
    ])
    
    await manager.edit("Ви впевнені, що хочете очистити весь кошик?", reply_markup=kb)

# Обработчик подтверждения очистки корзины
@router.callback_query(F.data == "cart_clear_confirm")
async def handle_cart_clear(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    user_id = callback.from_user.id
    deleted = data_base.clear_cart(user_id)
    if deleted:
        await callback.answer("Ваш кошик порожній!", show_alert=True)
        from keyboards.kb import create_main_menu_keyboard
        from utils.functions import get_caption
        from utils.filter_manager import FilterManager
        import asyncio
        data = await state.get_data()
        if "animation_task" in data and not data["animation_task"].done():
            data["animation_task"].cancel()
            try:
                await data["animation_task"]
            except asyncio.CancelledError:
                pass
        cart_source = data.get("cart_source", "main")
        slider_source = data.get("slider_source", "")
        slider_breadcrumbs = data.get("slider_breadcrumbs", "")
        
        # Если мы в слайдере корзины, возвращаемся в зависимости от breadcrumbs
        if slider_source == "cart":
            if slider_breadcrumbs == "filters":
                # Возврат в фильтры
                active_filters = await FilterManager.get_active_filters(state)
                from utils.filter_manager import FilterManager
                text = FilterManager.create_beautiful_caption(active_filters)
                markup = await FilterManager.create_simple_filters_keyboard("filters", active_filters, user_id=callback.from_user.id, state=state)
                await manager.edit(text, reply_markup=markup)
                return
            else:
                # Возврат в главное меню
                active_filters = await FilterManager.get_active_filters(state)
                start_kb = create_main_menu_keyboard(callback.from_user.id, "", "main", active_filters)
                await state.update_data(user_id=callback.from_user.id)
                caption = await get_caption(state)
                try:
                    await manager.edit(caption, reply_markup=start_kb)
                except Exception as e:
                    logger.error(f"Ошибка при редактировании сообщения: {e}")
                    return
        elif cart_source == "filters":
            # Возврат в фильтры
            active_filters = await FilterManager.get_active_filters(state)
            from utils.filter_manager import FilterManager
            text = FilterManager.create_beautiful_caption(active_filters)
            markup = await FilterManager.create_simple_filters_keyboard("filters", active_filters, user_id=callback.from_user.id, state=state)
            await manager.edit(text, reply_markup=markup)
            return
        else:
            # Показываем главное меню
            active_filters = await FilterManager.get_active_filters(state)
            start_kb = create_main_menu_keyboard(callback.from_user.id, "", "main", active_filters)
            await state.update_data(user_id=callback.from_user.id)
            caption = await get_caption(state)
            try:
                await manager.edit(caption, reply_markup=start_kb)
            except Exception as e:
                logger.error(f"Ошибка при редактировании сообщения: {e}")
                return
    else:
        await callback.answer("Ваш кошик порожній!", show_alert=True)

# Обработчик отмены очистки корзины
@router.callback_query(F.data == "cart_clear_cancel")
async def handle_cart_clear_cancel(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    await callback.answer("Очищення скасовано.")
    """Отмена очистки корзины - возврат к предыдущему состоянию"""
    data = await state.get_data()
    slider_source = data.get("slider_source", "")
    slider_breadcrumbs = data.get("slider_breadcrumbs", "")
    
    # Если мы в слайдере корзины, возвращаемся к слайдеру
    if slider_source == "cart":
        # Возвращаемся к слайдеру корзины
        user_id = callback.from_user.id
        cart_items = data_base.get_cart(user_id)
        if cart_items:
            # Создаем фейковый callback для возврата к слайдеру
            class FakeCallback:
                def __init__(self, from_user, data):
                    self.from_user = from_user
                    self.data = data
                async def answer(self, text=None, show_alert=False, **kwargs):
                    pass
            
            fake_callback = FakeCallback(callback.from_user, f"cart_slider:{slider_breadcrumbs}")
            await handle_cart_slider(fake_callback, state, manager)
        else:
            # Если корзина пуста, возвращаемся в главное меню
            from keyboards.kb import create_main_menu_keyboard
            from utils.functions import get_caption
            from utils.filter_manager import FilterManager
            
            active_filters = await FilterManager.get_active_filters(state)
            start_kb = create_main_menu_keyboard(callback.from_user.id, "", "main", active_filters)
            await state.update_data(user_id=callback.from_user.id)
            caption = await get_caption(state)
            await manager.edit(caption, reply_markup=start_kb)
    else:
        # Если не в слайдере, просто возвращаемся к корзине в профиле
        user_id = callback.from_user.id
        cart_items = data_base.get_cart(user_id)
        if cart_items:
            from keyboards.kb import NavigationCallback
            nav_cb = NavigationCallback(action="main", current_level="cart", breadcrumbs="profile").pack()
            
            class FakeCallback:
                def __init__(self, from_user, data):
                    self.from_user = from_user
                    self.data = data
                async def answer(self, text=None, show_alert=False, **kwargs):
                    pass
            
            fake_callback = FakeCallback(callback.from_user, nav_cb)
            await handle_cart(fake_callback, state, manager)
        else:
            # Если корзина пуста, возвращаемся в профиль
            from keyboards.kb import NavigationCallback
            nav_cb = NavigationCallback(action="main", current_level="profile", breadcrumbs="").pack()
            
            class FakeCallback:
                def __init__(self, from_user, data):
                    self.from_user = from_user
                    self.data = data
                async def answer(self, text=None, show_alert=False, **kwargs):
                    pass
            
            fake_callback = FakeCallback(callback.from_user, nav_cb)
            await handle_profile(fake_callback, state, manager)

@router.callback_query(F.data.startswith("cart_remove:"))
async def handle_cart_remove(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    await callback.answer()
    """
    Показывает подтверждение поштучного удаления товара из корзины.
    """
    cart_id = callback.data.split(":")[1]
    # Кнопки подтверждения
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Так, видалити", callback_data=f"cart_remove_confirm:{cart_id}"),
            InlineKeyboardButton(text="❌ Скасувати", callback_data="cart_remove_cancel")
        ]
    ])
    await manager.edit("Ви впевнені, що хочете видалити цей товар з кошика?", reply_markup=kb)

@router.callback_query(F.data.startswith("cart_remove_confirm:"))
async def handle_cart_remove_confirm(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    """
    Удаляет товар из корзины по cart_id и обновляет корзину.
    """
    cart_id = callback.data.split(":")[1]
    # Удаляем из базы
    from data_base.models import data_base
    data_base.execute_query("DELETE FROM cart WHERE id = ?", (cart_id,))
    
    # Сначала обновляем корзину, чтобы убрать кнопки подтверждения
    user_id = callback.from_user.id
    data = await state.get_data()
    cart_source = data.get("cart_source", "main")
    
    # Получаем NavigationCallback для возврата
    from keyboards.kb import NavigationCallback
    if cart_source == "profile":
        nav_cb = NavigationCallback(action="main", current_level="cart", breadcrumbs="profile").pack()
    elif cart_source == "filters":
        nav_cb = NavigationCallback(action="main", current_level="cart", breadcrumbs="").pack()
    else:
        nav_cb = NavigationCallback(action="main", current_level="cart", breadcrumbs="main").pack()
    
    # Создаём фейковый callback с нужными данными
    class FakeCallback:
        def __init__(self, from_user, data):
            self.from_user = from_user
            self.data = data
        async def answer(self, text=None, show_alert=False, **kwargs):
            pass  # Пустой асинхронный метод answer для совместимости
    
    fake_callback = FakeCallback(callback.from_user, nav_cb)
    await handle_cart(fake_callback, state, manager)
    
    # После обновления корзины показываем уведомление
    await callback.answer("Товар видалено з кошика!")

@router.callback_query(F.data == "cart_remove_cancel")
async def handle_cart_remove_cancel(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    await callback.answer("Видалення скасовано.")
    """
    Отмена удаления — просто обновляем корзину.
    """
    # Сначала обновляем корзину, чтобы убрать кнопки подтверждения
    data = await state.get_data()
    cart_source = data.get("cart_source", "main")
    from keyboards.kb import NavigationCallback
    if cart_source == "profile":
        nav_cb = NavigationCallback(action="main", current_level="cart", breadcrumbs="profile").pack()
    elif cart_source == "filters":
        nav_cb = NavigationCallback(action="main", current_level="cart", breadcrumbs="").pack()
    else:
        nav_cb = NavigationCallback(action="main", current_level="cart", breadcrumbs="main").pack()
    
    class FakeCallback:
        def __init__(self, from_user, data):
            self.from_user = from_user
            self.data = data
        async def answer(self, text=None, show_alert=False, **kwargs):
            pass  # Пустой асинхронный метод answer для совместимости
    
    fake_callback = FakeCallback(callback.from_user, nav_cb)
    await handle_cart(fake_callback, state, manager)

# --- Архів повідомлень ---

@router.callback_query(F.data == "user_message_archive")
async def handle_user_message_archive(callback: CallbackQuery, manager: MessageManager):
    """Показывает список заархивированных сообщений для пользователя."""
    await callback.answer()
    user_id = callback.from_user.id
    archived_messages = data_base.get_archived_messages_for_user(user_id)
    
    builder = InlineKeyboardBuilder()
    text = "🌀  <b>Архів повідомлень</b>\n\n"
    if not archived_messages:
        text += "Архів порожній."
    else:
        text += "Натисніть на повідомлення для перегляду:"
        for msg in archived_messages:
            builder.button(text=f"📄 {msg['name']}", callback_data=f"view_user_archive:{msg['id']}")
    
    # Кнопка "Назад в профиль"
    builder.button(
        text="← Назад до профілю",
        callback_data=NavigationCallback(action="main", current_level=RegisteredMainMenu.PROFILE, breadcrumbs="").pack()
    )
    builder.adjust(1)
    
    await manager.edit(text, reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("view_user_archive:"))
async def view_user_archived_message(callback: CallbackQuery, manager: MessageManager):
    """Показывает содержимое заархивированного сообщения."""
    await callback.answer()
    try:
        message_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        logger.error(f"Invalid message_id in callback: {callback.data}")
        return

    message_data = data_base.get_archived_message_by_id(message_id)
    if not message_data:
        await manager.edit("Повідомлення не знайдено в архіві.")
        return

    builder = InlineKeyboardBuilder()
    # Кнопка удаления только для админов
    if callback.from_user.id in admins:
        builder.button(text="❌ Видалити", callback_data=f"delete_user_archive_confirm:{message_id}")
    
    builder.button(text="← Назад до архіву", callback_data="user_message_archive")
    builder.adjust(1)

    await manager.edit(message_data['content'], reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("delete_user_archive_confirm:"))
async def delete_user_archive_confirm(callback: CallbackQuery, manager: MessageManager):
    """Запрашивает подтверждение на удаление (только для админов)."""
    await callback.answer()
    if callback.from_user.id not in admins:
        return
        
    try:
        message_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        return

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Так, видалити", callback_data=f"delete_user_archive_execute:{message_id}")
    builder.button(text="Скасувати", callback_data=f"view_user_archive:{message_id}")
    builder.adjust(2)

    text = "Ви впевнені, що хочете видалити це повідомлення з архіву? Ця дія незворотна."
    await manager.edit(text, reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("delete_user_archive_execute:"))
async def delete_user_archive_execute(callback: CallbackQuery, state: FSMContext, manager: MessageManager):
    """Удаляет сообщение из архива (только для админов)."""
    await callback.answer()
    if callback.from_user.id not in admins:
        return
        
    try:
        message_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        return

    data_base.delete_archived_message(message_id)
    
    # Обновляем список архива
    archived_messages = data_base.get_archived_messages_for_user(callback.from_user.id)
    builder = InlineKeyboardBuilder()
    text = "🌀 <b>Архів повідомлень</b>\n\n"
    if not archived_messages:
        text += "Архів тепер порожній."
    else:
        text += "Натисніть на повідомлення для перегляду:"
        for msg in archived_messages:
            builder.button(text=f"📄 {msg['name']}", callback_data=f"view_user_archive:{msg['id']}")
    
    builder.button(
        text="← Назад до профілю",
        callback_data=NavigationCallback(action="main", current_level=RegisteredMainMenu.PROFILE, breadcrumbs="").pack()
    )
    builder.adjust(1)
    
    await manager.edit(text, reply_markup=builder.as_markup())