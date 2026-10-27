#!/usr/bin/env bash
# c1_build.sh - build the Phase 6c tools into build/p6c/ (not tracked). Usage: bash scripts/c1_build.sh 2>&1 | tee logs/p6c/p6c_build.log
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
mkdir -p build/p6c
CF="-O2 -g -Wall -Wextra -std=gnu11 -Isrc"
echo "\$ gcc $CF -o build/p6c/c1_oracle src/c1_oracle.c -lpcap"
gcc $CF -o build/p6c/c1_oracle src/c1_oracle.c -lpcap
echo "\$ gcc $CF -DC1_COUNT -o build/p6c/c1_interp_count src/c1_interp.c"
gcc $CF -DC1_COUNT -o build/p6c/c1_interp_count src/c1_interp.c
echo "\$ gcc $CF -o build/p6c/c1_interp_ir src/c1_interp.c"
gcc $CF -o build/p6c/c1_interp_ir src/c1_interp.c
ls -l build/p6c/
