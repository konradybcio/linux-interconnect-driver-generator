#!/usr/bin/python3
# SPDX-License-Identifier: GPL-2.0-only
import argparse
import os
import shutil

from libfdt import Fdt, FdtRo

import generator
from driver import generate_driver
from driver_header import generate_driver_header
from dts import generate_dts


def generate(fdt: FdtRo, options: generator.Options) -> None:
    # FIXME use soc_model as directory name?
    if os.path.exists("generated"):
        shutil.rmtree("generated")
    os.mkdir("generated")

    generate_driver(fdt, options)
    generate_driver_header(fdt)
    generate_dts(fdt, options)
    # TODO generate include/dt-bindings/interconnect/qcom,{options.soc_name}.h


parser = argparse.ArgumentParser(
    description="Generate Linux interconnect driver based on (downstream) msm-bus-device device tree")
parser.add_argument('soc_model', help="Model name in mainline (e.g. SM8250)")
parser.add_argument('dtb', type=argparse.FileType('rb'), help="Device tree blobs to parse")

args = parser.parse_args(namespace=generator.Options())

with args.dtb as f:
    print(f"Parsing: {f.name}")
    args.soc_model = args.soc_model.lower()
    generate(Fdt(f.read()), args)
