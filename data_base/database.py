from .schema import setup_database
from .repositories.user_repository import UserRepository
from .repositories.product_repository import ProductRepository
from .repositories.order_repository import OrderRepository
from .repositories.cart_repository import CartRepository
from .repositories.favorite_repository import FavoriteRepository
from .repositories.loyalty_repository import LoyaltyRepository
from .repositories.promotion_repository import PromotionRepository
from .repositories.subscription_repository import SubscriptionRepository
from .repositories.message_archive_repository import MessageArchiveRepository
from .repositories.product_view_repository import ProductViewRepository
# ... и так далее

class Database:
    def __init__(self, db_name: str):
        """
        Инициализирует базу данных, настраивает схему и создает экземпляры репозиториев.
        
        Args:
            db_name: Имя файла базы данных (без .db)
        """
        # 1. Один раз настраиваем схему при запуске
        setup_database(db_name)

        # 2. Инициализируем репозитории
        self.users = UserRepository(db_name)
        self.products = ProductRepository(db_name)
        self.orders = OrderRepository(db_name)
        self.cart = CartRepository(db_name)
        self.favorites = FavoriteRepository(db_name)
        self.loyalty = LoyaltyRepository(db_name)
        self.promotions = PromotionRepository(db_name)
        self.subscriptions = SubscriptionRepository(db_name)
        self.message_archive = MessageArchiveRepository(db_name)
        self.product_views = ProductViewRepository(db_name)
        # ... и так далее

        # 3. Внедряем зависимости между репозиториями
        self.users._inject_db_instance(self)
        self.products._inject_db_instance(self)
        self.orders._inject_db_instance(self)
        self.cart._inject_db_instance(self)
        self.favorites._inject_db_instance(self)
        self.loyalty._inject_db_instance(self)
        self.promotions._inject_db_instance(self)
        self.subscriptions._inject_db_instance(self)
        self.message_archive._inject_db_instance(self)
        self.product_views._inject_db_instance(self)
