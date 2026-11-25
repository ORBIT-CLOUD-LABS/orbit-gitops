#!/usr/bin/env bash
# 서비스 overlay(ota/main, ota/sub, cdn/...)마다 렌더링하고 검사한다.
#   1. kustomize build
#   2. kubeconform -strict (Kubernetes 1.35.9 스키마, CRD는 CRDs-catalog 스키마)
#   3. check_manifests.py (CPU·메모리 requests·limits, 이미지 버전@digest)
# 한 overlay가 실패해도 나머지를 끝까지 검사하고, 하나라도 실패하면 종료 코드 1.
# 필요한 도구: kustomize, kubeconform, python3(PyYAML). 저장소 루트에서 실행한다.
set -euo pipefail

KUBERNETES_VERSION="1.35.9"
# CRD 스키마(ExternalSecret, Application 등). 커밋을 고정해 결과가 바뀌지 않게 한다.
CRDS_CATALOG="https://raw.githubusercontent.com/datreeio/CRDs-catalog/04af58d740718c4dc719441bf39fb284c784f4a8/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json"
SERVICE_DIRS=(ota cdn)

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT

overlays=()
for service in "${SERVICE_DIRS[@]}"; do
  [ -d "$service" ] || continue
  for dir in "$service"/*/; do
    dir="${dir%/}"
    [ "$(basename "$dir")" = "base" ] && continue
    [ -f "$dir/kustomization.yaml" ] || continue
    overlays+=("$dir")
  done
done

if [ "${#overlays[@]}" -eq 0 ]; then
  echo "검사할 overlay가 없습니다 (${SERVICE_DIRS[*]} 아래 base 외 kustomization.yaml 없음)."
  exit 0
fi

failed=()
for overlay in "${overlays[@]}"; do
  echo "::group::$overlay"
  rendered="$work_dir/$(echo "$overlay" | tr '/' '_').yaml"
  ok=true
  if ! kustomize build "$overlay" > "$rendered"; then
    echo "kustomize build 실패: $overlay"
    ok=false
  else
    kubeconform -strict -summary \
      -kubernetes-version "$KUBERNETES_VERSION" \
      -schema-location default \
      -schema-location "$CRDS_CATALOG" \
      "$rendered" || ok=false
    python3 "$script_dir/check_manifests.py" "$rendered" || ok=false
  fi
  echo "::endgroup::"
  if [ "$ok" = true ]; then
    echo "통과: $overlay"
  else
    echo "실패: $overlay"
    failed+=("$overlay")
  fi
done

if [ "${#failed[@]}" -gt 0 ]; then
  echo "실패한 overlay: ${failed[*]}"
  exit 1
fi
echo "모든 overlay 통과: ${overlays[*]}"
