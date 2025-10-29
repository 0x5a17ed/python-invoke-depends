# SPDX-License-Identifier: MIT-0
from __future__ import annotations

import os
import pathlib
import json
import hashlib

import invoke

XATTR_KEY = "user.depends.hash"


def make(args: tuple, kwargs: dict) -> str:
    """Return a hash fingerprint of args."""
    if args and isinstance(args[0], invoke.Context):
        args = args[1:]

    blob = json.dumps((args, kwargs)).encode()
    return hashlib.sha1(blob).hexdigest()


def get(path: pathlib.Path) -> str | None:
    try:
        return os.getxattr(path, XATTR_KEY, follow_symlinks=False).decode()
    except OSError:
        return None


def set(path: pathlib.Path, value: str) -> None:
    try:
        os.setxattr(path, XATTR_KEY, value.encode(), follow_symlinks=False)
    except OSError:
        pass
