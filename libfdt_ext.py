# SPDX-License-Identifier: GPL-2.0-only
from typing import Optional, Iterator

import libfdt
from libfdt import FDT_ERR_NOTFOUND, Property

from helpers import DtNode


def fdt_subnodes(self: libfdt.FdtRo, parent: DtNode) -> Iterator[DtNode]:
    offset = self.first_subnode(parent, [FDT_ERR_NOTFOUND])
    while offset != -FDT_ERR_NOTFOUND:
        yield offset
        offset = self.next_subnode(offset, [FDT_ERR_NOTFOUND])


libfdt.FdtRo.subnodes = fdt_subnodes


def fdt_getprop_or_none(self: libfdt.FdtRo, nodeoffset, prop_name) -> Optional[Property]:
    prop = self.getprop(nodeoffset, prop_name, [FDT_ERR_NOTFOUND])
    if prop == -FDT_ERR_NOTFOUND:
        return None
    return prop


libfdt.FdtRo.getprop_or_none = fdt_getprop_or_none
