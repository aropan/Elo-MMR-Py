#!/usr/bin/env bash
set -euo pipefail

# The pinned upstream enables native-tls transitively, so openssl-sys must find
# OpenSSL headers even though the Python bindings do not use its HTTP code.
if command -v dnf >/dev/null 2>&1; then
  dnf install -y openssl-devel
elif command -v yum >/dev/null 2>&1; then
  yum install -y openssl-devel
else
  echo 'No supported manylinux package manager found' >&2
  exit 1
fi
