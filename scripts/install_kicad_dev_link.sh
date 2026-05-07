#!/usr/bin/env bash
set -euo pipefail

# Creates a development symlink for KiGit in KiCad 10 PCM plugin directory.
#
# Target location (Linux KiCad 10):
#   ~/.local/share/kicad/10.0/3rdparty/plugins/
#
# This matches KiCad’s on-disk layout where the plugin directory contains the Python
# files directly (not nested under an extra `plugins/` folder).

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_LINK="${REPO_ROOT}/.stage_pcm/plugins"
DEST_DIR="${HOME}/.local/share/kicad/10.0/3rdparty/plugins"

NAME="com_github_ahmedmikatonikpc_kigit_dev"
DEST_LINK="${DEST_DIR}/${NAME}"

if [[ ! -d "${SRC_LINK}" ]]; then
  echo "Missing staged plugin dir: ${SRC_LINK}"
  echo "Run: python3 scripts/build_pcm_zip.py --version 0.x.y"
  exit 1
fi

mkdir -p "${DEST_DIR}"

if [[ -e "${DEST_LINK}" || -L "${DEST_LINK}" ]]; then
  echo "Already exists: ${DEST_LINK}"
  echo "Remove it first:"
  echo "  rm -rf \"${DEST_LINK}\""
  exit 1
fi

ln -s "${SRC_LINK}" "${DEST_LINK}"
echo "Created dev symlink:"
echo "  ${DEST_LINK} -> ${SRC_LINK}"
echo
echo "Restart KiCad to reload plugins."

