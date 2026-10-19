#!/bin/bash
# Private CUDA 12.8 copy with math_functions.h patched for glibc >= 2.41.
# glibc 2.41+ (Ubuntu 26.04 has 2.43) declares sinpi/cospi/rsqrt (+f variants) noexcept(true);
# CUDA 12.8's crt/math_functions.h does not, so every .cu that includes <cmath> fails with
# "exception specification is incompatible with that of previous function". NVIDIA fixed it in
# CUDA 12.9. This leaves the root-owned /usr/local/cuda-12.8 untouched and builds a copy at
# opt/cuda-12.8-patched. Use: export CUDA_HOME=/srv/containers/edq/opt/cuda-12.8-patched
set -e
SRC=/usr/local/cuda-12.8
DST=/srv/containers/edq/opt/cuda-12.8-patched
T=targets/x86_64-linux

if [ -x "$DST/bin/nvcc" ] && grep -q 'cospi(double x) noexcept' "$DST/$T/include/crt/math_functions.h"; then
    echo "already patched: $DST"
    exit 0
fi

mkdir -p "$DST/$T"
cp -a "$SRC/bin" "$DST/bin"
cp -a "$SRC/nvvm" "$DST/nvvm"
cp -a "$SRC/$T/include" "$DST/$T/include"
ln -sfn "$SRC/$T/lib" "$DST/$T/lib"
ln -sfn "$T/include" "$DST/include"
ln -sfn "$T/lib" "$DST/lib64"
ln -sfn "$SRC/extras" "$DST/extras"
cp -a "$SRC/version.json" "$DST/version.json"

H="$DST/$T/include/crt/math_functions.h"
chmod u+w "$H"
sed -i -E 's/^(extern __DEVICE_FUNCTIONS_DECL__ __device_builtin__ (double|float) +(cospi|sinpi|rsqrt|cospif|sinpif|rsqrtf)\((double|float) x\));/\1 noexcept(true);/' "$H"
grep -n -E '(cospi|sinpi|rsqrt)f?\((double|float) x\)' "$H" | grep -v '^\s*[0-9]*: \*'
