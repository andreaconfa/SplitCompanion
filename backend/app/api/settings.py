from fastapi import APIRouter
from pydantic import field_validator
from app.auth import Admin, DB
from app.models import InstanceSettings
from app.schemas import Input
from app.services.instance_settings import SUPPORTED_CURRENCIES, public_settings

router = APIRouter(prefix="/api/admin/settings")


class SettingsUpdate(Input):
    default_currency: str

    @field_validator("default_currency")
    @classmethod
    def supported_currency(cls, value):
        if value not in SUPPORTED_CURRENCIES:
            raise ValueError("Unsupported default currency.")
        return value


@router.get("")
def read_settings(admin: Admin, s: DB):
    return public_settings(s)


@router.patch("")
def update_settings(data: SettingsUpdate, admin: Admin, s: DB):
    settings = s.get(InstanceSettings, 1) or InstanceSettings()
    settings.default_currency = data.default_currency
    s.add(settings)
    s.flush()
    return public_settings(s)
