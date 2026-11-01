"""Defaults for new records only; no currency conversion or historical rewrites."""

from app.models import InstanceSettings

# All selectable currencies use two decimal places, matching the accounting model.
SUPPORTED_CURRENCIES = tuple(
    "AED AUD BRL CAD CHF CNY CZK DKK EUR GBP HKD HUF ILS INR MXN NOK NZD PLN RON SEK SGD TRY USD ZAR".split()
)


def default_currency(session):
    settings = session.get(InstanceSettings, 1)
    return settings.default_currency if settings else "EUR"


def public_settings(session):
    return {
        "default_currency": default_currency(session),
        "supported_currencies": list(SUPPORTED_CURRENCIES),
        "supported_languages": ["en", "it"],
    }


def apply_currency_default(session, data):
    # fields_set distinguishes omitted currency from an explicit legacy-client EUR.
    if "currency" not in data.model_fields_set:
        data.currency = default_currency(session)
    return data
