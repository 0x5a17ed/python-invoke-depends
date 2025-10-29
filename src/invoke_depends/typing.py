# SPDX-License-Identifier: MIT-0
from __future__ import annotations

import pathlib
import typing as t

Pathish = str | pathlib.Path
PathishSeq = t.Sequence[Pathish]
FlattenablePaths = t.Sequence[t.Union[Pathish, PathishSeq]]
