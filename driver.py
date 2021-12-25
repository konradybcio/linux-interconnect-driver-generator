# SPDX-License-Identifier: GPL-2.0-only
from typing import List, Tuple

from libfdt import FdtRo

import generator
import helpers
from helpers import DtNode


def handle_qnode(fdt: FdtRo, node: DtNode, soc_model: str) -> str:
    """
    Transform all mas-* and srv-* nodes into DEFINE_QNODE macro
    """
    name = fdt.get_name(node)

    cell_id = fdt.getprop(node, "cell-id").as_uint32()
    agg_ports = fdt.getprop(node, "qcom,agg-ports").as_uint32()
    buswidth = fdt.getprop(node, "qcom,buswidth").as_uint32()
    connections_prop = fdt.getprop_or_none(node, "qcom,connections")
    if connections_prop is None:
        connections = []
    else:
        connections = connections_prop.as_uint32_array()

    # if connections is None:
    #     print(f"WARN: ignoring node {name}")
    #     continue

    conn_cell_id_names = []
    for connection in connections:
        conn_node = fdt.node_offset_by_phandle(connection)
        # print(fdt.get_name(conn_node))
        conn_cell_id = fdt.getprop(conn_node, "cell-id").as_uint32()
        conn_cell_id_names.append(helpers.get_cell_id_name(conn_cell_id, soc_model, True))

    qnode_name = name[4:].replace("-", "_")
    cell_id_name = helpers.get_cell_id_name(cell_id, soc_model, True)

    if len(conn_cell_id_names) > 0:
        links_str = ", " + ', '.join(conn_cell_id_names)
    else:
        links_str = ""
    return f"DEFINE_QNODE({qnode_name}, {cell_id_name}, {agg_ports}, {buswidth}{links_str});\n"


def handle_bcm(fdt: FdtRo, bus_node: DtNode, node: DtNode) -> str:
    """
    Transform all bcm-* nodes into DEFINE_QBCM macro
    """
    name = fdt.get_name(node)
    bcm_name = fdt.getprop(node, "qcom,bcm-name").as_str()

    name2 = name.replace("-", "_")
    # print(name2)

    bcm_phandle = fdt.get_phandle(node)
    # print(bcm_phandle)

    ref_nodes = helpers.find_subnodes_referencing_phandle(fdt, bus_node, bcm_phandle, "qcom,bcms")
    ref_node_names = list(map(lambda x: fdt.get_name(x)[4:].replace("-", "_"), ref_nodes))
    # print(f"Got something: &{', &'.join(ref_nodes)}")

    keep_alive = "false"  # FIXME

    if len(ref_nodes) == 0:
        print(f"WARN: ignoring BCM {name2}")
        return ""

    return f"DEFINE_QBCM({name2}, \"{bcm_name}\", {keep_alive}, &{', &'.join(ref_node_names)});\n"


def handle_fab(fdt: FdtRo, bus_node: DtNode, node: DtNode, soc_model: str) -> Tuple[str, List[str]]:
    """
    From all nodes that have e.g. qcom,bus-dev = <&fab_aggre1_noc>; get a set
    of qcom,bcms values and print as struct qcom_icc_bcm

    and more...
    """
    s = ""
    name = fdt.get_name(node)[4:]

    if name.endswith("_display"):
        print(f"WARN: ignoring FAB {name}")
        return "", []

    s += f"static struct qcom_icc_bcm *{name}_bcms[] = {{\n"
    phandle = fdt.get_phandle(node)
    ref_nodes = helpers.find_subnodes_referencing_phandle(fdt, bus_node, phandle, "qcom,bus-dev")

    bcms_set = set()
    for node in ref_nodes:
        bcms_prop = fdt.getprop_or_none(node, "qcom,bcms")
        bcms = []
        if bcms_prop is not None:
            bcms = bcms_prop.as_uint32_array()
        for bcm in bcms:
            bcms_set.add(bcm)

    # print(bcms_set)

    # get names for BCMs
    bcm_names = []
    for bcm in bcms_set:
        bcm_node = fdt.node_offset_by_phandle(bcm)
        bcm_name = fdt.get_name(bcm_node).replace("-", "_")
        bcm_names.append(bcm_name)

    for bcm_name in sorted(bcm_names):
        s += f"\t&{bcm_name},\n"

    s += f'''\
}};

static struct qcom_icc_node *{name}_nodes[] = {{
'''

    icc_node_list = []
    for node in ref_nodes:
        cell_id = fdt.getprop(node, "cell-id").as_int32()
        idx = helpers.get_cell_id_name(cell_id, soc_model, False)

        node_name = fdt.get_name(node)
        qnode_name = node_name[4:].replace("-", "_")

        s += f"\t[{idx}] = &{qnode_name},\n"
        icc_node_list.append(idx)

    s += f'''\
}};

static struct qcom_icc_desc {soc_model}_{name} = {{
\t.nodes = {name}_nodes,
\t.num_nodes = ARRAY_SIZE({name}_nodes),
\t.bcms = {name}_bcms,
\t.num_bcms = ARRAY_SIZE({name}_bcms),
}};

'''

    return s, icc_node_list


def generate_bcms(fdt: FdtRo, bus_node: DtNode) -> str:
    s = ""
    for node in fdt.subnodes(bus_node):
        name = fdt.get_name(node)
        if name.startswith("bcm-"):
            s += handle_bcm(fdt, bus_node, node)
    return s


def generate_fabs(fdt: FdtRo, bus_node: DtNode, soc_model: str) -> Tuple[str, List[List[str]]]:
    s = ""
    all_icc_nodes = []
    for node in fdt.subnodes(bus_node):
        name = fdt.get_name(node)
        if name.startswith("fab-"):
            fab_str, icc_nodes = handle_fab(fdt, bus_node, node, soc_model)
            s += fab_str
            all_icc_nodes.append(icc_nodes)
    return s, all_icc_nodes


def generate_qnodes(fdt: FdtRo, bus_node: DtNode, soc_model: str) -> str:
    s = ""
    for node in fdt.subnodes(bus_node):
        name = fdt.get_name(node)
        if name.startswith("mas-") or name.startswith("slv-"):
            s += handle_qnode(fdt, node, soc_model)
    return s


def generate_of_match(reg_names: List[str], soc_model: str) -> str:
    s = ""
    for reg_name in sorted(reg_names):
        short_name = reg_name.replace("-base", "")
        s += f'''
\t{{ .compatible = \"qcom,{soc_model}-{short_name.replace('_', '-')}\",
\t  .data = &{soc_model}_{short_name}}},\
'''
    return s


def generate_driver(fdt: FdtRo, options: generator.Options) -> List[List[str]]:
    bus_node: DtNode = fdt.path_offset('/soc/ad-hoc-bus')

    # as_uint32_array() is technically not correct here but works
    regs_prop = fdt.getprop(bus_node, "reg").as_uint32_array()
    regs = []
    for i in range(0, int(len(regs_prop) / 2)):
        reg = (regs_prop[i * 2], regs_prop[i * 2 + 1])
        regs.append(reg)
        # print(f"{hex(reg[0])} {hex(reg[1])}")

    reg_names = fdt.getprop(bus_node, "reg-names").as_stringlist()
    # print(reg_names)

    fabs, icc_nodes = generate_fabs(fdt, bus_node, options.soc_model)

    with open(f"generated/{options.soc_model}.c", "w") as f:
        f.write(f'''\
// SPDX-License-Identifier: GPL-2.0
/*
 * Copyright (c) 2020, The Linux Foundation. All rights reserved.
 */

#include <linux/device.h>
#include <linux/interconnect.h>
#include <linux/interconnect-provider.h>
#include <linux/module.h>
#include <linux/of_platform.h>
#include <dt-bindings/interconnect/qcom,{options.soc_model}.h>

#include "bcm-voter.h"
#include "icc-rpmh.h"
#include "{options.soc_model}.h"

{generate_qnodes(fdt, bus_node, options.soc_model)}

{generate_bcms(fdt, bus_node)}

{fabs}

static const struct of_device_id qnoc_of_match[] = {{\
{generate_of_match(reg_names, options.soc_model)}
\t{{ }}
}};
MODULE_DEVICE_TABLE(of, qnoc_of_match);

static struct platform_driver qnoc_driver = {{
\t.probe = qcom_icc_rpmh_probe,
\t.remove = qcom_icc_rpmh_remove,
\t.driver = {{
\t\t.name = \"qnoc-{options.soc_model}\",
\t\t.of_match_table = qnoc_of_match,
\t\t.sync_state = icc_sync_state,
\t}},
}};
module_platform_driver(qnoc_driver);

MODULE_DESCRIPTION(\"Qualcomm {options.soc_model.upper()} NoC driver\");
MODULE_LICENSE("GPL v2");
''')
    return icc_nodes
