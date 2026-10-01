from datetime import datetime

from ninja import Schema


class CredentialsIn(Schema):
    email: str
    password: str


class RegistrationIn(Schema):
    email: str
    password: str
    password_confirmation: str


class RefreshIn(Schema):
    refresh: str


class InstitutionIn(Schema):
    name: str


class UserOut(Schema):
    id: int
    email: str
    is_staff: bool
    is_superuser: bool


class MembershipOut(Schema):
    institution_id: int
    institution_name: str
    role: str


class AccessEntitlementOut(Schema):
    origin: str
    capabilities: dict[str, bool]


class InstitutionOut(Schema):
    id: int
    name: str


class ConsentIn(Schema):
    purpose: str
    policy_version: str
    action: str


class ConsentOut(Schema):
    id: int
    purpose: str
    policy_version: str
    action: str
    recorded_at: datetime
