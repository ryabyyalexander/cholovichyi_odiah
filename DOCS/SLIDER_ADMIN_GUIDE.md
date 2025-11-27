# 👨‍💼 Слайдер - Руководство администратора

## 📋 Содержание

1. [Обзор системы](#обзор-системы)
2. [Управление слайдером](#управление-слайдером)
3. [Мониторинг и аналитика](#мониторинг-и-аналитика)
4. [Настройки и конфигурация](#настройки-и-конфигурация)
5. [Устранение неполадок](#устранение-неполадок)
6. [Безопасность](#безопасность)
7. [Резервное копирование](#резервное-копирование)
8. [Обновления и миграции](#обновления-и-миграции)

## 🎯 Обзор системы

### Архитектура слайдера

Слайдер представляет собой комплексную систему для отображения товаров с возможностью:
- **Автопроигрывания** медиа-контента
- **Интерактивной навигации** между товарами
- **Интеграции с корзиной** и избранным
- **Детального просмотра** товаров
- **Фильтрации** по различным критериям

### Компоненты системы

```
📱 Пользовательский интерфейс
├── 🎮 Управление слайдером
├── 🛒 Интеграция с корзиной
├── ❤️ Работа с избранным
└── 📋 Детальный просмотр

🔧 Техническая инфраструктура
├── 🗄️ База данных
├── 📊 Система аналитики
├── 🔒 Безопасность
└── 📈 Мониторинг
```

## 🎛️ Управление слайдером

### Административные функции

#### Редактирование товаров из слайдера

**Доступ**: Только администраторы

**Процесс**:
1. В слайдере нажмите **✏️ Редагувати**
2. Откроется карточка товара с возможностью редактирования
3. Доступные поля для редактирования:
   - 📂 Категория
   - 🗂 Подкатегории
   - 🌦 Сезон
   - ✏️ Название
   - ™️ Бренд
   - 📝 Описание
   - 💰 Цена
   - 🔥 Скидка
   - 📏 Размеры
   - 🖼 Фото
   - ❌ Удаление товара

#### Управление медиа-контентом

**Добавление фото**:
1. Откройте карточку товара
2. Нажмите **🖼 Фото**
3. Загрузите изображения
4. Установите главное фото

**Удаление фото**:
1. Выберите фото в галерее
2. Нажмите **🗑️ Удалить**
3. Подтвердите удаление

### Настройка источников слайдера

#### Основные источники

| Источник | Описание | Настройка |
|----------|----------|-----------|
| **main** | Основной каталог | Автоматически |
| **favorites** | Избранные товары | По запросу пользователя |
| **filters** | Отфильтрованные товары | По выбранным фильтрам |
| **sizes** | Товары по размерам | По сохраненным размерам |

#### Добавление нового источника

```python
# В utils/slider_manager.py
async def start_custom_slider(source: str, user_id: int):
    if source == "admin_panel":
        # Логика для админ-панели
        media_list = get_admin_products()
        await slider_manager.start_slider(
            media_list=media_list,
            source="admin_panel",
            user_id=user_id
        )
```

## 📊 Мониторинг и аналитика

### Ключевые метрики

#### Пользовательская активность

```sql
-- Статистика просмотров слайдера
SELECT 
    DATE(created_at) as date,
    COUNT(*) as slider_views,
    COUNT(DISTINCT user_id) as unique_users
FROM view_history 
WHERE view_type = 'slider'
GROUP BY DATE(created_at)
ORDER BY date DESC;
```

#### Производительность системы

```sql
-- Время отклика слайдера
SELECT 
    AVG(response_time) as avg_response_time,
    MAX(response_time) as max_response_time,
    COUNT(*) as total_requests
FROM slider_performance 
WHERE created_at >= NOW() - INTERVAL 24 HOUR;
```

#### Популярные товары

```sql
-- Топ товаров по просмотрам
SELECT 
    p.name,
    p.product_id,
    COUNT(vh.id) as view_count
FROM products p
JOIN view_history vh ON p.product_id = vh.product_id
WHERE vh.view_type = 'slider'
GROUP BY p.product_id
ORDER BY view_count DESC
LIMIT 10;
```

### Панель мониторинга

#### Основные показатели

- **Активные пользователи** (за последний час/день)
- **Количество просмотров** слайдера
- **Среднее время** в слайдере
- **Конверсия** (просмотр → добавление в корзину)
- **Ошибки** и их частота

#### Алерты и уведомления

```python
# Настройка алертов
ALERT_THRESHOLDS = {
    "error_rate": 0.05,  # 5% ошибок
    "response_time": 3.0,  # 3 секунды
    "memory_usage": 0.8,  # 80% памяти
    "disk_usage": 0.9     # 90% диска
}

async def check_system_health():
    # Проверка состояния системы
    if error_rate > ALERT_THRESHOLDS["error_rate"]:
        await notify_admin("Высокий уровень ошибок в слайдере")
```

## ⚙️ Настройки и конфигурация

### Глобальные настройки

#### Константы слайдера

**Файл**: `utils/slider_manager.py`

```python
# Настройки по умолчанию
DEFAULT_SLIDER_SPEED = 3  # секунды
SHUFFLE_SLIDER = True     # перемешивание товаров
MAX_SLIDER_ITEMS = 100    # максимальное количество товаров
```

#### Настройки производительности

```python
# Ограничения для предотвращения перегрузки
SLIDER_LIMITS = {
    "max_concurrent_sliders": 50,
    "max_media_per_slider": 100,
    "max_autoplay_duration": 300,  # 5 минут
    "memory_limit_mb": 512
}
```

### Пользовательские настройки

#### Скорость слайдера

Пользователи могут настраивать скорость автопроигрывания:
- **2 секунды** - быстрое переключение
- **3 секунды** - стандартная скорость
- **5 секунд** - медленное переключение

#### Персональные предпочтения

- **Избранные товары** - сохраняются в базе данных
- **История просмотров** - для аналитики
- **Настройки размера** - для персональных рекомендаций

### Конфигурация базы данных

#### Оптимизация запросов

```sql
-- Индексы для быстрой работы слайдера
CREATE INDEX idx_product_media ON product_media(product_id, media_type);
CREATE INDEX idx_user_favorites ON user_favorites(user_id, product_id);
CREATE INDEX idx_view_history ON view_history(user_id, view_type, created_at);
```

#### Очистка старых данных

```sql
-- Удаление старых записей просмотров
DELETE FROM view_history 
WHERE created_at < NOW() - INTERVAL 30 DAY;

-- Очистка неактивных сессий
DELETE FROM fsm_storage 
WHERE updated_at < NOW() - INTERVAL 1 HOUR;
```

## 🔧 Устранение неполадок

### Частые проблемы

#### Слайдер не запускается

**Симптомы**:
- Пользователь получает ошибку "Немає доступних медіа"
- Слайдер зависает на загрузке

**Диагностика**:
```python
# Проверка данных в FSM
data = await state.get_data()
logger.debug(f"FSM Data: {data}")

# Проверка медиа в базе
media_count = data_base.get_product_media_count()
logger.info(f"Total media in DB: {media_count}")
```

**Решение**:
1. Проверить наличие медиа в базе данных
2. Убедиться в корректности фильтров
3. Перезапустить слайдер

#### Медленная работа слайдера

**Симптомы**:
- Долгая загрузка изображений
- Задержки при переключении слайдов

**Диагностика**:
```python
# Измерение времени отклика
import time

start_time = time.time()
await slider_manager.update_photo(index)
duration = time.time() - start_time

if duration > 2.0:
    logger.warning(f"Slow slider update: {duration:.2f}s")
```

**Решение**:
1. Оптимизировать запросы к базе данных
2. Проверить размер изображений
3. Настроить кэширование

#### Ошибки обновления медиа

**Симптомы**:
- Ошибки "Message is not modified"
- Некорректное отображение изображений

**Диагностика**:
```python
try:
    await slider_manager.update_photo(index)
except TelegramBadRequest as e:
    logger.error(f"Telegram API error: {e}")
    # Fallback: отправка нового сообщения
    await manager.send_media_message(...)
```

**Решение**:
1. Проверить валидность file_id
2. Обновить изображения в базе
3. Использовать fallback механизм

### Логирование и отладка

#### Включение детального логирования

```python
# Настройка логгера для слайдера
import logging

slider_logger = logging.getLogger('slider')
slider_logger.setLevel(logging.DEBUG)

# Файловый обработчик
file_handler = logging.FileHandler('slider_debug.log')
file_handler.setLevel(logging.DEBUG)

# Форматтер
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
file_handler.setFormatter(formatter)
slider_logger.addHandler(file_handler)
```

#### Мониторинг ошибок

```python
# Отслеживание ошибок слайдера
async def track_slider_error(error: Exception, context: dict):
    error_data = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "context": context,
        "timestamp": datetime.now().isoformat()
    }
    
    # Сохранение в базу данных
    data_base.log_error(error_data)
    
    # Уведомление администратора
    await notify_admin(f"Slider error: {error}")
```

## 🔒 Безопасность

### Защита от злоупотреблений

#### Ограничение частоты запросов

```python
# Rate limiting для слайдера
from middlewares.anti_spam_middleware import rate_limit

@rate_limit(limit=20, window=60)  # 20 запросов в минуту
@router.callback_query(F.data.in_(["prev", "next", "pause", "play"]))
async def handle_slider_controls(callback: CallbackQuery, state: FSMContext):
    # Обработка управления слайдером
```

#### Валидация данных

```python
# Проверка входных данных
def validate_slider_request(data: dict) -> bool:
    required_fields = ["user_id", "product_id", "action"]
    
    for field in required_fields:
        if field not in data:
            return False
    
    # Проверка типов данных
    if not isinstance(data["user_id"], int):
        return False
    
    # Проверка диапазонов
    if data["user_id"] <= 0:
        return False
    
    return True
```

### Контроль доступа

#### Проверка прав администратора

```python
# Проверка прав для редактирования
async def check_admin_permissions(user_id: int) -> bool:
    if user_id not in admins:
        return False
    
    # Дополнительные проверки
    user = data_base.sql_get_user(user_id)
    if not user or user.get("is_blocked"):
        return False
    
    return True
```

#### Аудит действий

```python
# Логирование административных действий
async def log_admin_action(user_id: int, action: str, target_id: int):
    audit_data = {
        "admin_id": user_id,
        "action": action,
        "target_id": target_id,
        "timestamp": datetime.now().isoformat(),
        "ip_address": get_client_ip()
    }
    
    data_base.log_admin_action(audit_data)
```

## 💾 Резервное копирование

### Стратегия резервного копирования

#### Ежедневные резервные копии

```bash
#!/bin/bash
# backup_slider_data.sh

DATE=$(date +%Y%m%d)
BACKUP_DIR="/backups/slider"

# Резервное копирование базы данных
mysqldump -u username -p database_name > $BACKUP_DIR/slider_db_$DATE.sql

# Резервное копирование медиа-файлов
rsync -av /media/slider/ $BACKUP_DIR/media_$DATE/

# Сжатие резервных копий
tar -czf $BACKUP_DIR/slider_backup_$DATE.tar.gz $BACKUP_DIR/slider_db_$DATE.sql $BACKUP_DIR/media_$DATE/

# Удаление старых резервных копий (старше 30 дней)
find $BACKUP_DIR -name "slider_backup_*.tar.gz" -mtime +30 -delete
```

#### Автоматическое восстановление

```python
# Скрипт восстановления
async def restore_slider_data(backup_date: str):
    backup_file = f"/backups/slider/slider_backup_{backup_date}.tar.gz"
    
    if not os.path.exists(backup_file):
        raise FileNotFoundError(f"Backup file not found: {backup_file}")
    
    # Восстановление базы данных
    subprocess.run([
        "mysql", "-u", "username", "-p", "database_name",
        "<", f"/backups/slider/slider_db_{backup_date}.sql"
    ])
    
    # Восстановление медиа-файлов
    subprocess.run([
        "rsync", "-av", f"/backups/slider/media_{backup_date}/", "/media/slider/"
    ])
```

### Мониторинг резервных копий

```python
# Проверка целостности резервных копий
async def verify_backup_integrity(backup_date: str):
    backup_file = f"/backups/slider/slider_backup_{backup_date}.tar.gz"
    
    # Проверка размера файла
    file_size = os.path.getsize(backup_file)
    if file_size < 1024:  # Меньше 1KB
        await notify_admin(f"Backup file too small: {backup_file}")
        return False
    
    # Проверка контрольной суммы
    expected_checksum = get_expected_checksum(backup_date)
    actual_checksum = calculate_file_checksum(backup_file)
    
    if expected_checksum != actual_checksum:
        await notify_admin(f"Backup checksum mismatch: {backup_file}")
        return False
    
    return True
```

## 🔄 Обновления и миграции

### Процесс обновления

#### Подготовка к обновлению

1. **Создание резервной копии**
   ```bash
   ./backup_slider_data.sh
   ```

2. **Тестирование на staging**
   ```bash
   # Развертывание на тестовой среде
   git checkout new-slider-feature
   python -m pytest tests/test_slider.py
   ```

3. **Планирование downtime**
   - Уведомление пользователей
   - Подготовка rollback плана

#### Выполнение обновления

```python
# Скрипт миграции
async def migrate_slider_system():
    # 1. Остановка слайдера
    await stop_all_sliders()
    
    # 2. Выполнение миграций БД
    await run_database_migrations()
    
    # 3. Обновление кода
    await deploy_new_code()
    
    # 4. Проверка работоспособности
    await verify_system_health()
    
    # 5. Запуск слайдера
    await start_slider_system()
```

### Откат изменений

```python
# Процедура отката
async def rollback_slider_update():
    # 1. Восстановление предыдущей версии кода
    git checkout previous-version
    
    # 2. Откат миграций БД
    await rollback_database_migrations()
    
    # 3. Восстановление из резервной копии
    await restore_slider_data("latest_backup")
    
    # 4. Перезапуск системы
    await restart_slider_system()
```

### Версионирование

#### Семантическое версионирование

```
MAJOR.MINOR.PATCH

Примеры:
- 1.0.0 - Первый релиз слайдера
- 1.1.0 - Добавление новых функций
- 1.1.1 - Исправление багов
- 2.0.0 - Критические изменения API
```

#### Changelog

```markdown
# Changelog

## [2.0.0] - 2024-01-15
### Added
- Поддержка видео в слайдере
- Новая система фильтрации

### Changed
- Переработан API слайдера
- Улучшена производительность

### Fixed
- Исправлена ошибка с обновлением медиа
- Устранена проблема с памятью
```

## 📞 Поддержка и контакты

### Каналы поддержки

- **Техническая поддержка**: admin@example.com
- **Экстренные случаи**: +1234567890
- **Документация**: docs/slider/

### Эскалация проблем

1. **Уровень 1**: Базовые проблемы - решаются в течение 2 часов
2. **Уровень 2**: Критические проблемы - решаются в течение 30 минут
3. **Уровень 3**: Кризисные ситуации - немедленное реагирование

### Планы обслуживания

- **Ежедневно**: Проверка логов и метрик
- **Еженедельно**: Анализ производительности
- **Ежемесячно**: Обновление системы
- **Ежеквартально**: Аудит безопасности

---

*Это руководство поможет администраторам эффективно управлять системой слайдера и обеспечивать его стабильную работу.* 