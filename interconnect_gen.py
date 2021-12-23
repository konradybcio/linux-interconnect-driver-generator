#!/usr/bin/python3
# SPDX-License-Identifier: GPL-2.0-only

# Generate mainline interconnect stuff from downstream qcom,msm-bus-device
# interconnect_gen_ids.h is from downstream include/dt-bindings/msm/msm-bus-ids.h
#  MSM_BUS_MASTER_AMPSS_M0 -> MSM_BUS_MASTER_NPU_PROC
# echo "bus_ids = {}" > interconnect_gen_ids.py && sed 's|#define\t\(\w\+\) \([[:digit:]]\+\)|bus_ids[\2] = "\1"|' interconnect_gen_ids.h >> interconnect_gen_ids.py

import sys
from typing import List

import libfdt

import interconnect_gen_ids
# noinspection PyUnresolvedReferences
import libfdt_ext

soc_model = "unknown"

DtNode = int
Phandle = int


# FIXME
header = """// SPDX-License-Identifier: GPL-2.0
/*
 * Copyright (c) 2020, The Linux Foundation. All rights reserved.
 *
 */

#include <linux/device.h>
#include <linux/interconnect.h>
#include <linux/interconnect-provider.h>
#include <linux/module.h>
#include <linux/of_platform.h>
#include <dt-bindings/interconnect/qcom,sm8250.h>

#include "bcm-voter.h"
#include "icc-rpmh.h"
#include "sm8250.h"
"""

def get_cell_id_name(cell_id: int, soc_prefix: bool) -> str:
    name = interconnect_gen_ids.bus_ids[cell_id]
    return name.replace("MSM_BUS_", f"{soc_model.upper()}_" if soc_prefix else "")


def find_subnodes_referencing_phandle(fdt: libfdt.FdtRo, bus_node: DtNode,
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


def handle_qnode(fdt: libfdt.FdtRo, node: DtNode):
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
        conn_cell_id_names.append(get_cell_id_name(conn_cell_id, True))

    qnode_name = name[4:].replace("-", "_")
    cell_id_name = get_cell_id_name(cell_id, True)

    if len(conn_cell_id_names) > 0:
        links_str = ", " + ', '.join(conn_cell_id_names)
    else:
        links_str = ""
    print(
        f"DEFINE_QNODE({qnode_name}, {cell_id_name}, {agg_ports}, {buswidth}{links_str});",
        file=sys.stderr)


def handle_bcm(fdt, bus_node, node):
    """
    Transform all bcm-* nodes into DEFINE_QBCM macro
    """
    name = fdt.get_name(node)
    bcm_name = fdt.getprop(node, "qcom,bcm-name").as_str()

    name2 = name.replace("-", "_")
    # print(name2)

    bcm_phandle = fdt.get_phandle(node)
    # print(bcm_phandle)

    ref_nodes = find_subnodes_referencing_phandle(fdt, bus_node, bcm_phandle, "qcom,bcms")
    ref_node_names = list(map(lambda x: fdt.get_name(x)[4:].replace("-", "_"), ref_nodes))
    # print(f"Got something: &{', &'.join(ref_nodes)}")

    keep_alive = "false"  # FIXME

    if len(ref_nodes) == 0:
        print(f"WARN: ignoring BCM {name2}")
        return

    print(f"DEFINE_QBCM({name2}, \"{bcm_name}\", {keep_alive}, &{', &'.join(ref_node_names)});", file=sys.stderr)


def handle_fab(fdt, bus_node, node):
    """
    From all nodes that have e.g. qcom,bus-dev = <&fab_aggre1_noc>; get a set
    of qcom,bcms values and print as struct qcom_icc_bcm

    and more...
    """
    name = fdt.get_name(node)[4:]

    if name.endswith("_display"):
        print(f"WARN: ignoring FAB {name}")
        return

    print(f"static struct qcom_icc_bcm *{name}_bcms[] = {{", file=sys.stderr)
    phandle = fdt.get_phandle(node)
    ref_nodes = find_subnodes_referencing_phandle(fdt, bus_node, phandle, "qcom,bus-dev")

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
        print(f"\t&{bcm_name},", file=sys.stderr)

    print("};", file=sys.stderr)

    print(file=sys.stderr)

    print(f"static struct qcom_icc_node *{name}_nodes[] = {{", file=sys.stderr)
    for node in ref_nodes:
        cell_id = fdt.getprop(node, "cell-id").as_int32()
        idx = get_cell_id_name(cell_id, False)

        node_name = fdt.get_name(node)
        qnode_name = node_name[4:].replace("-", "_")

        print(f"\t[{idx}] = &{qnode_name},", file=sys.stderr)
    print("};", file=sys.stderr)

    print(file=sys.stderr)

    print(f"static struct qcom_icc_desc {soc_model}_{name} = {{", file=sys.stderr)
    print(f"\t.nodes = {name}_nodes,", file=sys.stderr)
    print(f"\t.num_nodes = ARRAY_SIZE({name}_nodes),", file=sys.stderr)
    print(f"\t.bcms = {name}_bcms,", file=sys.stderr)
    print(f"\t.num_bcms = ARRAY_SIZE({name}_bcms),", file=sys.stderr)
    print("};", file=sys.stderr)

    print(file=sys.stderr)


def main():
    if len(sys.argv) < 3:
        print("Usage: {} <soc_model> <dtb_file>".format(sys.argv[0]))
        sys.exit(1)

    global soc_model
    soc_model = sys.argv[1].lower()

    with open(sys.argv[2], mode='rb') as f:
        fdt = libfdt.FdtRo(f.read())

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

    print(header, file=sys.stderr)

    for node in fdt.subnodes(bus_node):
        name = fdt.get_name(node)
        if name.startswith("mas-") or name.startswith("slv-"):
            handle_qnode(fdt, node)

    print(file=sys.stderr)

    for node in fdt.subnodes(bus_node):
        name = fdt.get_name(node)
        if name.startswith("bcm-"):
            handle_bcm(fdt, bus_node, node)

    print(file=sys.stderr)

    for node in fdt.subnodes(bus_node):
        name = fdt.get_name(node)
        if name.startswith("fab-"):
            handle_fab(fdt, bus_node, node)

    # Driver boiler plate
    print("static const struct of_device_id qnoc_of_match[] = {", file=sys.stderr)
    for reg_name in sorted(reg_names):
        short_name = reg_name.replace("-base", "")
        print(f"\t{{ .compatible = \"qcom,{soc_model}-{short_name.replace('_', '-')}\",", file=sys.stderr)
        print(f"\t  .data = &{soc_model}_{short_name}}},", file=sys.stderr)
    print("\t{ }", file=sys.stderr)
    print("};", file=sys.stderr)
    print("MODULE_DEVICE_TABLE(of, qnoc_of_match);", file=sys.stderr)

    print(file=sys.stderr)

    print("static struct platform_driver qnoc_driver = {", file=sys.stderr)
    print("\t.probe = qcom_icc_rpmh_probe,", file=sys.stderr)
    print("\t.remove = qcom_icc_rpmh_remove,", file=sys.stderr)
    print("\t.driver = {", file=sys.stderr)
    print(f"\t\t.name = \"qnoc-{soc_model}\",", file=sys.stderr)
    print("\t\t.of_match_table = qnoc_of_match,", file=sys.stderr)
    print("\t\t.sync_state = icc_sync_state,", file=sys.stderr)
    print("\t},", file=sys.stderr)
    print("};", file=sys.stderr)
    print("module_platform_driver(qnoc_driver);", file=sys.stderr)

    print(file=sys.stderr)

    print(f"MODULE_DESCRIPTION(\"Qualcomm {soc_model.upper()} NoC driver\");", file=sys.stderr)
    print("MODULE_LICENSE(\"GPL v2\");", file=sys.stderr)

    # for reg_name in reg_names:
    #     short_name = reg_name.replace("-base", "")
    #     print(f"static struct qcom_icc_bcm *{short_name}_bcms[] = {{")

    # TODO Generate dts
    # TODO Generate {soc_name}.h


if __name__ == '__main__':
    main()
