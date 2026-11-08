#!/usr/bin/env bash
# p10_build.sh - builds the Phase 10 tools into build/p10/ (untracked). Usage: bash scripts/p10_build.sh 2>&1 | tee logs/p10/p10_build.log
set -eu
cd "$(dirname "${BASH_SOURCE[0]}")/.."
mkdir -p build/p10
rm -f build/p10/p10_memcpy build/p10/p10_testrun build/p10/p10_drain build/p10/p10_loop_unbounded.o build/p10/p10_loop_bounded.o
gcc -O2 -Wall -Wextra -Werror -o build/p10/p10_memcpy src/p10/p10_memcpy.c
gcc -O2 -Wall -Wextra -Werror -o build/p10/p10_testrun src/p10/p10_testrun.c -lbpf
gcc -O2 -Wall -Wextra -Werror -o build/p10/p10_drain src/p10/p10_drain.c -lbpf
for t in p10_memcpy p10_testrun p10_drain; do test -x build/p10/$t; echo "built build/p10/$t"; done
