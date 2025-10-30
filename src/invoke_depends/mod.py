# SPDX-License-Identifier: MIT-0
from __future__ import annotations

import functools
import itertools
import pathlib
import string
import typing as t

from . import path_mtime, arg_templates, fingerprint
from .typing import FlattenablePaths


def _flatten(items: FlattenablePaths) -> list[pathlib.Path]:
    """Flatten nested sequences of paths and strings into a single list."""
    return [
        p
        for p in itertools.chain.from_iterable(
            item if isinstance(item, (list, tuple, set)) else [item] for item in items
        )
    ]


def _should_run(
    fp: str, inps: list[pathlib.Path], outs: list[pathlib.Path]
) -> tuple[bool, str]:
    # no outputs -> always run, nothing to check.
    if not outs:
        return True, "no outputs given"

    for dst in outs:
        # Missing output -> must rebuild.
        if not dst.exists():
            return True, f"{dst}: missing file"

        # If any input is newer than this output -> trigger rebuild.
        newer_src = next((src for src in inps if path_mtime.is_newer(src, dst)), None)
        if newer_src:
            return True, f"{dst}: older than {newer_src}"

        # If the argument fingerprint has changed -> trigger rebuild.
        if fingerprint.read(dst) != fp:
            return True, f"{dst}: context changed"

    return False, "up to date"


P = t.ParamSpec("P")
R = t.TypeVar("R")


class Depends(t.Generic[P, R]):
    """Skip a task if all `outs` exist and are newer than every `inps`."""

    def __init__(
        self,
        body: t.Callable[P, R],
        *,
        inps: FlattenablePaths,
        outs: FlattenablePaths,
        touch_files: bool = False,
        verbose: bool = False,
        echo_format: str = "[depends] ${func_name} -> ${reason}",
    ) -> None:
        self.body = body

        self.inp_files = _flatten(inps)
        self.out_files = _flatten(outs)
        self.touch_outputs = touch_files
        self.verbose = verbose
        self.echo_template = string.Template(echo_format)

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
        inps = arg_templates.expand(self.inp_files, args, kwargs, self.body)
        outs = arg_templates.expand(self.out_files, args, kwargs, self.body)

        fp = fingerprint.make(args, kwargs)

        should_run, reason = _should_run(fp, inps, outs)
        self._report_reason(reason)
        if not should_run:
            return None

        result = self.body(*args, **kwargs)

        for dst in outs:
            path_mtime.invalidate(dst)

            fingerprint.write(dst, fp)

            if self.touch_outputs:
                dst.touch()

        return result


def on(
    *,
    inps: FlattenablePaths,
    outs: FlattenablePaths,
    touch_outputs: bool = False,
    verbose: bool = False,
    echo_format: str = "[depends] ${func_name} -> ${reason}",
    klass: type[Depends[P, R]] = Depends,
) -> t.Callable[[t.Callable[P, R]], t.Callable[P, t.Optional[R]]]:
    """Dependency-aware decorator for Invoke tasks or plain functions."""

    def decorator(fn: t.Callable[P, R]) -> t.Callable[P, t.Optional[R]]:
        depends = klass(
            fn,
            inps=inps,
            outs=outs,
            touch_files=touch_outputs,
            verbose=verbose,
            echo_format=echo_format,
        )

        @functools.wraps(fn)
        def wrapper(*a: P.args, **kw: P.kwargs) -> t.Optional[R]:
            return depends.call(*a, **kw)

        return wrapper

    return decorator
