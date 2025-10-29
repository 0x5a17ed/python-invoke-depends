# SPDX-License-Identifier: MIT-0
from __future__ import annotations
import functools
import itertools
import string
import pathlib
import typing as t

import cachetools


@cachetools.cached(cache={})
def _path_mtime(path: pathlib.Path) -> int:
    return path.stat().st_mtime_ns


def _path_mtime_invalidate(path: pathlib.Path) -> None:
    """Invalidate the cached mtime for a given path."""
    _path_mtime.cache.pop(path, None)


def _is_newer(src: pathlib.Path, dst: pathlib.Path) -> bool:
    """Check if src is newer than dst."""
    return _path_mtime(src) > _path_mtime(dst)


def _resolve(items: t.Sequence[t.Union[str, t.Sequence[str]]]) -> list[pathlib.Path]:
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
        deps: t.Sequence[t.Union[str, t.Sequence[str]]],
        creates: t.Sequence[t.Union[str, t.Sequence[str]]],
        touch_files: bool = False,
        verbose: bool = False,
        echo_format: str = "[depends] ${func_name} -> ${reason}",
    ) -> None:
        self.body = body
        functools.update_wrapper(self, self.body)

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

    def __getattr__(self, name: str) -> t.Any:
        """Delegate unknown attributes to the underlying function."""
        return getattr(self.body, name)

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> t.Optional[R]:
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


def on(*args: t.Any, **kwargs: t.Any) -> t.Callable[..., Depends]:
    klass: type[Depends] = kwargs.pop("klass", Depends)

    # @decorator used directly
    if len(args) == 1 and callable(args[0]) and not isinstance(args[0], Depends):
        return klass(args[0], **kwargs)

    # @decorator(...)
    def inner(func: t.Callable[P, R]) -> Depends[P, R]:
        return klass(func, **kwargs)

    return inner
