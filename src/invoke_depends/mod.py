# SPDX-License-Identifier: MIT-0
from __future__ import annotations

import functools
import itertools
import pathlib
import string
import typing as t

import cachetools

Pathish = str | pathlib.Path
PathishSeq = t.Sequence[Pathish]
FlattenablePaths = t.Sequence[t.Union[Pathish, PathishSeq]]


@cachetools.cached(cache={})
def _path_mtime(path: pathlib.Path) -> int:
    return path.stat().st_mtime_ns


def _path_mtime_invalidate(path: pathlib.Path) -> None:
    """Invalidate the cached mtime for a given path."""
    _path_mtime.cache.pop(path, None)


def _is_newer(src: pathlib.Path, dst: pathlib.Path) -> bool:
    """Check if src is newer than dst."""
    return _path_mtime(src) > _path_mtime(dst)


def _resolve(items: FlattenablePaths) -> list[pathlib.Path]:
    """Convert raw file paths to Path objects (flatten nested sequences)."""
    return [
        pathlib.Path(p)
        for p in itertools.chain.from_iterable(
            item if isinstance(item, (list, tuple, set)) else [item] for item in items
        )
    ]


P = t.ParamSpec("P")
R = t.TypeVar("R")


class Depends(t.Generic[P, R]):
    """Skip a task if all `creates` exist and are newer than every `on`."""

    def __init__(
        self,
        body: t.Callable[P, R],
        *,
        deps: FlattenablePaths,
        creates: FlattenablePaths,
        touch_files: bool = False,
        verbose: bool = False,
        echo_format: str = "[depends] ${func_name} -> ${reason}",
    ) -> None:
        self.body = body

        self.dep_files = _resolve(deps)
        self.create_files = _resolve(creates)
        self.touch_files = touch_files
        self.verbose = verbose
        self.echo_template = string.Template(echo_format)

    def _should_run(self) -> tuple[bool, str]:
        if not self.dep_files:
            return True, f"no source files given"
        if not self.create_files:
            return True, f"no target files given"

        for src in self.dep_files:
            for dst in self.create_files:
                if not dst.exists():
                    return True, f"target missing ({dst})"
                if _is_newer(src, dst):
                    return True, f"{src} newer than {dst}"

        return False, "up to date"

    def _report_reason(self, reason: str) -> None:
        if not self.verbose:
            return

        out = self.echo_template.safe_substitute(
            dict(
                reason=reason,
                func_name=self.body.__name__,
            )
        )

        print(out, flush=True)

    def call(self, *args: P.args, **kwargs: P.kwargs) -> t.Optional[R]:
        should_run, reason = self._should_run()
        self._report_reason(reason)
        if not should_run:
            return None

        result = self.body(*args, **kwargs)

        for dst in self.create_files:
            _path_mtime_invalidate(dst)
            if self.touch_files:
                dst.touch()

        return result


def on(
    *,
    deps: FlattenablePaths,
    creates: FlattenablePaths,
    touch_files: bool = False,
    verbose: bool = False,
    echo_format: str = "[depends] ${func_name} -> ${reason}",
    klass: type[Depends[P, R]] = Depends,
) -> t.Callable[[t.Callable[P, R]], t.Callable[P, t.Optional[R]]]:
    """Dependency-aware decorator for Invoke tasks or plain functions."""

    def decorator(fn: t.Callable[P, R]) -> t.Callable[P, t.Optional[R]]:
        depends = klass(
            fn,
            deps=deps,
            creates=creates,
            touch_files=touch_files,
            verbose=verbose,
            echo_format=echo_format,
        )

        @functools.wraps(fn)
        def wrapper(*a: P.args, **kw: P.kwargs) -> t.Optional[R]:
            return depends.call(*a, **kw)

        return wrapper

    return decorator
