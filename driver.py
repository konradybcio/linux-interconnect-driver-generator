# SPDX-License-Identifier: GPL-2.0-only
from typing import List, Tuple, Set

from libfdt import FdtRo

import generator
import helpers
from helpers import DtNode


def handle_qnode(fdt: FdtRo, node: DtNode, soc_model: str) -> Tuple[str, Set[str]]:
    """
    Transform all mas-* and srv-* nodes into DEFINE_QNODE macro
    """
    name = fdt.get_name(node)

    # Ignore ALC "since it will not be voted from kernel."
    #   https://lore.kernel.org/linux-arm-msm/1e79c73f22c8891dc9f868babd940fca@codeaurora.org/
    # Ignore IP0 since it's handled by clk framework
    #   https://lore.kernel.org/linux-arm-msm/20220412220033.1273607-1-swboyd@chromium.org/
    # Ignore _display -- unknown reason
    if name.endswith("-alc") or "-ipa-core-" in name or name.endswith("_display"):
        print(f"INFO: handle_qnode: ignoring {name}")
        return "", set()

    cell_id = fdt.getprop(node, "cell-id").as_uint32()
    agg_ports = fdt.getprop(node, "qcom,agg-ports").as_uint32()
    buswidth = fdt.getprop(node, "qcom,buswidth").as_uint32()
    connections_prop = fdt.getprop_or_none(node, "qcom,connections")
    if connections_prop is None:
        connections = []
    else:
        connections = connections_prop.as_uint32_list()

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

    node_names: Set[str] = set()
    node_names.add(cell_id_name)
    node_names.update(conn_cell_id_names)

    if len(conn_cell_id_names) > 0:
        links_str = ", " + ', '.join(conn_cell_id_names)
    else:
        links_str = ""
    return f"DEFINE_QNODE({qnode_name}, {cell_id_name}, {agg_ports}, {buswidth}{links_str});\n", node_names


def handle_bcm(fdt: FdtRo, bus_node: DtNode, node: DtNode) -> str:
    """
    Transform all bcm-* nodes into DEFINE_QBCM macro
    """
    name = fdt.get_name(node)

    # Ignore ALC "since it will not be voted from kernel."
    #   https://lore.kernel.org/linux-arm-msm/1e79c73f22c8891dc9f868babd940fca@codeaurora.org/
    # Ignore IP0 since it's handled by clk framework
    #   https://lore.kernel.org/linux-arm-msm/20220412220033.1273607-1-swboyd@chromium.org/
    # Ignore _display -- unknown reason
    if name.endswith("-alc") or name.endswith("-ip0") or name.endswith("_display"):
        print(f"INFO: handle_bcm: ignoring {name}")
        return ""

    bcm_name = fdt.getprop(node, "qcom,bcm-name").as_str()

    name2 = name.replace("-", "_")
    # print(name2)

    bcm_phandle = fdt.get_phandle(node)
    # print(bcm_phandle)

    ref_nodes = helpers.find_subnodes_referencing_phandle(fdt, bus_node, bcm_phandle, "qcom,bcms")
    ref_node_names = list(map(lambda x: fdt.get_name(x)[4:].replace("-", "_"), ref_nodes))
    # print(f"Got something: &{', &'.join(ref_nodes)}")

    # Unknown logic behind this
    # "You can keepalive enabled for SH0, MC0, MM0, SN0 and CN0."
    # https://lore.kernel.org/linux-arm-msm/1e79c73f22c8891dc9f868babd940fca@codeaurora.org/
    # git grep "^DEFINE_QBCM" | grep ", true," | cut -d"," -f2 | sort | uniq -c
    keep_alive = "true" if bcm_name in ["CN0", "MC0", "MM0", "MM1", "SH0", "SN0"] else "false"

    if len(ref_nodes) == 0:
        print(f"WARN: handle_bcm: ignoring {name}")
        return ""

    return f"DEFINE_QBCM({name2}, \"{bcm_name}\", {keep_alive}, &{', &'.join(ref_node_names)});\n"


def handle_fab(fdt: FdtRo, bus_node: DtNode, node: DtNode, soc_model: str) -> Tuple[str, List[str]]:
    """
    From all nodes that have e.g. qcom,bus-dev = <&fab_aggre1_noc>; get a set
    of qcom,bcms values and print as struct qcom_icc_bcm

    and more...
    """
    s = ""
    name = fdt.get_name(node)

    # Ignore _display FABs -- unknown reason
    if name.endswith("_display"):
        print(f"INFO: handle_fab: ignoring {name}")
        return "", []

    name = name[4:]

    qos_offset = None
    qos_offset_prop = fdt.getprop_or_none(node, "qcom,base-offset")
    if qos_offset_prop is not None:
        qos_offset = qos_offset_prop.as_int32()
        if qos_offset != 0:
            qos_offset = hex(qos_offset)
        else:
            qos_offset = None
    # print(f"QOS offset {name} = {qos_offset}")

    bus_type_prop = fdt.getprop_or_none(node, "qcom,bus-type")
    if bus_type_prop is not None:
        bus_type = bus_type_prop.as_int32()
        if bus_type == 1:
            bus_type = "QCOM_ICC_NOC"
        elif bus_type == 2:
            bus_type = "QCOM_ICC_BIMC"
        elif bus_type == 3:
            bus_type = "QCOM_ICC_QNOC"
        else:
            raise RuntimeError(f"Unhandled bus type (enum qcom_icc_type): {bus_type}")
    else:
        # Default type is NOC
        bus_type = "QCOM_ICC_NOC"

    clocks_prop = fdt.getprop_or_none(node, "clocks")
    if clocks_prop:
        clocks = clocks_prop.as_int32_list()
        if len(clocks) > 0:
            raise RuntimeError(f"Clocks are currently not handled in dts: {clocks}")

    s += f"static struct qcom_icc_bcm * const {name}_bcms[] = {{\n"
    phandle = fdt.get_phandle(node)
    ref_nodes = helpers.find_subnodes_referencing_phandle(fdt, bus_node, phandle, "qcom,bus-dev")

    bcms_set = set()
    for node in ref_nodes:
        bcms_prop = fdt.getprop_or_none(node, "qcom,bcms")
        bcms = []
        if bcms_prop is not None:
            bcms = bcms_prop.as_uint32_list()
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
        if bcm_name == "bcm_alc" or bcm_name == "bcm_ip0" or bcm_name.endswith("_display"):
            print(f"INFO: handle_fab: ignoring {bcm_name}")
            continue
        s += f"\t&{bcm_name},\n"

    s += f'''\
}};

static struct qcom_icc_node * const {name}_nodes[] = {{
'''

    icc_node_list = []
    for node in ref_nodes:
        cell_id = fdt.getprop(node, "cell-id").as_int32()
        idx = helpers.get_cell_id_name(cell_id, soc_model, False)

        node_name = fdt.get_name(node)
        qnode_name = node_name[4:].replace("-", "_")

        if qnode_name == "alc" or qnode_name.startswith("ipa_core_") or qnode_name.endswith("_display"):
            print(f"INFO: handle_fab: ignoring {qnode_name}")
            continue

        s += f"\t[{idx}] = &{qnode_name},\n"
        icc_node_list.append(idx)

    s += f'''\
}};

static const struct qcom_icc_desc {soc_model}_{name} = {{
\t.nodes = {name}_nodes,
\t.num_nodes = ARRAY_SIZE({name}_nodes),
\t.bcms = {name}_bcms,
\t.num_bcms = ARRAY_SIZE({name}_bcms),
'''
    # RPMH driver currently doesn't support .type
    # \t.type = {bus_type},

    # RPMH driver currently doesn't support .qos_offset
    # if qos_offset:
    #     s += f'\t.qos_offset = {qos_offset},\n'

    s += f'''\
}};

'''

    return s, icc_node_list


def generate_bcms(fdt: FdtRo, bus_node: DtNode) -> str:
    s = ""
    for node in fdt.subnodes(bus_node):
        name = fdt.get_name(node)
        if name.startswith("bcm-"):
            s += handle_bcm(fdt, bus_node, node)
    return s.strip()


def generate_fabs(fdt: FdtRo, bus_node: DtNode, soc_model: str) -> Tuple[str, List[List[str]]]:
    s = ""
    all_icc_nodes = []
    for node in fdt.subnodes(bus_node):
        name = fdt.get_name(node)
        if name.startswith("fab-"):
            fab_str, icc_nodes = handle_fab(fdt, bus_node, node, soc_model)
            s += fab_str
            all_icc_nodes.append(icc_nodes)
    return s.strip(), all_icc_nodes


def generate_qnodes(fdt: FdtRo, bus_node: DtNode, soc_model: str) -> Tuple[str, Set[str]]:
    s = ""
    all_node_names: Set[str] = set()
    for node in fdt.subnodes(bus_node):
        name = fdt.get_name(node)
        if name.startswith("mas-") or name.startswith("slv-"):
            qnode_str, node_names = handle_qnode(fdt, node, soc_model)
            s += qnode_str
            all_node_names.update(node_names)
    return s.strip(), all_node_names


def generate_of_match(reg_names: List[str], soc_model: str) -> str:
    s = ""
    for reg_name in sorted(reg_names):
        short_name = reg_name.replace("-base", "")
        s += f'''
\t{{ .compatible = \"qcom,{soc_model}-{short_name.replace('_', '-')}\",
\t  .data = &{soc_model}_{short_name}}},\
'''
    return s


def generate_driver(fdt: FdtRo, options: generator.Options) -> Tuple[List[List[str]], Set[str]]:
    bus_node: DtNode = fdt.path_offset('/soc/ad-hoc-bus')

    regs_prop = fdt.getprop(bus_node, "reg").as_uint32_list()
    regs = []
    for i in range(0, int(len(regs_prop) / 2)):
        reg = (regs_prop[i * 2], regs_prop[i * 2 + 1])
        regs.append(reg)
        # print(f"{hex(reg[0])} {hex(reg[1])}")

    reg_names = fdt.getprop(bus_node, "reg-names").as_stringlist()
    # print(reg_names)

    fabs, icc_nodes = generate_fabs(fdt, bus_node, options.soc_model)

    qnodes, node_names = generate_qnodes(fdt, bus_node, options.soc_model)

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

{qnodes}

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
    return icc_nodes, node_names
