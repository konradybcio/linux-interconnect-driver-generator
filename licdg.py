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
from dts_header import generate_dt_bindings_header


def generate(fdt: FdtRo, options: generator.Options) -> None:
    if os.path.exists("generated"):
        shutil.rmtree("generated")
    os.mkdir("generated")

    # Generate drivers/interconnect/qcom/smXXXX.c
    icc_nodes, node_names = generate_driver(fdt, options)
    # Generate drivers/interconnect/qcom/smXXXX.h
    generate_driver_header(node_names, options)
    # Generate include/dt-bindings/interconnect/qcom,smXXXX.h
    generate_dt_bindings_header(icc_nodes, options)
    # Generate nodes for arch/arm64/boot/dts/qcom/smXXXX.dtsi
    generate_dts(fdt, options)

    # Things to update manually:
    # * Documentation/devicetree/bindings/interconnect/qcom,rpmh.yaml
    # * drivers/interconnect/qcom/Kconfig
    # * drivers/interconnect/qcom/Makefile


parser = argparse.ArgumentParser(
    description="Generate Linux interconnect driver based on (downstream) msm-bus-device device tree")
parser.add_argument('soc_model', help="Model name in mainline (e.g. SM8250)")
parser.add_argument('dtb', type=argparse.FileType('rb'), help="Device tree blobs to parse")

args = parser.parse_args(namespace=generator.Options())

with args.dtb as f:
    print(f"Parsing: {f.name}")
    args.soc_model = args.soc_model.lower()
    generate(Fdt(f.read()), args)
