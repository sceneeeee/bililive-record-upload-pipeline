#!/usr/bin/env bash
# Run on a build host with Docker, never against a running application container.
set -euo pipefail
repo=$(cd -- "$(dirname -- "$0")/.." && pwd)
output=${1:-"$repo/build/upstream"}
image=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["images"]["bililive-api"])' "$repo/patches/versions.lock.json")
mkdir -p -- "$output"
for name in index-DQV9sVEn.cjs index-ZJeYopVC.cjs; do
    if [[ -e "$output/$name" ]]; then
        echo "Output already exists; choose an empty extraction directory" >&2
        exit 1
    fi
done
docker pull --platform linux/amd64 "$image"
container=$(docker create --platform linux/amd64 "$image")
trap 'docker rm "$container" >/dev/null' EXIT
docker cp "$container:/app/index-DQV9sVEn.cjs" "$output/index-DQV9sVEn.cjs"
docker cp "$container:/app/index-ZJeYopVC.cjs" "$output/index-ZJeYopVC.cjs"
python3 "$repo/scripts/build_patches.py" --upstream "$output"
