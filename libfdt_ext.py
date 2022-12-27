# SPDX-License-Identifier: GPL-2.0-only
import struct
from typing import List, Any, Optional, Iterator

import libfdt
from libfdt import FDT_ERR_NOTFOUND, Property

from helpers import DtNode


def fdt_subnodes(self: libfdt.FdtRo, parent: DtNode) -> Iterator[DtNode]:
    offset = self.first_subnode(parent, [FDT_ERR_NOTFOUND])
    while offset != -FDT_ERR_NOTFOUND:
        yield offset
        offset = self.next_subnode(offset, [FDT_ERR_NOTFOUND])


libfdt.FdtRo.subnodes = fdt_subnodes

# not pretty extensions
def fdt_as_array(self: libfdt.Property, fmt: str) -> List[Any]:
    unpack_iter = struct.iter_unpack('>' + fmt, self)
    ret = []
    for val in unpack_iter:
        ret.append(val[0])
    return ret


def fdt_as_int32_array(self: libfdt.Property) -> List[int]:
    return self.as_array('l')


def fdt_as_uint32_array(self: libfdt.Property) -> List[int]:
    return self.as_array('L')


def fdt_as_stringlist(self: libfdt.Property) -> List[str]:
    if self[-1] != 0:
        raise ValueError('Property lacks nul termination')
    parts = self[:-1].split(b'\x00')
    return list(map(lambda x: x.decode('utf-8'), parts))

def fdt_getprop_or_none(self: libfdt.FdtRo, nodeoffset, prop_name) -> Optional[Property]:
    prop = self.getprop(nodeoffset, prop_name, [FDT_ERR_NOTFOUND])
    if prop == -FDT_ERR_NOTFOUND:
        return None
    return prop


libfdt.Property.as_array = fdt_as_array
libfdt.Property.as_int32_array = fdt_as_int32_array
libfdt.Property.as_uint32_array = fdt_as_uint32_array
libfdt.Property.as_stringlist = fdt_as_stringlist
libfdt.FdtRo.getprop_or_none = fdt_getprop_or_none
