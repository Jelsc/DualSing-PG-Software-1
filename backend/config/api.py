from ninja import NinjaAPI

from accounts.api import institutions, mobile, protected, session, web
from accounts.authentication import LiveUserJWTAuth

api = NinjaAPI(title="DualSign API", version="0.1.0")


@api.get("/health")
def health(request):
    return {"status": "ok"}


api.add_router("/web", web)
api.add_router("/web", session)
api.add_router("/mobile", mobile)
api.add_router("/mobile", protected)
api.add_router("/institutions", institutions, auth=LiveUserJWTAuth())
