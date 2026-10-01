from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("An email address is required")
        user = self.model(email=self.normalize_email(email).lower(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if not extra_fields["is_staff"] or not extra_fields["is_superuser"]:
            raise ValueError("A platform administrator must be staff and superuser")
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email


class Institution(models.Model):
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Membership(models.Model):
    class Role(models.TextChoices):
        INSTITUTION_ADMIN = "institution_admin", "Institution administrator"
        OPERATOR = "operator", "Operator"
        VOCABULARY_REVIEWER = "vocabulary_reviewer", "Vocabulary reviewer"

    user = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="memberships")
    institution = models.ForeignKey(Institution, on_delete=models.PROTECT, related_name="memberships")
    role = models.CharField(max_length=32, choices=Role.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("user", "institution"), name="unique_user_institution_membership"),
            models.CheckConstraint(
                condition=models.Q(role__in=("institution_admin", "operator", "vocabulary_reviewer")),
                name="membership_role_valid",
            ),
        ]


class AccessEntitlement(models.Model):
    class Origin(models.TextChoices):
        FREE = "free", "Free"
        PLUS = "plus", "Plus"
        ENTERPRISE_ACCESS = "enterprise_access", "Enterprise access"

    user = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="access_entitlements")
    institution = models.ForeignKey("accounts.Institution", null=True, blank=True, on_delete=models.PROTECT, related_name="access_entitlements")
    origin = models.CharField(max_length=32, choices=Origin.choices, default=Origin.FREE)
    capabilities = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(models.Q(user__isnull=False, institution__isnull=True) | models.Q(user__isnull=True, institution__isnull=False)),
                name="access_entitlement_one_owner",
            ),
            models.UniqueConstraint(fields=("user",), condition=models.Q(user__isnull=False), name="unique_user_access_entitlement"),
            models.UniqueConstraint(fields=("institution",), condition=models.Q(institution__isnull=False), name="unique_institution_access_entitlement"),
            models.CheckConstraint(
                condition=models.Q(origin__in=("free", "plus", "enterprise_access")),
                name="access_entitlement_origin_valid",
            ),
        ]


class ConsentRecord(models.Model):
    class Action(models.TextChoices):
        GRANT = "grant", "Grant"
        WITHDRAW = "withdraw", "Withdraw"

    user = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="consent_records")
    purpose = models.CharField(max_length=100)
    policy_version = models.CharField(max_length=50)
    action = models.CharField(max_length=10, choices=Action.choices)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("recorded_at", "id")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Consent records are append-only")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Consent records are append-only")


class AuditRecord(models.Model):
    actor = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="audit_records")
    institution = models.ForeignKey(Institution, null=True, blank=True, on_delete=models.PROTECT, related_name="audit_records")
    event_type = models.CharField(max_length=100)
    subject_type = models.CharField(max_length=100, blank=True)
    subject_id = models.CharField(max_length=100, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("occurred_at", "id")

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Audit records are append-only")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Audit records are append-only")
