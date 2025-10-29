# SPDX-License-Identifier: MIT-0
from __future__ import annotations

import inspect
import pathlib
import string
import typing as t

from .typing import PathishSeq


def expand(
    templates: PathishSeq,
    args: tuple,
    kwargs: dict,
    fn: t.Callable[..., t.Any],
) -> list[pathlib.Path]:
    """Expand ${var} placeholders in strings using function arguments."""
    sig = inspect.signature(fn)
    bound = sig.bind_partial(*args, **kwargs)
    bound.apply_defaults()

    context = {k: str(v) for k, v in bound.arguments.items()}

    paths: list[pathlib.Path] = []
    for raw in templates:
        if isinstance(raw, pathlib.Path):
            paths.append(raw)
        else:
            expanded = string.Template(str(raw)).safe_substitute(context)
            paths.append(pathlib.Path(expanded))
    return paths
