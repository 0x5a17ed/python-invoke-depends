# SPDX-License-Identifier: MIT-0
from __future__ import annotations

import pathlib
import typing as t
import cachetools

_cache: t.MutableMapping[pathlib.Path, int | None] = {}


@t.overload
def get(path: pathlib.Path, raising: t.Literal[True] = True) -> int: ...
@t.overload
def get(path: pathlib.Path, raising: t.Literal[False]) -> int | None: ...
@cachetools.cached(cache=_cache, key=lambda path, raising=True: path)
def get(path: pathlib.Path, raising: bool = True) -> int | None:
    try:
        st = path.stat()
    except FileNotFoundError:
        if raising:
            raise
        return None
    return st.st_mtime_ns


def invalidate(path: pathlib.Path) -> None:
    """Invalidate the cached mtime for a given path."""
    _cache.pop(path, None)


def is_newer(src: pathlib.Path, dst: pathlib.Path) -> bool:
    """Check if src is newer than dst."""
    return get(src) > get(dst)
