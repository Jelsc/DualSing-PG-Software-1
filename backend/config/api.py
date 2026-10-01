from ninja import NinjaAPI

from accounts.api import institutions, mobile, protected, session, web
from accounts.authentication import LiveUserJWTAuth
from vocabulary.api import admin_vocabulary, mobile_vocabulary
from mvp.api import mvp
from mvp.portal_api import portal
from billing.api import mobile as billing_mobile, web as billing_web

api = NinjaAPI(title="DualSign API", version="0.1.0")


@api.get("/health")
def health(request):
    return {"status": "ok"}


api.add_router("/web", web)
api.add_router("/web", session)
api.add_router("/mobile", mobile)
api.add_router("/mobile", protected)
api.add_router("/institutions", institutions, auth=LiveUserJWTAuth())
api.add_router("/vocabulary", admin_vocabulary)
api.add_router("/mobile/vocabulary", mobile_vocabulary)
api.add_router("/mobile/mvp", mvp)
api.add_router("/portal", portal)
api.add_router("/mobile/billing", billing_mobile)
api.add_router("/billing", billing_web)
