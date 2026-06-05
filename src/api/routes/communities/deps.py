"""Runtime accessors for the communities route package."""

from importlib import import_module
from types import ModuleType
from typing import Any


def get_communities_module() -> ModuleType:
    """Load the package module so tests can patch its exported names."""
    return import_module("src.api.routes.communities")


def get_graph_store():
    """Return the package-exported graph store accessor."""
    return get_communities_module().get_graph_store()


def create_community_detector():
    """Instantiate the package-exported community detector."""
    return get_communities_module().CommunityDetector()


def create_hierarchy_builder():
    """Instantiate the package-exported hierarchy builder."""
    return get_communities_module().HierarchyBuilder()


def create_community_summarizer():
    """Instantiate the package-exported community summarizer."""
    return get_communities_module().CommunitySummarizer()


def get_uuid_module() -> Any:
    """Return the package-exported uuid module for patch compatibility."""
    return get_communities_module().uuid
