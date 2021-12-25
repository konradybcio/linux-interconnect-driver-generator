# SPDX-License-Identifier: GPL-2.0-only
import math
from typing import List

import generator

TAB_SIZE = 8


def pad_with_tabs(string: str, suffix: str, num_tabs: int = 5) -> str:
    remaining_size = num_tabs * TAB_SIZE - len(string)
    # print(f"remaining_size = {remaining_size} -- len(string) {len(string)}")
    num_tabs = math.ceil(remaining_size / TAB_SIZE)
    return string + "\t"*num_tabs + suffix


def generate_defines(icc_nodes: List[List[str]]) -> str:
    s = ""
    for group in icc_nodes:
        for idx, item in enumerate(group):
            s += pad_with_tabs(f"#define {item}", f"{idx}\n")
        s += "\n"
    return s


def generate_dt_bindings_header(icc_nodes: List[List[str]], options: generator.Options) -> None:
    # FIXME use soc_model as directory name?
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
