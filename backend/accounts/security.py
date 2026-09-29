from ninja.errors import HttpError
from ninja.utils import check_csrf


def require_csrf(request):
    if check_csrf(request):
        raise HttpError(403, "CSRF check failed")
