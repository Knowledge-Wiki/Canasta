"""Freeze the parent image's Composer inputs and remove runtime resolution."""
import hashlib
import json
import os
from pathlib import Path
import urllib.request

home = Path(os.environ["MW_HOME"])
root = Path("/opt/canasta-runtime")
config = json.loads((home / "composer.local.json").read_text())
files = {home / "composer.json", home / "composer.local.json", home / "composer.lock"}
for pattern in config["extra"]["merge-plugin"]["include"]:
    matches = list(home.glob(pattern))
    if not matches:
        raise RuntimeError(f"Missing build dependency metadata: {pattern}")
    files.update(matches)
manifest = {
    str(path.relative_to(home)): [hashlib.sha256(path.read_bytes()).hexdigest()]
    for path in sorted(files)
}

# Support this pinned SRF source when supplied on an extension volume. Its runtime
# requirements must match the image's bundled SRF before reusing vendor/.
srf_commit = "a2682d7841c442e82533360fd0f35e2b40c17d68"
srf_path = "extensions/SemanticResultFormats/composer.json"
url = f"https://raw.githubusercontent.com/SemanticMediaWiki/SemanticResultFormats/{srf_commit}/composer.json"
with urllib.request.urlopen(url, timeout=60) as response:
    srf_bytes = response.read()
bundled = json.loads((home / srf_path).read_text())
override = json.loads(srf_bytes)
for key in ("require", "conflict", "replace", "provide", "autoload"):
    if bundled.get(key) != override.get(key):
        raise RuntimeError(f"SRF {key} changed; review root libraries before building")
manifest[srf_path].append(hashlib.sha256(srf_bytes).hexdigest())
(root / "composer-inputs.json").write_text(json.dumps(manifest, indent=2) + "\n")

startup = Path("/run-all.sh")
source = startup.read_text()
start = source.index("# Unified composer autoloader")
end = source.index("/update-docker-gateway.sh", start)
source = source[:start] + """# Verify pinned dependencies and refresh autoloading for mounted extensions.
# This never resolves or downloads new dependency versions.
/opt/canasta-runtime/prepare-composer.sh || exit 1

""" + source[end:]
needle = "  run_autoupdate\n"
if source.count(needle) != 1:
    raise RuntimeError("Unexpected Canasta startup maintenance entry point")
source = source.replace(needle, '  if isTrue "$MW_AUTOUPDATE"; then\n    run_autoupdate || exit 1\n  fi\n')
startup.write_text(source)
