import logging
import threading
from typing import Generic, TypeVar, final

logger = logging.getLogger(__name__)


class RegistryError(Exception): ...


@final
class KeyNotFoundError(RegistryError):
    def __init__(self, key: str, available_keys: list[str]) -> None:
        super().__init__(f"Key '{key}' not found. Available keys: {available_keys}")
        self.key = key


@final
class DuplicateKeyError(RegistryError):
    def __init__(self, key: str) -> None:
        super().__init__(f"Key '{key}' is already registered.")
        self.key = key


T = TypeVar('T')


@final
class Registry(Generic[T]):
    """https://martinfowler.com/eaaCatalog/registry.html"""

    def __init__(self, allow_override: bool = False) -> None:
        self._store: dict[str, T] = {}
        self._lock = threading.RLock()
        self._allow_override = allow_override

    def register(self, key: str, value: T) -> None:
        with self._lock:
            if key in self._store:
                if self._allow_override:
                    logger.warning("Overriding registry key: %s", key)
                else:
                    raise DuplicateKeyError(key)
            
            self._store[key] = value
            logger.debug("Registered key: %s", key)

    def get(self, key: str) -> T:
        with self._lock:
            try:
                return self._store[key]
            except KeyError:
                raise KeyNotFoundError(key, list(self._store.keys()))

    def get_or_default(self, key: str, default: T) -> T:
        with self._lock:
            return self._store.get(key, default)

    def has(self, key: str) -> bool:
        with self._lock:
            return key in self._store

    def keys(self) -> list[str]:
        with self._lock:
            return list(self._store.keys())

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            logger.info("Registry cleared")

    def register_decorator(self, key: str):
        """
        Usage:
            @registry.register_decorator('my_key')
            class MyClass: ...
        """
        def decorator(value: T) -> T:
            self.register(key, value)
            return value
        return decorator


################################################################################
from abc import ABC, abstractmethod
from dataclasses import dataclass

class PaymentProvider(ABC):
    @abstractmethod
    def charge(self, amount: float) -> bool:
        pass

@dataclass
class StripeProvider(PaymentProvider):
    api_key: str = "__CHANGEME__"
    
    def charge(self, amount: float) -> bool:
        print(f"Charging ${amount} via Stripe")
        return True

@dataclass
class PayPalProvider(PaymentProvider):
    client_id: str = "__CHANGEME__"
    
    def charge(self, amount: float) -> bool:
        print(f"Charging ${amount} via PayPal")
        return True


################################################################################
payment_registry = Registry[PaymentProvider](allow_override=False)

payment_registry.register('stripe', StripeProvider())
payment_registry.register('paypal', PayPalProvider())
# Or @payment_registry.register_decorator('crypto')


class PaymentService:
    def __init__(self, registry: Registry[PaymentProvider]):
        self._registry = registry

    def process_payment(self, provider_name: str, amount: float) -> bool:
        try:
            provider = self._registry.get(provider_name)
            return provider.charge(amount)
        except KeyNotFoundError as e:
            logger.error("Payment failed: %s", e)
            raise ValueError(f"Unsupported payment provider: {provider_name}")


if __name__ == "__main__":
    service = PaymentService(payment_registry)
    
    service.process_payment('stripe', 100.0)
    
    try:
        service.process_payment('bitcoin', 100.0)
    except ValueError:
        print("Handled unsupported provider gracefully")