from .models import Institution, Membership


def is_platform_admin(user):
    return bool(user and user.is_authenticated and user.is_active and user.is_superuser and user.is_staff)


def active_memberships(user):
    if not user or not user.is_authenticated or not user.is_active:
        return Membership.objects.none()
    return Membership.objects.filter(user=user, is_active=True, institution__is_active=True).select_related("institution")


def can_view_institution(user, institution_id):
    if is_platform_admin(user):
        return Institution.objects.filter(pk=institution_id).first()
    membership = active_memberships(user).filter(institution_id=institution_id).first()
    return membership.institution if membership else None


def can_create_institution(user):
    return is_platform_admin(user)
