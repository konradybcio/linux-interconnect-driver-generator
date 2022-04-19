# SPDX-License-Identifier: GPL-2.0-only
import sys
from dataclasses import dataclass
from itertools import groupby

from libfdt import FdtRo

import generator
# noinspection PyUnresolvedReferences
import libfdt_ext
from helpers import DtNode


@dataclass
class NocReg:
    reg: int
    size: int
    reg_name: str


def separate_nocs(nocs):
    main_noc = []
    child_nocs = []

    for noc in nocs:
        if noc.reg_name.endswith("_virt-base"):
            child_nocs.append(noc)
        else:
            main_noc.append(noc)

    # Special case for some SoCs
    if len(main_noc) == 2 and \
            main_noc[0].reg_name == "aggre2_noc-base" and \
            main_noc[1].reg_name == "compute_noc-base":
        print("INFO: separate_nocs: Moving compute_noc as child of aggre2_noc")
        child_nocs.append(main_noc.pop())

    return main_noc, child_nocs


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
        reg = NocReg(regs_prop[i * 2], regs_prop[i * 2 + 1], reg_names[i])
        regs.append(reg)

    regs = sorted(regs, key=lambda x: x.reg)

    with open("generated/interconnect.dtsi", "w") as f:
        for _, reg_group in groupby(regs, lambda x: x.reg):
            reg_group = list(reg_group)

            main_noc, child_nocs = separate_nocs(reg_group)
            if len(main_noc) != 1:
                raise RuntimeError(f"Expected only one main noc, got: {main_noc}")
            main_noc = main_noc[0]

            short_name = main_noc.reg_name.replace("-base", "")
            f.write(f'''\
{short_name}: interconnect@{'{:x}'.format(main_noc.reg)} {{
	compatible = "qcom,{options.soc_model}-{short_name.replace("_", "-")}";
	reg = <0 0x{'{:08x}'.format(main_noc.reg)} 0 {hex(main_noc.size)}>;
	#interconnect-cells = <1>;
	qcom,bcm-voters = <&apps_bcm_voter>;
''')

            for child_noc in child_nocs:
                short_name = child_noc.reg_name.replace("-base", "")
                f.write(f'''\

	{short_name}: interconnect-{short_name.replace("_virt", "").replace("_", "-")} {{
		compatible = "qcom,{options.soc_model}-{short_name.replace("_", "-")}";
		#interconnect-cells = <1>;
		qcom,bcm-voters = <&apps_bcm_voter>;
	}};
''')

            f.write(f'''\
}};

''')
