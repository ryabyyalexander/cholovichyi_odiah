from typing import Optional, List, Any, Dict

from .base_repository import BaseRepository


class CartRepository(BaseRepository):
    """Репозиторий для управления корзиной."""

    def add_to_cart(self, user_id: int, product_id: int, size_id: int, quantity: int = 1) -> None:
        """Добавляет товар в корзину или увеличивает его количество."""
        cursor = self._execute_query(
            "SELECT id, quantity FROM cart WHERE user_id = ? AND product_id = ? AND size_id = ?",
            (user_id, product_id, size_id)
        )
        existing_item = cursor.fetchone()

        if existing_item:
            new_quantity = existing_item[1] + quantity
            self._execute_query(
                "UPDATE cart SET quantity = ? WHERE id = ?",
                (new_quantity, existing_item[0])
            )
        else:
            self._execute_query(
                "INSERT INTO cart (user_id, product_id, size_id, quantity) VALUES (?, ?, ?, ?)",
                (user_id, product_id, size_id, quantity)
            )

    def remove_from_cart(self, cart_item_id: int) -> None:
        """Удаляет товар из корзины по ID записи в корзине."""
        self._execute_query("DELETE FROM cart WHERE id = ?", (cart_item_id,))

    def update_cart_quantity(self, cart_item_id: int, new_quantity: int) -> None:
        """Обновляет количество товара в корзине."""
        if new_quantity > 0:
            self._execute_query(
                "UPDATE cart SET quantity = ? WHERE id = ?",
                (new_quantity, cart_item_id)
            )
        else:
            self.remove_from_cart(cart_item_id)

    def get_cart_items(self, user_id: int) -> List[Dict[str, Any]]:
        """Получает все товары в корзине пользователя."""
        cursor = self._execute_query(
            '''SELECT c.id, c.product_id, p.name, s.value as size, c.quantity, p.sale_price, p.discount
               FROM cart c
               JOIN products p ON c.product_id = p.id
               LEFT JOIN sizes s ON c.size_id = s.id
               WHERE c.user_id = ?''',
            (user_id,)
        )
        items = []
        for row in cursor.fetchall():
            items.append({
                'id': row[0],
                'product_id': row[1],
                'name': row[2],
                'size': row[3],
                'quantity': row[4],
                'price': row[5],
                'discount': row[6]
            })
        return items

    def clear_cart(self, user_id: int) -> None:
        """Очищает корзину пользователя."""
        self._execute_query("DELETE FROM cart WHERE user_id = ?", (user_id,))

    def is_product_in_cart(self, user_id: int, product_id: int, size_value: Optional[str] = None) -> bool:
        """Проверяет, находится ли товар в корзине."""
        if size_value:
            size_id = self._db.products.get_size_id(size_value)
            cursor = self._execute_query(
                "SELECT 1 FROM cart WHERE user_id = ? AND product_id = ? AND size_id = ?",
                (user_id, product_id, size_id)
            )
        else:
            cursor = self._execute_query(
                "SELECT 1 FROM cart WHERE user_id = ? AND product_id = ?",
                (user_id, product_id)
            )
        return cursor.fetchone() is not None
