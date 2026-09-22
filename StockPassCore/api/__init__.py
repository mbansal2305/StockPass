from ninja import NinjaAPI

from StockPassCore.api.auth import router as auth_router
from StockPassCore.api.users import router as users_router


api = NinjaAPI(
    title="StockPass API",
    version="1.0.0",
)


api.add_router("/auth/", auth_router)
api.add_router("/users/", users_router)