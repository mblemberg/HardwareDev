"""Content-addressed local cache for DAG node results (design doc section 8).

Cache layout:
    <cache_dir>/
      <hash>.pkl    # one file per cached value

Files are pickle-serialized framework objects (typically a ``Quantity``).
Writes are atomic: write to a sibling ``.tmp`` then rename. Reads validate a
magic-bytes header so a corrupted or alien file is ignored rather than
crashing the loader.

Pickle is used here for value storage on the assumption the cache is local
and trusted. A future remote / shared-cache phase (design doc section 8
"phase 2") will want a safer format; the read/write API doesn't change.
"""
from __future__ import annotations

import logging
import os
import pickle
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_MAGIC = b"HW_ANALYSIS_CACHE_V1\n"


class Cache:
    """A directory-backed key/value store keyed by hex hash strings."""

    def __init__(self, cache_dir: Path | str) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: str) -> Path:
        return self.cache_dir / f"{key}.pkl"

    def get(self, key: str) -> Any | None:
        """Return the cached value for ``key`` or ``None`` if missing/corrupt."""
        path = self._path_for(key)
        if not path.is_file():
            return None
        try:
            with path.open("rb") as f:
                header = f.read(len(_MAGIC))
                if header != _MAGIC:
                    logger.warning("cache file %s has unexpected header; ignoring", path)
                    return None
                return pickle.load(f)
        except (pickle.UnpicklingError, EOFError, ValueError) as e:
            logger.warning("cache file %s could not be deserialized (%s); ignoring", path, e)
            return None

    def put(self, key: str, value: Any) -> None:
        """Atomically write ``value`` under ``key``. Best-effort; logs on failure."""
        path = self._path_for(key)
        try:
            # Same-directory tmp file so the final os.replace is atomic on Windows too.
            fd, tmp_name = tempfile.mkstemp(
                dir=str(self.cache_dir), prefix=".cache_", suffix=".tmp"
            )
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(_MAGIC)
                    pickle.dump(value, f, protocol=pickle.HIGHEST_PROTOCOL)
                os.replace(tmp_name, path)
            except Exception:
                # Clean up the temp file if anything went wrong before rename.
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
                raise
        except (pickle.PicklingError, OSError, TypeError) as e:
            logger.warning("could not write cache entry %s (%s); cache is best-effort", path, e)

    def clear(self) -> None:
        """Remove every entry. The cache directory itself stays."""
        for f in self.cache_dir.glob("*.pkl"):
            try:
                f.unlink()
            except OSError:
                pass

    def __len__(self) -> int:
        return sum(1 for _ in self.cache_dir.glob("*.pkl"))


__all__ = ["Cache"]
