# SPDX-License-Identifier: GPL-2.0-only
from typing import List

import generator
import helpers


def generate_defines(icc_nodes: List[List[str]]) -> str:
    s = ""
    for group in icc_nodes:
        for idx, item in enumerate(group):
            s += helpers.pad_with_tabs(f"#define {item}", f"{idx}\n", 5)
        s += "\n"
    return s.strip()


def generate_dt_bindings_header(icc_nodes: List[List[str]], options: generator.Options) -> None:
    with open(f"generated/qcom,{options.soc_model}.h", "w") as f:
        f.write(f'''\
/* SPDX-License-Identifier: GPL-2.0 */
/*
 * Qualcomm {options.soc_model.upper()} interconnect IDs
 *
 * Copyright (c) 2020, The Linux Foundation. All rights reserved.
 */

#ifndef __DT_BINDINGS_INTERCONNECT_QCOM_{options.soc_model.upper()}_H
#define __DT_BINDINGS_INTERCONNECT_QCOM_{options.soc_model.upper()}_H

{generate_defines(icc_nodes)}

#endif
''')
