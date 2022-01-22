# SPDX-License-Identifier: GPL-2.0-only
import sys

from libfdt import FdtRo

import generator
# noinspection PyUnresolvedReferences
import libfdt_ext
from helpers import DtNode


# FIXME Some regs and sizes are wrong?
# This is relevant for *some*... (example from sm8250)
# 0x1733000 = compute_noc-base 0x1700000 + qcom,base-offset = <208896>;
# compute_noc: interconnect@1733000 {
def generate_dts(fdt: FdtRo, options: generator.Options) -> None:
    bus_node: DtNode = fdt.path_offset('/soc/ad-hoc-bus')

    regs_prop = fdt.getprop(bus_node, "reg").as_uint32_list()
    reg_names = fdt.getprop(bus_node, "reg-names").as_stringlist()

    if len(regs_prop) / 2 != len(reg_names):
        print(f"ERROR: regs len {len(regs_prop) / 2} != reg-names len {len(reg_names)}")
        sys.exit(1)

    regs = []
    for i in range(0, len(reg_names)):
        # tuples are (reg, size, reg_name)
        reg = (regs_prop[i * 2], regs_prop[i * 2 + 1], reg_names[i])
        regs.append(reg)

    regs = sorted(regs, key=lambda x: x[0])

    with open("generated/interconnect.dtsi", "w") as f:
        for reg, size, reg_name in regs:
            short_name = reg_name.replace("-base", "")
            f.write(f'''\
{short_name}: interconnect@{'{:x}'.format(reg)} {{
	compatible = "qcom,{options.soc_model}-{short_name.replace("_", "-")}";
	reg = <0 0x{'{:08x}'.format(reg)} 0 {hex(size)}>;
	#interconnect-cells = <1>;
	qcom,bcm-voters = <&apps_bcm_voter>;
}};

''')
