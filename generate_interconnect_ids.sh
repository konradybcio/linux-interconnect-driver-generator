#!/bin/bash

grep "^#define" interconnect_ids.h > interconnect_ids.h.tmp

duplicates="$(awk -F '[ \t]+' '{print $3}' interconnect_ids.h.tmp | sort | uniq -d)"
if [ -n "$duplicates" ]; then
    echo "ERROR: Duplicates found: $duplicates"
    exit 1
fi

echo "bus_ids = {" > interconnect_ids.py
sed 's|#define\t\(\w\+\)[ \t]\+\([[:digit:]]\+\)|    \2: "\1",|' interconnect_ids.h.tmp >> interconnect_ids.py
echo "}" >> interconnect_ids.py

rm interconnect_ids.h.tmp
