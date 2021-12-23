# SPDX-License-Identifier: GPL-2.0-only
from typing import List

from libfdt import FdtRo

import interconnect_gen_ids

DtNode = int
Phandle = int


def get_cell_id_name(cell_id: int, soc_model: str, soc_prefix: bool) -> str:
    name = interconnect_gen_ids.bus_ids[cell_id]
    return name.replace("MSM_BUS_", f"{soc_model.upper()}_" if soc_prefix else "")


def find_subnodes_referencing_phandle(fdt: FdtRo, bus_node: DtNode,
                                      phandle: Phandle, prop_name: str) -> List[DtNode]:
    nodes = []

    for node in fdt.subnodes(bus_node):
        prop = fdt.getprop_or_none(node, prop_name)
        if prop is None:
            continue
        values = prop.as_uint32_array()
        if phandle in values:
            nodes.append(node)

    return nodes
