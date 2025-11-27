from typing import Optional, List, Tuple, Any, Dict

from .base_repository import BaseRepository


class ProductRepository(BaseRepository):
    """Репозиторий для управления товарами."""

    def add_product_media(self, product_id: int, file_id: str,
                          media_type: str = 'photo', is_main: bool = False,
                          caption: str = '') -> None:
        self._execute_query(
            "INSERT INTO product_media (product_id, telegram_file_id, media_type, is_main, caption) "
            "VALUES (?, ?, ?, ?, ?)",
            (product_id, file_id, media_type, int(is_main), caption))

    def get_next_product_id(self) -> int:
        cursor = self._execute_query("SELECT seq FROM sqlite_sequence WHERE name='products'")
        result = cursor.fetchone()
        return 1 if result is None else result[0] + 1

    def add_product(self, product_data: Dict[str, Any]) -> int:
        query = '''
        INSERT INTO products (
            vendor_code, name, short_description,
            purchase_price, sale_price, discount, season, loyalty_tiers, category,
            subcategory, brand, country
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        params = (
            product_data['vendor_code'],
            product_data['name'],
            product_data.get('short_description'),
            product_data['purchase_price'],
            product_data['sale_price'],
            product_data.get('discount', 0),
            product_data['season'],
            product_data.get('loyalty_tiers'),
            product_data['category'],
            product_data.get('subcategory'),
            product_data.get('brand'),
            product_data.get('country')
        )
        cursor = self._execute_query(query, params)
        return cursor.lastrowid

    def create_products_with_media(self, media_list: List[Dict[str, Any]],
                                   create_separate: bool = False) -> List[int]:
        created_ids = []
        if not media_list:
            return created_ids
        # ... (rest of the logic needs to be adapted)
        return created_ids

    def get_product_media(self, product_id: int) -> List[Dict[str, Any]]:
        cursor = self._execute_query(
            "SELECT id, telegram_file_id, media_type, is_main, caption FROM product_media WHERE product_id = ?",
            (product_id,)
        )
        media = []
        for row in cursor.fetchall():
            media.append({
                'id': row[0],
                'telegram_file_id': row[1],
                'media_type': row[2],
                'is_main': bool(row[3]),
                'caption': row[4]
            })
        return media

    def get_main_media(self, product_id: int) -> Optional[Dict[str, Any]]:
        cursor = self._execute_query(
            "SELECT id, telegram_file_id, media_type, caption FROM product_media WHERE product_id = ? AND is_main = 1",
            (product_id,)
        )
        main_media = cursor.fetchone()
        if main_media:
            return {
                'id': main_media[0],
                'telegram_file_id': main_media[1],
                'media_type': main_media[2],
                'caption': main_media[3]
            }
        return None

    def update_product_field(self, product_id: int, field: str, value: Any) -> None:
        query = f"UPDATE products SET {field} = ? WHERE id = ?"
        self._execute_query(query, (value, product_id))

    def get_product_field(self, product_id: int, field: str) -> Any:
        query = f"SELECT {field} FROM products WHERE id = ?"
        cursor = self._execute_query(query, (product_id,))
        result = cursor.fetchone()
        return result[0] if result else None

    def get_all_products(self, active_only: bool = True) -> List[Dict[str, Any]]:
        where_clause = "WHERE is_active = 1" if active_only else ""
        cursor = self._execute_query(f"SELECT * FROM products {where_clause}")
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def sql_get_product(self, product_id: int) -> Optional[Dict[str, Any]]:
        cursor = self._execute_query(
            "SELECT * FROM products WHERE id = ?",
            (product_id,)
        )
        product = cursor.fetchone()
        if product:
            columns = [column[0] for column in cursor.description]
            return dict(zip(columns, product))
        return None

    def get_products_by_filters(self, filters: Dict[str, Any], page: int = 1, page_size: int = 10) -> Tuple[List[Dict[str, Any]], int]:
        query = "SELECT DISTINCT p.* FROM products p "
        count_query = "SELECT COUNT(DISTINCT p.id) FROM products p "
        params = []
        where_clauses = ["p.is_active = 1"]

        if filters.get("sizes"):
            query += "JOIN product_variants pv ON p.id = pv.product_id JOIN sizes s ON pv.size_id = s.id "
            count_query += "JOIN product_variants pv ON p.id = pv.product_id JOIN sizes s ON pv.size_id = s.id "
            size_placeholders = ",".join("?" for _ in filters["sizes"])
            where_clauses.append(f"s.value IN ({size_placeholders})")
            params.extend(filters["sizes"])

        for key, value in filters.items():
            if key not in ["sizes", "sort_by"] and value is not None:
                if isinstance(value, list):
                    placeholders = ",".join("?" for _ in value)
                    where_clauses.append(f"p.{key} IN ({placeholders})")
                    params.extend(value)
                else:
                    where_clauses.append(f"p.{key} = ?")
                    params.append(value)

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
            count_query += " WHERE " + " AND ".join(where_clauses)

        sort_by = filters.get("sort_by", "newest")
        if sort_by == "newest":
            query += " ORDER BY p.created_at DESC"
        elif sort_by == "price_asc":
            query += " ORDER BY p.sale_price ASC"
        elif sort_by == "price_desc":
            query += " ORDER BY p.sale_price DESC"

        count_cursor = self._execute_query(count_query, tuple(params))
        total_count = count_cursor.fetchone()[0]

        offset = (page - 1) * page_size
        query += f" LIMIT {page_size} OFFSET {offset}"

        cursor = self._execute_query(query, tuple(params))
        columns = [column[0] for column in cursor.description]
        products = [dict(zip(columns, row)) for row in cursor.fetchall()]

        return products, total_count

    def get_product_variants(self, product_id: int) -> List[Dict[str, Any]]:
        cursor = self._execute_query(
            '''SELECT s.id, s.value, s.type, pv.quantity 
               FROM product_variants pv 
               JOIN sizes s ON pv.size_id = s.id 
               WHERE pv.product_id = ?''',
            (product_id,)
        )
        variants = []
        for row in cursor.fetchall():
            variants.append({
                'size_id': row[0],
                'size_value': row[1],
                'size_type': row[2],
                'quantity': row[3]
            })
        return variants

    def get_available_sizes(self, product_id: int) -> List[str]:
        cursor = self._execute_query(
            '''SELECT s.value 
               FROM product_variants pv 
               JOIN sizes s ON pv.size_id = s.id 
               WHERE pv.product_id = ? AND pv.quantity > 0''',
            (product_id,)
        )
        return [row[0] for row in cursor.fetchall()]

    def get_size_id(self, size_value: str) -> Optional[int]:
        cursor = self._execute_query(
            "SELECT id FROM sizes WHERE value = ?",
            (size_value,)
        )
        result = cursor.fetchone()
        return result[0] if result else None

    def get_all_sizes(self) -> List[Dict[str, Any]]:
        cursor = self._execute_query("SELECT id, type, value, equivalent_letter FROM sizes")
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def activate_product(self, product_id: int, admin_id: int, reason: str = None) -> bool:
        product = self.sql_get_product(product_id)
        if not product:
            raise ValueError(f"Товар {product_id} не найден")
        
        required_fields = ['name', 'purchase_price', 'sale_price', 'season', 'category']
        missing_fields = []
        
        for field in required_fields:
            if not product.get(field):
                missing_fields.append(field)
        
        if missing_fields:
            raise ValueError(f"Товар {product_id} не может быть активирован. Отсутствуют поля: {', '.join(missing_fields)}")
        
        self._execute_query(
            "UPDATE products SET is_active = 1 WHERE id = ?",
            (product_id,)
        )
        
        self._execute_query(
            "INSERT INTO product_activation_history (product_id, admin_id, action, reason) "
            "VALUES (?, ?, 'activated', ?)",
            (product_id, admin_id, reason)
        )
        return True

    def deactivate_product(self, product_id: int, admin_id: int, reason: str = None) -> bool:
        product = self.sql_get_product(product_id)
        if not product:
            raise ValueError(f"Товар {product_id} не найден")
        
        self._execute_query(
            "UPDATE products SET is_active = 0 WHERE id = ?",
            (product_id,)
        )
        
        self._execute_query(
            "INSERT INTO product_activation_history (product_id, admin_id, action, reason) "
            "VALUES (?, ?, 'deactivated', ?)",
            (product_id, admin_id, reason)
        )
        return True

    def set_main_photo(self, media_id: int, product_id: int) -> None:
        self._execute_query("UPDATE product_media SET is_main = 0 WHERE product_id = ?", (product_id,))
        self._execute_query("UPDATE product_media SET is_main = 1 WHERE id = ?", (media_id,))

    def update_media_caption(self, media_id: int, new_caption: str) -> None:
        self._execute_query("UPDATE product_media SET caption = ? WHERE id = ?", (new_caption, media_id))

    def delete_media(self, media_id: int) -> None:
        self._execute_query("DELETE FROM product_media WHERE id = ?", (media_id,))

    def get_all_categories(self) -> List[str]:
        cursor = self._execute_query("SELECT DISTINCT category FROM products WHERE category IS NOT NULL")
        return [row[0] for row in cursor.fetchall()]

    def get_subcategories_by_category(self, category: str) -> List[str]:
        cursor = self._execute_query(
            "SELECT DISTINCT subcategory FROM products WHERE category = ? AND subcategory IS NOT NULL",
            (category,)
        )
        return [row[0] for row in cursor.fetchall()]

    def update_product_variant_quantity(self, product_id: int, size_id: int, quantity: int) -> None:
        self._execute_query(
            "UPDATE product_variants SET quantity = ? WHERE product_id = ? AND size_id = ?",
            (quantity, product_id, size_id)
        )

    def delete_product(self, product_id: int) -> None:
        self._execute_query("DELETE FROM products WHERE id = ?", (product_id,))

    def get_all_product_media(self) -> List[Dict[str, Any]]:
        cursor = self._execute_query("SELECT * FROM product_media")
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_filtered_product_media(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        products, _ = self.get_products_by_filters(filters, page_size=1000) # Assuming we get all products
        product_ids = [p['id'] for p in products]
        if not product_ids:
            return []
        
        placeholders = ",".join("?" for _ in product_ids)
        query = f"SELECT * FROM product_media WHERE product_id IN ({placeholders})"
        cursor = self._execute_query(query, tuple(product_ids))
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def debug_database_content(self) -> Dict[str, Any]:
        # This is a debug method, so it's okay to have multiple queries
        _, total_active_products = self.get_products_by_filters({}, 1, 1000)
        
        cursor = self._execute_query("SELECT COUNT(DISTINCT product_id) FROM product_media")
        products_with_media = cursor.fetchone()[0]

        available_categories = self.get_all_categories()
        available_brands = self.get_all_brands()
        
        cursor = self._execute_query("SELECT DISTINCT season FROM products WHERE season IS NOT NULL")
        available_seasons = [row[0] for row in cursor.fetchall()]

        cursor = self._execute_query("SELECT category, COUNT(*) FROM products WHERE is_active = 1 GROUP BY category")
        category_counts = {row[0]: row[1] for row in cursor.fetchall()}

        sample_products = self.get_all_products(active_only=True)[:3]

        return {
            'total_active_products': total_active_products,
            'products_with_media': products_with_media,
            'available_categories': available_categories,
            'available_brands': available_brands,
            'available_seasons': available_seasons,
            'category_counts': category_counts,
            'sample_products': sample_products
        }

    def debug_subcategories(self) -> Dict[str, Any]:
        products = self.get_all_products(active_only=False)
        by_category = {}
        for p in products:
            cat = p['category']
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(p)
        
        return {
            'total_products': len(products),
            'by_category': by_category,
            'sample_products': products[:5]
        }

    def check_filter_combination_exists(self, **filters) -> bool:
        """Проверяет, существует ли хотя бы один товар по заданным фильтрам."""
        _, count = self.get_products_by_filters(filters, page_size=1)
        return count > 0

    def get_unique_categories_for_filters(self, **filters) -> List[str]:
        """Возвращает список уникальных категорий по заданным фильтрам."""
        products, _ = self.get_products_by_filters(filters, page_size=1000)
        return list(set(p['category'] for p in products))

    def get_detailed_available_sizes(self, product_id: int) -> Dict[str, Dict[str, Any]]:
        """Возвращает детальную информацию о размерах, включая резервы."""
        query = """
            SELECT 
                s.value, 
                pv.quantity, 
                (SELECT COUNT(*) FROM reservations r WHERE r.product_id = pv.product_id AND r.size_id = pv.size_id AND r.status = 'active') > 0 as is_reserved
            FROM product_variants pv
            JOIN sizes s ON pv.size_id = s.id
            WHERE pv.product_id = ?
        """
        cursor = self._execute_query(query, (product_id,))
        sizes_info = {}
        for row in cursor.fetchall():
            sizes_info[row[0]] = {
                'quantity': row[1],
                'is_reserved': bool(row[2])
            }
        return sizes_info
