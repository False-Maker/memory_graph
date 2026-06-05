"""Runtime accessors for the data route package."""

from importlib import import_module
from types import ModuleType
from typing import Any


def get_data_module() -> ModuleType:
    """Load the package module so tests can patch its exported names."""
    return import_module("src.api.routes.data")


def get_vector_store():
    """Return the package-exported vector store accessor."""
    return get_data_module().get_vector_store()


def get_graph_store():
    """Return the package-exported graph store accessor."""
    return get_data_module().get_graph_store()


def get_memory_service():
    """Return the package-exported memory service accessor."""
    return get_data_module().get_memory_service()


def get_llm_manager():
    """Return the package-exported llm manager accessor."""
    return get_data_module().get_llm_manager()


def get_detector():
    """Return the package-exported detector accessor."""
    return get_data_module().get_detector()


async def batch_create_memories(memory_list: list[Any]):
    """Call the package-exported batch_create_memories route function."""
    return await get_data_module().batch_create_memories(memory_list)
