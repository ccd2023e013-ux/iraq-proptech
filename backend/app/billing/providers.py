"""Payment-provider abstraction.

* ``demo`` (default outside production): an in-app simulated checkout. No money
  moves; every payment is flagged ``is_demo`` and the UI says so.
* ``none``: billing disabled (the production default until a real provider is
  configured).
* Real Iraqi/regional gateways (e.g. ZainCash, FIB, Qi Card, international
  cards) are FUTURE INTEGRATIONS that REQUIRE MERCHANT CREDENTIALS. They plug
  in by implementing :class:`PaymentProvider` — create a hosted checkout and
  verify signed callbacks — without touching the rest of billing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.core.config import get_settings


@dataclass(frozen=True)
class Checkout:
    provider_ref: str | None
    redirect_url: str  # where the browser goes to pay


@dataclass(frozen=True)
class CallbackResult:
    provider_ref: str
    succeeded: bool
    reason: str | None = None


class PaymentProvider(Protocol):
    name: str
    is_demo: bool

    def create_checkout(self, payment_id: str, amount: str, currency: str) -> Checkout: ...

    def parse_callback(self, headers: dict[str, str], body: bytes) -> CallbackResult:
        """Verify the provider's signature and return the outcome (raise on bad input)."""
        ...

    def refund(self, provider_ref: str | None) -> None: ...


class BillingDisabledError(Exception):
    pass


class DemoPaymentProvider:
    name = "demo"
    is_demo = True

    def create_checkout(self, payment_id: str, amount: str, currency: str) -> Checkout:
        return Checkout(
            provider_ref=f"demo_{payment_id}", redirect_url=f"/billing/demo/{payment_id}"
        )

    def parse_callback(self, headers: dict[str, str], body: bytes) -> CallbackResult:
        raise BillingDisabledError("The demo provider has no callbacks")

    def refund(self, provider_ref: str | None) -> None:
        return None


def get_provider() -> PaymentProvider:
    provider = get_settings().effective_payment_provider
    if provider == "demo":
        return DemoPaymentProvider()
    raise BillingDisabledError("Payments are not enabled on this deployment")


def billing_enabled() -> bool:
    try:
        get_provider()
    except BillingDisabledError:
        return False
    return True
