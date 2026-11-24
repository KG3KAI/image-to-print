#!/usr/bin/env bash
# Offline slice with Bambu Studio CLI using its default printer/filament. Usage: slice_bambu.sh model.3mf outdir
set -euo pipefail
BS="${BAMBU_STUDIO:-/Applications/BambuStudio.app/Contents/MacOS/BambuStudio}"
[ -x "$BS" ] || { echo "Bambu Studio not found; set BAMBU_STUDIO"; exit 1; }
IN="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"; OUT="${2:-$(dirname "$IN")/slice}"
mkdir -p "$OUT"; OUT="$(cd "$OUT" && pwd)"
"$BS" --slice 0 --outputdir "$OUT" "$IN" >"$OUT/bambu.log" 2>&1 || true
python3 - "$OUT" <<'PY'
import json, sys, re, pathlib
out = pathlib.Path(sys.argv[1]); r = json.loads((out / "result.json").read_text())
g = next(out.glob("*.gcode"), None)
est = None
if g:
    for line in g.open(errors="ignore"):
        m = re.search(r"estimated printing time \(normal mode\) = (.+)", line)
        if m: est = m.group(1).strip(); break
print(json.dumps({"ok": r.get("return_code") == 0, "message": r.get("error_string"), "gcode": str(g) if g else None,
                  "estimated_time": est, "layer_height": round(r.get("layer_height", 0), 2)}, ensure_ascii=False))
PY
