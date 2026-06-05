"""Persistence helpers for VectorStore."""

from __future__ import annotations

import os
import pickle
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from src.core.vector_store_models import MemoryDocument


def get_vector_persist_directory(settings: Any) -> str:
    """Get the FAISS persist directory from dict or settings object."""
    vector_config = settings.database.vector

    if isinstance(vector_config, dict):
        faiss_config = vector_config.get("faiss")
        if isinstance(faiss_config, dict):
            return faiss_config.get(
                "persist_directory",
                vector_config.get("persist_directory", "./data/faiss"),
            )
        return vector_config.get("persist_directory", "./data/faiss")

    faiss_config = getattr(vector_config, "faiss", None)
    if faiss_config is not None:
        persist_directory = getattr(faiss_config, "persist_directory", None)
        if persist_directory:
            return persist_directory

    persist_directory = getattr(vector_config, "persist_directory", None)
    if persist_directory:
        return persist_directory

    return "./data/faiss"


def get_paths(settings: Any) -> tuple[Path, Path]:
    """Resolve the index and metadata payload paths."""
    persist_dir = Path(get_vector_persist_directory(settings))
    persist_dir.mkdir(parents=True, exist_ok=True)
    return persist_dir / "index.faiss", persist_dir / "documents.pkl"


def fsync_file(path: Path) -> None:
    """Flush file contents to disk when possible."""
    with open(path, "rb") as file_handle:
        os.fsync(file_handle.fileno())


def fsync_directory(path: Path) -> None:
    """Flush directory metadata so completed atomic replacements survive crashes."""
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        directory_fd = os.open(path, directory_flags)
    except OSError:
        return
    try:
        os.fsync(directory_fd)
    except OSError:
        pass
    finally:
        os.close(directory_fd)


def save_documents_payload(
    path: Path,
    *,
    documents: Dict[str, MemoryDocument],
    id_to_idx: Dict[str, int],
    idx_to_id: Dict[int, str],
    next_vector_id: int,
) -> None:
    """Persist document metadata to a temporary file."""
    with open(path, "wb") as file_handle:
        pickle.dump(
            {
                "documents": documents,
                "id_to_idx": id_to_idx,
                "idx_to_id": idx_to_id,
                "next_vector_id": next_vector_id,
            },
            file_handle,
        )
        file_handle.flush()
        os.fsync(file_handle.fileno())


def save_index_state(
    *,
    faiss_module: Any,
    index: Any,
    index_path: Path,
    docs_path: Path,
    documents: Dict[str, MemoryDocument],
    id_to_idx: Dict[str, int],
    idx_to_id: Dict[int, str],
    next_vector_id: int,
    save_documents_payload_fn: Callable[[Path], None],
    fsync_file_fn: Callable[[Path], None],
    fsync_directory_fn: Callable[[Path], None],
) -> None:
    """Save the FAISS index and document metadata using atomic file replacement."""
    temp_suffix = f".{uuid.uuid4().hex}.tmp"
    temp_index_path = index_path.with_name(f"{index_path.name}{temp_suffix}")
    temp_docs_path = docs_path.with_name(f"{docs_path.name}{temp_suffix}")

    try:
        faiss_module.write_index(index, str(temp_index_path))
        fsync_file_fn(temp_index_path)
        save_documents_payload_fn(temp_docs_path)

        os.replace(temp_index_path, index_path)
        os.replace(temp_docs_path, docs_path)
        fsync_directory_fn(index_path.parent)
    finally:
        temp_index_path.unlink(missing_ok=True)
        temp_docs_path.unlink(missing_ok=True)


def load_persisted_state(
    *,
    faiss_module: Any,
    index_path: Path,
    docs_path: Path,
    logger: Any,
) -> Dict[str, Any]:
    """Load persisted FAISS state and metadata payloads."""
    state = {
        "index": None,
        "documents": {},
        "id_to_idx": {},
        "idx_to_id": {},
        "next_vector_id": 1,
        "loaded_index_dimension": None,
        "documents_load_failed": False,
    }

    if index_path.exists():
        try:
            state["index"] = faiss_module.read_index(str(index_path))
            state["loaded_index_dimension"] = getattr(state["index"], "d", None)
        except Exception as exc:
            logger.warning(
                "Failed to load FAISS index from %s: %s",
                index_path,
                exc,
            )

    if docs_path.exists():
        try:
            with open(docs_path, "rb") as file_handle:
                data = pickle.load(file_handle)
                state["documents"] = data.get("documents", {})
                state["id_to_idx"] = data.get("id_to_idx", {})
                state["idx_to_id"] = data.get("idx_to_id", {})
                state["next_vector_id"] = data.get(
                    "next_vector_id",
                    max(state["idx_to_id"].keys(), default=0) + 1,
                )
        except Exception as exc:
            state["documents_load_failed"] = True
            logger.warning(
                "Failed to load vector store documents from %s: %s. Falling back to an empty in-memory state.",
                docs_path,
                exc,
            )
            state["documents"] = {}
            state["id_to_idx"] = {}
            state["idx_to_id"] = {}
            state["next_vector_id"] = 1

    return state
