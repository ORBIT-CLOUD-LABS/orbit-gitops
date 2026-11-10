# External Secrets Operator (Phase2)

작업: [#45](https://github.com/ORBIT-CLOUD-LABS/orbit-gitops/issues/45).
현재는 ESO 설치 Application과 Sync 정책을 작성·로컬 검증한 단계다.
운영 배포, Vault 연결 선언, ExternalSecret 동기화 검증은 아직 하지 않았다.

## 설치 선언

- Application: `clusters/orbit-k3s/apps/external-secrets.yaml`
- 프로젝트: `orbit-k3s-addons`
- chart: `external-secrets` **2.14.0**, appVersion **v2.14.0**
- chart 저장소: `https://charts.external-secrets.io` (공식 index로 리다이렉트)
- Helm release: `external-secrets`
- namespace / controller SA: `external-secrets/external-secrets`
- controller, webhook, cert-controller의 이미지는 동일한 OCI index digest로 고정:
  `sha256:10608eb53e636e744903d5f3657a4d9c44e28d9d9c181b73e07bc7dd2e6884dc`
- 세 Deployment는 control-plane 라벨이 없는 노드에만 배치한다.
  워커 역할 라벨이나 control-plane toleration은 사용하지 않는다.
- Sync 정책: [sync-policy.md](sync-policy.md)

공식 chart index와 [릴리스](https://github.com/external-secrets/external-secrets/releases/tag/helm-chart-2.14.0)를
2026-11-10 확인해 버전을 선정했다. chart archive SHA256은
`0a6d9e91b1ff50adfdbf24b50b582babfa7c5b7df42b21974ca4b3fb88ee5e34`다.
GHCR의 v2.14.0 manifest digest를 조회했으며 linux/amd64와 linux/arm64가 포함되어 있다.

## 확정한 Fluent Bit 연결 값

| 항목 | 값 |
| --- | --- |
| Fluent Bit namespace | `fluent-bit` |
| ExternalSecret / 생성 Secret 이름 | `fluent-bit-elasticsearch` |
| 생성 Secret 키 | `password` |
| Vault 원본 | `secret/orbit/k3s/fluent-bit` (KV v2) |
| `remoteRef.key` / `property` | `orbit/k3s/fluent-bit` / `password` |

namespace 생성과 AppProject 대상 허용은 orbit-infrastructure에서 관리한다.
로컬 infrastructure 코드의 `argocd_addons_namespaces`에 `external-secrets`와
`fluent-bit`가 포함된 것을 확인했다. 운영 적용 여부는 배포 전에 별도로 확인한다.
ClusterSecretStore를 추가할 때에도 `fluent-bit`를 사용 허용 namespace에 명시한다.

## 렌더링 확인 (2026-11-10)

Application의 `spec.source.helm.valuesObject`를 values 파일로 추출해 Helm 3.19.0으로
실제 렌더링했다. 결과 파일과 다운로드한 도구는 `/private/tmp`에만 두며 Git에 넣지 않는다.

```bash
# 저장소 루트. Ruby YAML로 Application에 실제 작성한 values를 추출한다.
ruby -ryaml -e 'app = YAML.load_file("clusters/orbit-k3s/apps/external-secrets.yaml"); puts app.fetch("spec").fetch("source").fetch("helm").fetch("valuesObject").to_yaml' > /tmp/orbit-eso-values.yaml
curl --fail --location --output /tmp/orbit-external-secrets-2.14.0.tgz \
  https://github.com/external-secrets/external-secrets/releases/download/helm-chart-2.14.0/external-secrets-2.14.0.tgz
helm template external-secrets /tmp/orbit-external-secrets-2.14.0.tgz \
  --namespace external-secrets --kube-version 1.35.9 --include-crds \
  -f /tmp/orbit-eso-values.yaml
kubectl kustomize clusters/orbit-k3s/apps
```

- `helm template`, `helm lint`, `kubectl kustomize`, `git diff --check` 통과.
- Deployment 3개, ServiceAccount 3개, Service 1개, Role/RoleBinding 각 1개.
- 클러스터 리소스: CRD 25개, ClusterRole 5개, ClusterRoleBinding 2개,
  ValidatingWebhookConfiguration 2개. 현재 AppProject가 허용하는 종류에 포함된다.
- controller ClusterRole에 `serviceaccounts/token`의 `create` 권한이 있고,
  controller Deployment의 SA 이름은 `external-secrets`다.
  Vault TokenReview용 `system:auth-delegator` binding은 후속 연결 선언에서 추가한다.
- 세 Deployment 모두 고정 digest와 control-plane 제외 affinity를 사용한다.
- chart는 webhook 인증서를 담을 빈 Secret 1개를 렌더링한다.
  이 Secret은 cert-controller가 채우는 내부 TLS용이며 Vault 앱 비밀값이 아니다.
  Git에는 렌더링 결과나 인증서 개인키를 저장하지 않는다.
- ClusterSecretStore와 SecretStore CRD의 JSON 크기는 각각 365,268 / 365,221 bytes로
  262,144 bytes를 초과한다. 따라서 ESO Application은 server-side apply를 사용한다.
- 서버 측 dry-run, 실제 노드 배치와 ESO Ready 여부는 아직 검증하지 않았다.

## 다음 구현

1. `addons/external-secrets/`에 공개 Vault CA ConfigMap, 정식 TokenReview RBAC,
   namespace 사용 범위를 제한한 ClusterSecretStore와 배포 Application을 추가한다.
2. `fluent-bit` namespace에 위 표의 ExternalSecret과 배포 연결을 추가한다.
3. 전체 선언을 한 PR로 검토한다. 첫 배포는 ESO·CRD·webhook → Store Ready →
   ExternalSecret Ready 순으로 확인한다. Application 간 wave만으로 준비를 가정하지 않는다.
4. 가짜 값으로 재생성·갱신·실패 중 기존 Secret 유지 시험을 하고 실제 적용 기록을 남긴다.

아직 연결 선언이 없으므로 이 단계만 배포해도 Fluent Bit 비밀번호는 생성되지 않는다.
