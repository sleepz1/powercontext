#!/usr/bin/env bash
set -euo pipefail
# Run inside Ubuntu 24.04 WSL. No sudo, no service changes, no deletions.
installation=/mnt/e/tools/seekdb-linux/1.4.0
downloads=/mnt/e/seekdb-deps
if pgrep -x seekdb >/dev/null; then
  echo 'seekdb is already running; leave installed program files unchanged.'; exit 0
fi
mkdir -p "$installation" "$downloads"
package="$downloads/seekdb-linux-1.4.0.deb"
expected=8b2b15ecb0d7d681105776895c2a029f8064c3476150242635515f3a355abee3
if [[ ! -f "$package" ]]; then
  curl -fL --retry 3 \
    https://mirrors.oceanbase.com/oceanbase/community/stable/ubuntu/jammy/amd64/seekdb_1.4.0-100000212026082616ubuntu22.04_amd64.deb \
    -o "$package"
fi
printf '%s  %s\n' "$expected" "$package" | sha256sum --check -
dpkg-deb -x "$package" "$installation"
cd "$downloads"
apt-get download libaio1t64
shopt -s nullglob
aio_packages=("$downloads"/libaio1t64_*_amd64.deb)
if [[ ${#aio_packages[@]} -ne 1 ]]; then
  echo 'Expected one libaio1t64 package; inspect downloaded files manually.' >&2; exit 1
fi
dpkg-deb -x "${aio_packages[0]}" "$installation"
aio_dir="$installation/usr/lib/x86_64-linux-gnu"
if [[ ! -e "$aio_dir/libaio.so.1" ]]; then ln -s libaio.so.1t64 "$aio_dir/libaio.so.1"; fi
LD_LIBRARY_PATH="$aio_dir" "$installation/usr/bin/seekdb" --version
