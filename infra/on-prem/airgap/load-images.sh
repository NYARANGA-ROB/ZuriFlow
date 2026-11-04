#!/usr/bin/env bash
# Load exported tarball into a private registry.
set -euo pipefail

TARBALL="${1:?Usage: load-images.sh <tarball> [registry]}"
TARGET_REGISTRY="${2:-registry.internal:5000}"

echo "Loading ${TARBALL}..."
docker load -i "$TARBALL"

# Re-tag and push every loaded image to the private registry.
while read -r src; do
  name_tag="${src#*/}"
  dest="${TARGET_REGISTRY}/${name_tag}"
  echo "→ ${src} => ${dest}"
  docker tag "$src" "$dest"
  docker push "$dest"
done < <(docker images --format '{{.Repository}}:{{.Tag}}' | grep -v '<none>')

echo "Images available at ${TARGET_REGISTRY}"
