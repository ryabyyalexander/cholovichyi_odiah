from typing import Optional, List, Tuple, Any, Dict

from .base_repository import BaseRepository
from utils.functions import calculate_final_item_price

class OrderRepository(BaseRepository):
    """Репозиторий для управления заказами и продажами."""

    def create_sale(self, user_id: int, cart_items: list, discount_amount: float = 0) -> int:
        if not cart_items:
            raise ValueError("Корзина пуста")

        total_amount = 0
        for item in cart_items:
            product = self._db.products.sql_get_product(item['product_id'])
            if not product:
                continue
            
            final_price = calculate_final_item_price(product, user_id)
            total_amount += final_price * item['quantity']

        final_amount = total_amount - discount_amount
        
        cursor = self._execute_query(
            "INSERT INTO sales (user_id, total_amount, discount_amount, final_amount) "
            "VALUES (?, ?, ?, ?)",
            (user_id, total_amount, discount_amount, final_amount)
        )
        sale_id = cursor.lastrowid
        
        for item in cart_items:
            product_id = item['product_id']
            size_id = item.get('size_id')
            quantity = item['quantity']
            product = self._db.products.sql_get_product(product_id)
            if product:
                unit_price = product['sale_price']
                total_price = unit_price * quantity
                purchase_price = product['purchase_price'] if product else 0
                self._execute_query(
                    "INSERT INTO sale_items (sale_id, product_id, size_id, quantity, unit_price, total_price, purchase_price) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (sale_id, product_id, size_id, quantity, unit_price, total_price, purchase_price)
                )
        self._db.cart.clear_cart(user_id)
        return sale_id

    def complete_sale(self, sale_id: int, admin_id: int, admin_notes: str = None) -> bool:
        cursor = self._execute_query("SELECT status FROM sales WHERE id = ?", (sale_id,))
        result = cursor.fetchone()
        if not result:
            raise ValueError(f"Продажа {sale_id} не найдена")
        
        status = result[0]
        if status not in ['pending', 'reserved']:
            raise ValueError(f"Продажа {sale_id} уже обработана (статус: {status})")
        
        admin = self._db.users.sql_get_user(admin_id, 'is_admin')
        if not admin or not admin[0]:
            return False

        cursor = self._execute_query("SELECT product_id, size_id, quantity FROM sale_items WHERE sale_id = ?", (sale_id,))
        items = cursor.fetchall()

        for product_id, size_id, quantity in items:
            if size_id:
                update_cursor = self._execute_query(
                    "UPDATE product_variants SET quantity = quantity - ? WHERE product_id = ? AND size_id = ? AND quantity >= ?",
                    (quantity, product_id, size_id, quantity)
                )
                # self._db.products._check_and_deactivate_product_if_out_of_stock(product_id, admin_id)
        
        self._execute_query(
            "UPDATE sales SET status = 'confirmed', confirmed_at = CURRENT_TIMESTAMP, admin_notes = ? WHERE id = ?",
            (admin_notes, sale_id)
        )
        return True

    def cancel_sale(self, sale_id: int, admin_id: int, reason: str = None) -> bool:
        cursor = self._execute_query("SELECT status FROM sales WHERE id = ?", (sale_id,))
        result = cursor.fetchone()
        if not result:
            raise ValueError(f"Продажа {sale_id} не найдена")
        
        if result[0] != 'pending':
            raise ValueError(f"Продажа {sale_id} уже обработана (статус: {result[0]})")
        
        self._execute_query(
            "UPDATE sales SET status = 'cancelled', admin_notes = ? WHERE id = ?",
            (reason, sale_id)
        )
        return True

    def get_sales_report(self, start_date: str = None, end_date: str = None) -> dict:
        # ... (This method is self-contained)
        pass

    def get_detailed_sales_data(self, start_date: str, end_date: str) -> list:
        # ... (This method is self-contained)
        pass

    def get_pending_orders_count(self) -> int:
        cursor = self._execute_query("SELECT COUNT(*) FROM sales WHERE status = 'pending'")
        count = cursor.fetchone()[0]
        return count

    def get_pending_orders(self) -> list:
        cursor = self._execute_query('''
            SELECT s.id, s.user_id, s.total_amount, s.discount_amount, s.final_amount, s.created_at,
                   u.first_name, u.last_name, u.user_name, COUNT(si.id) as items_count
            FROM sales s
            JOIN users u ON s.user_id = u.user_id
            LEFT JOIN sale_items si ON s.id = si.sale_id
            WHERE s.status = 'pending'
            GROUP BY s.id
            ORDER BY s.created_at DESC
        ''')
        orders = []
        for row in cursor.fetchall():
            orders.append({
                'id': row[0],
                'user_id': row[1],
                'total_amount': row[2],
                'discount_amount': row[3],
                'final_amount': row[4],
                'created_at': row[5],
                'user_name': f"{row[6]} {row[7]}" if row[6] and row[7] else row[8] or f"User {row[1]}",
                'items_count': row[9]
            })
        return orders

    def get_user_orders(self, user_id: int) -> list:
        cursor = self._execute_query("SELECT id, total_amount, discount_amount, final_amount, status, created_at FROM sales WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
        orders = []
        for row in cursor.fetchall():
            orders.append({
                'id': row[0],
                'total_amount': row[1],
                'discount_amount': row[2],
                'final_amount': row[3],
                'status': row[4],
                'created_at': row[5],
            })
        return orders

    def get_order_details(self, order_id: int) -> dict:
        order_cursor = self._execute_query('''
            SELECT s.id, s.user_id, s.total_amount, s.discount_amount, s.final_amount, s.status, s.created_at,
                   s.confirmed_at, s.admin_notes, u.first_name, u.last_name, u.user_name, u.phone
            FROM sales s
            JOIN users u ON s.user_id = u.user_id
            WHERE s.id = ?
        ''', (order_id,))
        order_data = order_cursor.fetchone()
        if not order_data:
            return None
        
        items_cursor = self._execute_query('''
            SELECT si.id, si.product_id, si.size_id, si.quantity, si.unit_price, si.total_price, si.purchase_price,
                   si.profit, p.name, p.brand, p.category, s.value as size_value
            FROM sale_items si
            JOIN products p ON si.product_id = p.id
            LEFT JOIN sizes s ON si.size_id = s.id
            WHERE si.sale_id = ?
        ''', (order_id,))
        
        items = []
        for row in items_cursor.fetchall():
            items.append({
                'id': row[0], 'product_id': row[1], 'size_id': row[2], 'quantity': row[3],
                'unit_price': row[4], 'total_price': row[5], 'purchase_price': row[6],
                'profit': row[7], 'name': row[8], 'brand': row[9], 'category': row[10],
                'size_value': row[11]
            })
        
        return {
            'id': order_data[0], 'user_id': order_data[1], 'total_amount': order_data[2],
            'discount_amount': order_data[3], 'final_amount': order_data[4], 'status': order_data[5],
            'created_at': order_data[6], 'confirmed_at': order_data[7], 'admin_notes': order_data[8],
            'user_name': f"{order_data[9]} {order_data[10]}" if order_data[9] and order_data[10] else order_data[11] or f"User {order_data[1]}",
            'user_phone': order_data[12], 'items': items
        }

    def get_active_reservations(self) -> list:
        cursor = self._execute_query("SELECT * FROM reservations WHERE status = 'active'")
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_reservation_details(self, reservation_id: int) -> Optional[Dict[str, Any]]:
        cursor = self._execute_query("SELECT * FROM reservations WHERE id = ?", (reservation_id,))
        data = cursor.fetchone()
        if not data:
            return None
        columns = [column[0] for column in cursor.description]
        return dict(zip(columns, data))

    def update_reservation_status(self, reservation_id: int, status: str) -> None:
        self._execute_query("UPDATE reservations SET status = ? WHERE id = ?", (status, reservation_id))

    def create_reservation_from_order(self, order_id: int, admin_id: int) -> bool:
        order = self.get_order_details(order_id)
        if not order or order['status'] != 'pending':
            raise ValueError(f"Заказ {order_id} не найден или уже обработан.")

        for item in order['items']:
            self._execute_query(
                "INSERT INTO reservations (order_id, user_id, admin_id, product_id, size_id, quantity, status, final_price) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (order_id, order['user_id'], admin_id, item['product_id'], item['size_id'], item['quantity'], 'active', item['total_price'])
            )
        
        self._execute_query("UPDATE sales SET status = 'reserved' WHERE id = ?", (order_id,))
        return True

    def complete_sale_from_reservation(self, order_id: int, admin_id: int) -> None:
        self.complete_sale(order_id, admin_id, "Продано из резерва")
