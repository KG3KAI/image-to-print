#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
VENV="$HOME/.image-to-print-venv"
command -v uv >/dev/null || { echo "need uv: curl -LsSf https://astral.sh/uv/install.sh | sh"; exit 1; }
[ -x "$VENV/bin/python" ] || uv venv "$VENV" --python 3.11
uv pip install --python "$VENV/bin/python" trimesh numpy pillow scipy manifold3d networkx lxml shapely rtree matplotlib gradio_client requests
for dest in "$HOME/.codex/skills" "$HOME/.claude/skills"; do
  mkdir -p "$dest"
  ln -sfn "$HERE/skill/image-to-print" "$dest/image-to-print"
  echo "linked $dest/image-to-print"
done
