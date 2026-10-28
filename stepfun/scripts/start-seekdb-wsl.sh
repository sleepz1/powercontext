#!/usr/bin/env bash
set -euo pipefail
# Installs and models live on E:. Keep database files on WSL's native filesystem;
# this machine's /mnt/e mount failed database direct I/O initialization.
installation=/mnt/e/tools/seekdb-linux/1.4.0
runtime="${SEEKDB_RUNTIME:-/home/geshanchang/seekdb-contest-runtime2}"
if [[ ! -x "$installation/usr/bin/seekdb" ]]; then
  echo "Missing official seekdb 1.4.0 under $installation" >&2; exit 1
fi
if [[ -f "$runtime/run/seekdb.pid" ]]; then
  read -r seekdb_pid < "$runtime/run/seekdb.pid" || true
  if [[ "${seekdb_pid:-}" =~ ^[0-9]+$ ]] && kill -0 "$seekdb_pid" 2>/dev/null; then
    echo "seekdb already running, PID $seekdb_pid; runtime $runtime"; exit 0
  fi
fi
mkdir -p "$runtime"
export LD_LIBRARY_PATH="$installation/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$installation/usr/bin/seekdb" --nodaemon --base-dir "$runtime" --port 2881 --log-level WARN \
  --parameter datafile_size=1G --parameter datafile_maxsize=4G --parameter log_disk_size=2G
