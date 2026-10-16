"""Check registry. A check is a function (CheckContext) -> CheckResult, registered by name."""
from typing import Callable

REGISTRY: dict = {}


def register(name: str):
    def deco(fn: Callable):
        REGISTRY[name] = fn
        return fn
    return deco


def get(name: str):
    return REGISTRY.get(name)
