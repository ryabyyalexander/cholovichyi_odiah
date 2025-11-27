from typing import Optional, List, Dict

from .base_repository import BaseRepository


class InventoryRepository(BaseRepository):
    """Репозиторий для управления инвентарем и остатками."""

    def register_inventory_receipt(self, product_id: int, size_value: str, quantity: int,
                                  purchase_price: float, admin_id: int, notes: str = None) -> int:
        size_id = self._db.products.get_size_id(size_value) if size_value else None
        
        cursor = self._execute_query(
            "INSERT INTO inventory_receipts (product_id, size_id, quantity, purchase_price, admin_id, notes) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (product_id, size_id, quantity, purchase_price, admin_id, notes)
        )
        receipt_id = cursor.lastrowid
        
        if size_id:
            cursor = self._execute_query(
                "SELECT quantity FROM product_variants WHERE product_id = ? AND size_id = ?",
                (product_id, size_id)
            )
            existing = cursor.fetchone()
            
            if existing:
                self._execute_query(
                    "UPDATE product_variants SET quantity = quantity + ? WHERE product_id = ? AND size_id = ?",
                    (quantity, product_id, size_id)
                )
            else:
                self._execute_query(
                    "INSERT INTO product_variants (product_id, size_id, quantity) VALUES (?, ?, ?)",
                    (product_id, size_id, quantity)
                )
        return receipt_id

    def get_inventory_history(self, product_id: int = None) -> list:
        # ... (logic to be moved)
        pass

    def get_total_inventory_stats(self) -> dict:
        query = '''
            SELECT
                COUNT(DISTINCT CASE WHEN p.is_active = 1 THEN p.id END) as active_products,
                COUNT(DISTINCT CASE WHEN p.is_active = 0 THEN p.id END) as inactive_products,
                SUM(CASE WHEN p.is_active = 1 THEN pv.quantity ELSE 0 END) as total_quantity,
                SUM(CASE WHEN p.is_active = 1 THEN pv.quantity * (p.sale_price * (1 - p.discount / 100.0)) ELSE 0 END) as total_value
            FROM products p
            LEFT JOIN product_variants pv ON p.id = pv.product_id
        '''
        cursor = self._execute_query(query)
        result = cursor.fetchone()
        return {
            'active_products': result[0] or 0,
            'inactive_products': result[1] or 0,
            'total_quantity': result[2] or 0,
            'total_value': result[3] or 0
        }

    def get_inventory_by_category(self) -> list:
        # ... (logic to be moved)
        pass

    def get_inventory_by_subcategory(self) -> list:
        # ... (logic to be moved)
        pass

    def get_inventory_by_brand(self) -> list:
        # ... (logic to be moved)
        pass

    def get_all_brands(self) -> List[str]:
        cursor = self._execute_query(
            "SELECT DISTINCT brand FROM products WHERE brand IS NOT NULL ORDER BY brand"
        )
        return [row[0] for row in cursor.fetchall()]

    def get_inventory_by_size(self, size_type: Optional[str] = None) -> list:
        # ... (logic to be moved)
        pass
