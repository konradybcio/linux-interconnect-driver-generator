# SPDX-License-Identifier: GPL-2.0-only
import math
from typing import List

from libfdt import FdtRo

import interconnect_gen_ids

DtNode = int
Phandle = int

TAB_SIZE = 8


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


def pad_with_tabs(string: str, suffix: str, num_tabs: int) -> str:
    """
    Pad a given string with enough tabs to match the size of num_tabs, but at least one tab.
    Appends the suffix after the tabs.
    """
    remaining_size = num_tabs * TAB_SIZE - len(string)
    num_tabs = math.ceil(remaining_size / TAB_SIZE)
    return string + "\t" * max(num_tabs, 1) + suffix
