# SPDX-License-Identifier: GPL-2.0-only
from dataclasses import dataclass
from typing import TextIO


@dataclass(init=False)
class Options:
    soc_model: str
    dtb: TextIO
