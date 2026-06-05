"""Runtime accessors for the collectors route package."""

from importlib import import_module
from types import ModuleType
from typing import Any


def get_collectors_module() -> ModuleType:
    """Load the package module so tests can patch its exported names."""
    return import_module("src.api.routes.collectors")


def get_unified_collector():
    """Return the package-exported unified collector accessor."""
    return get_collectors_module().get_unified_collector()


def get_settings():
    """Return the package-exported settings accessor."""
    return get_collectors_module().get_settings()


def parse_collector_type(raw_type: str):
    """Return the package-exported collector type parser."""
    return get_collectors_module()._parse_collector_type(raw_type)


def parse_collector_types(raw_types: list[str] | None):
    """Return the package-exported collector type list parser."""
    return get_collectors_module()._parse_collector_types(raw_types)


def require_registered_collector(raw_type: str):
    """Return the package-exported collector registration guard."""
    return get_collectors_module()._require_registered_collector(raw_type)


def require_runtime_component(component_name: str, missing_detail: str):
    """Return the package-exported runtime component guard."""
    return get_collectors_module()._require_runtime_component(component_name, missing_detail)


async def scan_directory(request: Any):
    """Call the package-exported scan_directory route function."""
    return await get_collectors_module().scan_directory(request)
