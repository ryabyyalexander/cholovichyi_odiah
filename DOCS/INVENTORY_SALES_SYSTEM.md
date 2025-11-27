# 📦 Система учета товаров и продаж

## Обзор

Система учета товаров и продаж обеспечивает полный контроль над товарными запасами, автоматизацию продаж и детальную аналитику.

## 🏗️ Архитектура

### Новые таблицы базы данных

#### 1. `inventory_receipts` - Поступления товаров
```sql
CREATE TABLE inventory_receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    size_id INTEGER,
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    purchase_price REAL NOT NULL CHECK(purchase_price >= 0),
    receipt_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    admin_id INTEGER,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY (size_id) REFERENCES sizes(id),
    FOREIGN KEY (admin_id) REFERENCES users(user_id)
);
```

#### 2. `sales` - Продажи
```sql
CREATE TABLE sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    total_amount REAL NOT NULL CHECK(total_amount >= 0),
    discount_amount REAL DEFAULT 0 CHECK(discount_amount >= 0),
    final_amount REAL NOT NULL CHECK(final_amount >= 0),
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'confirmed', 'cancelled', 'completed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TIMESTAMP,
    completed_at TIMESTAMP,
    admin_notes TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
```

#### 3. `sale_items` - Позиции продаж
```sql
CREATE TABLE sale_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    size_id INTEGER,
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    unit_price REAL NOT NULL CHECK(unit_price >= 0),
    total_price REAL NOT NULL CHECK(total_price >= 0),
    purchase_price REAL NOT NULL CHECK(purchase_price >= 0),
    profit REAL GENERATED ALWAYS AS (total_price - (purchase_price * quantity)) STORED,
    FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY (size_id) REFERENCES sizes(id)
);
```

#### 4. `product_activation_history` - История активации товаров
```sql
CREATE TABLE product_activation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    admin_id INTEGER NOT NULL,
    action TEXT NOT NULL CHECK(action IN ('activated', 'deactivated')),
    reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY (admin_id) REFERENCES users(user_id)
);
```

## 🔧 Основные методы

### Учет товаров

#### `register_inventory_receipt()`
Регистрирует поступление товара на склад.

```python
receipt_id = data_base.register_inventory_receipt(
    product_id=15,
    size_value="M",
    quantity=10,
    purchase_price=25.50,
    admin_id=123456,
    notes="Поступление от поставщика"
)
```

#### `activate_product()`
Активирует товар (делает видимым для пользователей).

```python
success = data_base.activate_product(
    product_id=15,
    admin_id=123456,
    reason="Товар готов к продаже"
)
```

#### `deactivate_product()`
Деактивирует товар (делает невидимым для пользователей).

```python
success = data_base.deactivate_product(
    product_id=15,
    admin_id=123456,
    reason="Товар закончился"
)
```

### Продажи

#### `create_sale()`
Создает заказ из корзины пользователя.

```python
order_id = data_base.create_sale(
    user_id=789012,
    cart_items=cart_items,
    discount_amount=15.50
)
```

#### `complete_sale()`
Подтверждает продажу (списывает товар).

```python
success = data_base.complete_sale(
    sale_id=25,
    admin_id=123456,
    admin_notes="Заказ подтвержден"
)
```

#### `cancel_sale()`
Отменяет продажу (возвращает товар на склад).

```python
success = data_base.cancel_sale(
    sale_id=25,
    admin_id=123456,
    reason="Товар недоступен"
)
```

### Аналитика

#### `get_sales_report()`
Получает отчет по продажам за период.

```python
report = data_base.get_sales_report(
    start_date="2024-01-01",
    end_date="2024-01-31"
)
```

#### `get_inventory_history()`
Получает историю движения товара.

```python
history = data_base.get_inventory_history(product_id=15)
```

#### `get_pending_orders()`
Получает список ожидающих подтверждения заказов.

```python
pending_orders = data_base.get_pending_orders()
```

## 📱 Интерфейс администратора

### Админ-панель

#### Управление продажами
- **📋 Очікуючі замовлення** - просмотр и обработка заказов
- **📊 Статистика продаж** - аналитика по продажам
- **📦 Управління товарами** - активация/деактивация товаров

#### Обработка заказов
1. Просмотр списка ожидающих заказов
2. Детальный просмотр каждого заказа
3. Подтверждение или отмена заказа
4. Автоматические уведомления пользователям

#### Управление товарами
1. **Активация товара**: `15a` - делает товар видимым
2. **Деактивация товара**: `15a` - скрывает товар
3. **Добавление на склад**: `15a:M:10:25.50` - добавляет товар

## 🔔 Система уведомлений

### Уведомления админам
- **Новые заказы** - автоматически при оформлении
- **Низкий остаток** - при критическом количестве
- **Активация товаров** - при изменении статуса

### Уведомления пользователям
- **Подтверждение заказа** - при обработке админом
- **Отмена заказа** - при отмене с указанием причины

## 📊 Аналитика

### Отчеты по продажам
- Общее количество заказов
- Подтвержденные и отмененные заказы
- Общая выручка и средний чек
- Топ товаров по продажам
- Прибыль по товарам

### Отчеты по товарам
- Общее количество товаров
- Активные и неактивные товары
- Остатки на складе
- История движения товаров

## 🔄 Жизненный цикл товара

### 1. Создание товара
- Товар создается неактивным (`is_active = 0`)
- Заполняются обязательные поля

### 2. Активация товара
- Админ проверяет данные товара
- Активирует товар через админ-панель
- Товар становится видимым для пользователей

### 3. Поступление на склад
- Регистрируется поступление с закупочной ценой
- Обновляется количество в `product_variants`

### 4. Продажа товара
- Пользователь добавляет товар в корзину
- Оформляет заказ
- Товар резервируется (уменьшается количество)
- Админ подтверждает заказ

### 5. Списание товара
- При подтверждении заказа товар списывается
- Записывается прибыль в `sale_items`

## 🛡️ Безопасность

### Валидация данных
- Проверка обязательных полей при активации
- Контроль остатков при продаже
- Валидация цен и количеств

### Логирование
- История всех операций с товарами
- Отслеживание изменений статусов
- Аудит действий администраторов

## 🚀 Преимущества системы

### Для администраторов
- ✅ Автоматические уведомления о заказах
- ✅ Контроль качества товаров перед активацией
- ✅ Детальная аналитика продаж
- ✅ История движения товаров

### Для пользователей
- ✅ Только качественные товары в каталоге
- ✅ Автоматическое оформление заказов
- ✅ Уведомления о статусе заказа
- ✅ Прозрачная система скидок

### Для бизнеса
- ✅ Контроль товарных запасов
- ✅ Анализ прибыльности
- ✅ Автоматизация рутинных операций
- ✅ Снижение ошибок при продажах

## 📝 Примеры использования

### Активация товара
```
Админ вводит: 15a
Система: Товар 15 активирован
Результат: Товар виден пользователям
```

### Добавление на склад
```
Админ вводит: 15a:M:10:25.50
Система: Добавлено 10 шт. размера M по цене 25.50€
Результат: Обновлены остатки на складе
```

### Оформление заказа
```
Пользователь: Нажимает "Оформить заказ"
Система: Создает заказ, резервирует товар, уведомляет админов
Результат: Заказ ожидает подтверждения
```

### Подтверждение заказа
```
Админ: Нажимает "Подтвердить"
Система: Списывает товар, уведомляет пользователя
Результат: Заказ выполнен
``` 