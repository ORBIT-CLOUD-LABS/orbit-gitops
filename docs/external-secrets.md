# External Secrets Operator (Phase2)

작업: [#45](https://github.com/ORBIT-CLOUD-LABS/orbit-gitops/issues/45).
현재는 ESO 설치 Application, Sync 정책, Vault 연결 선언, Fluent Bit용 ExternalSecret을 작성·로컬 검증한 단계다.
운영 배포와 ExternalSecret 동기화 검증은 아직 하지 않았다.

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
  Vault TokenReview용 `system:auth-delegator` binding은 아래 Vault 연결 선언에서 관리한다.
- 세 Deployment 모두 고정 digest와 control-plane 제외 affinity를 사용한다.
- chart는 webhook 인증서를 담을 빈 Secret 1개를 렌더링한다.
  이 Secret은 cert-controller가 채우는 내부 TLS용이며 Vault 앱 비밀값이 아니다.
  Git에는 렌더링 결과나 인증서 개인키를 저장하지 않는다.
- ClusterSecretStore와 SecretStore CRD의 JSON 크기는 각각 365,268 / 365,221 bytes로
  262,144 bytes를 초과한다. 따라서 ESO Application은 server-side apply를 사용한다.
- 서버 측 dry-run, 실제 노드 배치와 ESO Ready 여부는 아직 검증하지 않았다.

## Vault 연결 선언

`orbit-k3s-external-secrets-vault` Application이 `develop`의
`addons/external-secrets/`를 Kustomize로 읽는다. 프로젝트는 `orbit-k3s-addons`,
대상 namespace는 `external-secrets`다. ESO 설치 Application과 별도로 관리한다.

| 리소스 | 이름 | 역할 |
| --- | --- | --- |
| ConfigMap | `external-secrets/vault-ca` | Vault HTTPS 서버 검증용 공개 CA |
| ClusterRoleBinding | `orbit-eso-vault-auth` | 정식 ESO SA에 `system:auth-delegator` 부여 |
| ClusterSecretStore | `orbit-vault` | Vault 연결·Kubernetes 인증·사용 namespace 제한 |

- Vault: `https://10.0.0.201:8200`, KV `path: secret`, `version: v2`.
- 인증: `mountPath: kubernetes`, 역할 `eso`, SA `external-secrets/external-secrets`,
  audience `https://kubernetes.default.svc.cluster.local`.
- `conditions.namespaces`는 `fluent-bit`만 허용한다. 다른 앱을 추가할 때는 해당
  namespace를 검토 후 명시적으로 추가한다. ESO가 실행되는 `external-secrets`
  namespace를 Store 사용 대상으로 추가할 필요는 없다.
- Vault 정책의 실제 읽기 범위는 `secret/orbit/k3s/*`다. Store의 namespace 제한은
  이 Vault 정책을 대체하지 않으며, 허용된 namespace별 Vault 경로 격리를 제공하지 않는다.
- 토큰 Secret이나 `secretRef`를 만들지 않는다. chart의 TokenRequest 권한으로
  단기 SA 토큰을 발급한다. Vault가 로그인 JWT로 TokenReview를 수행하는 현재 구성에
  맞춰 위 정식 binding을 사용하며 시험용 binding은 재사용하지 않는다.

### 공개 CA 확인 (2026-11-10)

astra에 개인 계정으로 SSH 접속해 `/opt/vault/tls/vault-ca.crt`만 읽어
`vault-ca.yaml`에 담았다. CA 개인키와 Vault 토큰은 읽거나 저장하지 않았다.

- subject / issuer: `CN=ORBIT Vault CA`.
- SHA256 지문:
  `AF:3D:80:14:5A:15:7A:09:09:C1:C7:80:63:2C:AC:95:8D:B7:A5:B1:B0:61:BC:60:86:C4:52:62:6E:EB:51:2C`.
- 유효 기간: 2026-11-01 17:37:24 UTC ~ 2036-10-29 17:37:24 UTC.
- ConfigMap에서 추출한 인증서의 지문과 astra 원본의 지문이 일치하며,
  `openssl verify`로 CA 자체 서명 검증에 성공했다.
- astra에서 원본 CA를 사용한 `https://10.0.0.201:8200/v1/sys/health` HTTPS 조회에
  성공했다. 당시 `initialized=true`, `sealed=false`, `standby=false`였다.
  ESO 파드에서의 접속·로그인은 아직 확인하지 않았다.

### 선언 검증과 첫 배포

- `kubectl kustomize addons/external-secrets`와 `kubectl kustomize clusters/orbit-k3s/apps` 통과.
- `kubeconform -strict -kubernetes-version 1.35.9`로 연결 리소스 3개 검증 통과.
  ClusterSecretStore에는 chart 2.14.0 CRD의 `v1` 스키마를 별도로 제공했다.
- 자식 Application 2개는 Argo CD v3.5.6 Application CRD 스키마로 검증 통과.
- SA·audience·역할을 infrastructure 변수와 대조했고, CA 참조와 binding subject,
  Store 사용 namespace가 서로 일치하는지 확인했다.
- Vault 연결 Application에는 `SkipDryRunOnMissingResource=true`를 사용한다.
  ESO CRD가 아직 없을 때 dry-run만 건너뛰며 실제 적용 실패를 무시하지 않는다.
  별도 Application 간 순서나 Ready 완료를 보장하는 옵션은 아니다.

첫 배포는 두 Application을 함께 생성할 수 있다. ESO의 controller·webhook·cert-controller가
준비되기 전에 Store 적용이 실패하면 제한된 재시도가 동작한다. 재시도를 소진했으면
ESO 준비 후 해당 Application을 다시 Sync한다. kubectl로 별도 apply하지 않아도 된다.

```bash
# polaris에서 운영 배포 후 실행. Secret 값이나 토큰은 출력하지 않는다.
sudo k3s kubectl -n argocd get applications
sudo k3s kubectl -n external-secrets rollout status deployment/external-secrets --timeout=300s
sudo k3s kubectl -n external-secrets rollout status deployment/external-secrets-webhook --timeout=300s
sudo k3s kubectl -n external-secrets rollout status deployment/external-secrets-cert-controller --timeout=300s
sudo k3s kubectl wait --for=condition=Ready clustersecretstore/orbit-vault --timeout=300s
```

서버 측 dry-run과 위 운영 배포 후 확인 명령은 아직 실행하지 않았다.

## Fluent Bit ExternalSecret

`orbit-k3s-fluent-bit-secrets` Application은 `develop`의 `addons/fluent-bit/secrets/`를
배포한다. namespace는 `fluent-bit`, 프로젝트는 `orbit-k3s-addons`다.
#45에서 비밀값 동기화를 먼저 구성하며, Fluent Bit 본체는 #46에서 배포한다.
#46의 다른 Application에서 이 ExternalSecret을 중복 관리하지 않는다.

- ExternalSecret과 생성할 Secret의 이름은 모두 `fluent-bit-elasticsearch`.
- `ClusterSecretStore/orbit-vault`를 통해 `orbit/k3s/fluent-bit`의 `password`를
  Secret 키 `password`에 명시적으로 매핑한다. `dataFrom`으로 다른 키를 가져오지 않는다.
- `refreshPolicy: Periodic`, `refreshInterval: 1m`으로 원본 변경을 주기적으로 반영한다.
- `creationPolicy: Owner`로 Secret을 생성·관리한다. Secret 삭제 시 ESO가 재생성하며,
  **ExternalSecret 자체를 삭제하면 ownerReference에 의해 Secret도 삭제될 수 있다.**
- `deletionPolicy: Retain`은 Vault 원본 삭제 시 기존 Secret을 유지하는 정책이다.
  ExternalSecret 삭제까지 보호하는 설정은 아니다. 관련 [ESO 정책 문서](https://external-secrets.io/latest/guides/ownership-deletion-policy/).
- Vault 접근 오류나 원본 누락 시 Ready 오류를 확인한다. 처음부터 원본이 없으면
  Secret은 만들어지지 않으며, 재시도로 원본을 만들어 주지는 않는다.
- 실제 password 값은 Git이나 검증 출력에 담지 않는다. Vault 원본의 존재·필수 키는
  배포 전에 권한 있는 운영자가 값을 출력하지 않는 방식으로 확인한다.

### #46에서 사용

Fluent Bit 파드는 같은 `fluent-bit` namespace에서 다음과 같이 비밀번호를 참조한다.
선정한 chart의 환경변수 설정 키에 맞춰 이 참조를 넣고, Elasticsearch 출력의
`HTTP_Passwd`에서 `${ELASTICSEARCH_PASSWORD}`를 사용한다.

```yaml
# Fluent Bit 컨테이너의 env 예시. chart values 필드명은 #46에서 선정 버전과 대조한다.
env:
  - name: ELASTICSEARCH_PASSWORD
    valueFrom:
      secretKeyRef:
        name: fluent-bit-elasticsearch
        key: password
```

Secret을 환경변수(`env`, `envFrom`)로 읽는 기존 파드는 Secret 갱신만으로 환경변수가
바뀌지 않는다. 비밀번호 변경 후 Fluent Bit 파드를 재시작해야 새 값을 사용한다.
자동 재시작 도입은 #45 범위에 포함하지 않는다.

### 로컬 검증과 운영 확인

`kubectl kustomize addons/fluent-bit/secrets` 렌더링과 chart 2.14.0의
ExternalSecret `v1` CRD 스키마 검사를 통과했다. root 묶음의 자식 Application 3개도
Argo CD v3.5.6 Application CRD 스키마 검사를 통과했다.
Store 이름, namespace 허용 범위, Secret 이름·키와 주기·소유·삭제 정책을 대조했다.
서버 측 dry-run과 아래 명령은 아직 실행하지 않았다.

```bash
# polaris에서 운영 배포 후 실행. data 값 대신 Ready와 키 이름만 확인한다.
sudo k3s kubectl -n fluent-bit wait --for=condition=Ready externalsecret/fluent-bit-elasticsearch --timeout=300s
sudo k3s kubectl -n fluent-bit get externalsecret fluent-bit-elasticsearch \
  -o jsonpath='{range .status.conditions[*]}{.type}={.status} {.reason}{"\n"}{end}'
sudo k3s kubectl -n fluent-bit get secret fluent-bit-elasticsearch \
  -o go-template='{{.metadata.namespace}}/{{.metadata.name}}{{"\n"}}{{range $key, $value := .data}}{{$key}}{{"\n"}}{{end}}'
```

## 남은 작업

1. 전체 선언을 한 PR로 검토한다. 첫 배포는 ESO·CRD·webhook → Store Ready →
   ExternalSecret Ready 순으로 확인한다. Application 간 wave만으로 준비를 가정하지 않는다.
2. 가짜 값으로 재생성·갱신·실패 중 기존 Secret 유지 시험을 하고 실제 적용 기록을 남긴다.
3. chart/CRD 업그레이드, CA 교체, 복구·롤백·삭제 절차를 정리한다.

아직 운영 배포 전이며, 실제 Fluent Bit Secret 생성·갱신은 확인하지 않았다.
