# SPDX-License-Identifier: GPL-2.0-only
from typing import Set

import generator
import helpers


def generate_defines(node_names: Set[str]) -> str:
    s = ""
    for idx, name in enumerate(sorted(node_names)):
        s += helpers.pad_with_tabs(f"#define {name}", f"{idx}\n", 6)
    s += "\n"
    return s.strip()


def generate_driver_header(node_names: Set[str], options: generator.Options) -> None:
    with open(f"generated/{options.soc_model}.h", "w") as f:
        f.write(f'''\
/* SPDX-License-Identifier: GPL-2.0 */
/*
 * Qualcomm #define {options.soc_model.upper()} interconnect IDs
 *
 * Copyright (c) 2020, The Linux Foundation. All rights reserved.
 */

#ifndef __DRIVERS_INTERCONNECT_QCOM_{options.soc_model.upper()}_H
#define __DRIVERS_INTERCONNECT_QCOM_{options.soc_model.upper()}_H

{generate_defines(node_names)}

#endif
''')
