#!/usr/bin/env bash
# p10b_build.sh - builds the three Phase 10 WP1b tools into build/p10/ (untracked). Usage: bash scripts/p10b_build.sh 2>&1 | tee logs/p10/p10b_build.log
set -eu
cd "$(dirname "${BASH_SOURCE[0]}")/.."
mkdir -p build/p10
rm -f build/p10/p10b_memcpy build/p10/p10b_testrun build/p10/p10b_drain
gcc -O2 -Wall -Wextra -Werror -o build/p10/p10b_memcpy src/p10/p10b_memcpy.c
gcc -O2 -Wall -Wextra -Werror -o build/p10/p10b_testrun src/p10/p10b_testrun.c -lbpf
gcc -O2 -Wall -Wextra -Werror -o build/p10/p10b_drain src/p10/p10b_drain.c -lbpf
for t in p10b_memcpy p10b_testrun p10b_drain; do test -x build/p10/$t; echo "built build/p10/$t"; done
