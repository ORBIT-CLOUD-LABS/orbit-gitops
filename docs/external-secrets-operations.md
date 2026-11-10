# ESO 운영 절차

대상 선언과 고정 버전은 [external-secrets.md](external-secrets.md), 자식 Application
정책은 [sync-policy.md](sync-policy.md)를 따른다. 아래 절차는 작성한 운영 지침이며
**실제 배포·장애 시험·업그레이드·복원·삭제를 실행한 기록이 아니다.**

## 첫 배포와 확인

1. infrastructure에서 Argo CD, root, AppProject와 `external-secrets`·`fluent-bit`
   namespace가 운영에 적용되어 있는지 확인한다. 새 namespace를 GitOps에서 만들지 않는다.
2. Vault가 unseal되어 있고 워커에서 `10.0.0.201:8200`, Vault에서 k3s API
   `10.0.0.200:6443`으로 접속 가능해야 한다. Kubernetes 인증의 CA는 현재 클러스터
   CA여야 하고, `eso` 역할의 SA·namespace·audience가 선언과 같아야 한다.
3. 권한 있는 운영자가 Vault `secret/orbit/k3s/fluent-bit`의 `password` 존재를
   확인한다. 값을 출력하거나 Git·Issue·PR·채팅·로그에 복사하지 않는다.
4. 검토된 PR을 `develop`에 머지하면 root가 자식 Application 3개를 생성한다.
   push만으로는 root가 작업 브랜치를 읽지 않는다.
5. ESO rollout → Store `Ready=True` → ExternalSecret `Ready=True`/`SecretSynced` →
   생성 Secret의 namespace·이름·필수 키를 [확인 명령](external-secrets.md#로컬-검증과-운영-확인)으로 확인한다.
   Secret의 `data` 전체나 디코딩한 값을 출력하지 않는다.
6. 첫 동기화에서 CRD 또는 webhook 준비 전 오류로 재시도를 소진할 수 있다.
   원인을 해결하고 해당 Application만 다시 Sync한다. 정상화되기 전까지 완료로 기록하지 않는다.

CRD가 실제 클러스터에 준비된 뒤, 저장소 루트의 현재 선언으로 아래 dry-run을 실행한다.
연결 선언은 ESO·webhook 준비 후, ExternalSecret은 Store Ready 확인 후 검사한다.
`kubectl`이 대상 클러스터를 가리키는 환경에서 실행하며 일반 Secret 값은 포함하지 않는다.

```bash
kubectl kustomize addons/external-secrets | kubectl apply --dry-run=server -f -
kubectl kustomize addons/fluent-bit/secrets | kubectl apply --dry-run=server -f -
```

## 장애 확인

| 증상 | 확인할 대상 |
| --- | --- |
| Argo CD `ComparisonError` | 저장소 URL·develop 경로·chart 버전·렌더링 오류 |
| `resource ... is not permitted` | infrastructure AppProject의 namespace·리소스 허용 범위 |
| CRD 없음 / webhook 접속 실패 | ESO Application Sync, CRD Established, webhook rollout과 Service endpoints |
| Store `Ready=False`, TLS 오류 | 공개 CA, Vault 서버 인증서 SAN·유효 기간, 워커→Vault 연결 |
| Vault 로그인 거부 | `eso` 역할, SA·namespace·audience, TokenRequest와 TokenReview 권한, Vault의 k3s CA |
| Store Ready인데 ExternalSecret 오류 | Store 사용 namespace, Vault 경로·property, `eso-orbit` 읽기 정책 |
| Secret 갱신 후 Fluent Bit 인증 실패 | Elasticsearch의 실제 계정 비밀번호와 Vault 값 일치 여부, 기존 파드 재시작 여부 |

오류 메시지·Ready 상태부터 확인한다. 조사 목적으로 운영 Vault를 seal하거나 중단하지
않는다. 일반 Secret이나 토큰을 덤프하지 않는다. 기존 Secret이 있어도 원본 접근 실패가
계속되면 자동 갱신·재생성이 불가능하므로, Secret 존재만으로 정상이라고 판단하지 않는다.

## chart·CRD 업그레이드

1. 새 ESO 릴리스의 변경·업그레이드 안내와 지원 API를 확인한다. 현재 사용하는
   `external-secrets.io/v1`과 기존 리소스의 저장 버전이 새 CRD에서 유지되는지 본다.
   버전 제거·변환이 필요하면 해당 릴리스의 마이그레이션 절차를 먼저 따른다.
2. `external-secrets.yaml`의 chart `targetRevision`과 controller·webhook·cert-controller
   이미지 digest 3개를 함께 바꾼다. 이미지 tag만 바꾸고 기존 digest를 남기지 않는다.
3. Application에서 실제 values를 추출해 고정 chart로 `helm template --include-crds`와
   `helm lint`를 실행한다. 새 클러스터 리소스나 namespace가 생기면 infrastructure의
   AppProject 허용 범위를 먼저 검토·반영한다.
4. 이전 렌더링과 CRD의 served/storage 버전·스키마·webhook·RBAC를 비교한다.
   새 스키마로 기존 Store·ExternalSecret 선언도 검사한다. CRD에는 server-side apply를 유지한다.
5. PR 머지 후 ESO Sync와 rollout, Store/ExternalSecret Ready 및 Secret 필수 키를
   확인한다. 가짜 값 전용 시험에서 갱신까지 확인하고 실제 수행한 결과만 기록한다.

## 공개 Vault CA 교체

Vault TLS CA와 k3s API CA는 서로 다르다. `vault-ca.yaml`은 **Vault HTTPS 서버**용이다.
k3s 재설치로 바뀐 API CA는 Vault의 `auth/kubernetes/config`에서 갱신해야 한다.

1. 새 공개 CA를 신뢰할 수 있는 경로로 확보하고 지문·유효 기간·CA 속성을 검증한다.
   개인키는 복사하지 않는다. 기존 Vault 서버가 아직 사용 중이면 ConfigMap의
   `vault-ca.crt`에 기존·새 CA를 함께 넣는 전환용 PEM bundle을 먼저 배포한다.
2. CA ConfigMap의 Git 변경을 Sync하고 운영 값의 인증서 지문을 확인한다.
   원본 Vault CA를 교체하는 작업은 infrastructure 절차에서 진행한다.
3. 새 CA로 서명된 Vault 서버 인증서로 전환한 뒤 Store Ready와 새로운 동기화 성공을
   확인한다. 기존 Ready 상태만 보지 말고 전환 이후 갱신도 확인한다.
4. TLS 오류가 계속되면 ConfigMap 참조와 ESO의 CA 재로딩 여부를 확인한다.
   필요한 경우 ESO controller를 재시작해 새 CA로 연결하는지 확인한다.
5. 이전 CA가 더 이상 필요 없음을 확인한 뒤 bundle에서 제거하고 다시 검증한다.
   Vault 서버 인증서 자체만 갱신하고 서명 CA가 같다면 CA ConfigMap 변경은 필요하지 않다.

## 롤백

Argo CD는 Helm을 렌더링 도구로 사용하므로 이 배포의 롤백에 `helm rollback`을 쓰지 않는다.
자동 Sync 상태에서는 직접 롤백보다 Git 선언을 정상 버전으로 되돌리는 방법을 사용한다.
[Argo CD 자동 Sync 문서](https://argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/).

1. 마지막 정상 chart 버전·이미지 digest·연결 선언을 확인한다. Git의 검증 기록을 사용하며
   일반 Secret 값을 Git에 백업하지 않는다.
2. CRD가 바뀌었다면 이전 controller가 현재 CRD 및 저장된 리소스와 호환되는지 먼저 확인한다.
   호환되지 않으면 단순한 chart downgrade로 해결하지 말고 수정 버전 적용이나 공식
   마이그레이션 절차를 따른다. CRD를 삭제해 되돌리지 않는다.
3. 정상 Git 선언으로 되돌리는 PR을 머지하고 다시 Sync한다. 긴급히 자동 동기화를
   멈출 때는 해당 자식의 Git 선언에 `automated.enabled: false`를 반영한다.
   root만 멈춰서는 자식이 멈추지 않는다. 진행 중인 Sync는 별도로 상태를 확인하고
   필요하면 종료해야 하며, 자동 Sync를 끄는 것만으로 취소되지는 않는다.
4. Ready·갱신 성공 확인 후 자동 Sync를 다시 켠다. ConfigMap이나 Store를 되돌려도
   Vault·Elasticsearch의 실제 비밀번호는 되돌아가지 않는다. 비밀번호 복구는 해당
   원본 시스템과 Vault를 함께 맞춘 뒤 소비 파드를 재시작한다.

## 클러스터 재구축과 Secret 복구

1. infrastructure에서 k3s·Cilium·Argo CD·namespace·AppProject·root를 복구한다.
   API CA가 바뀌었다면 Vault Kubernetes 인증의 CA도 갱신한다.
2. Vault 원본이 유지되어 있고 unseal·네트워크·정책·인증·CA가 준비됐는지 확인한다.
   Vault 자체 데이터를 잃었다면 먼저 infrastructure의 Vault 복원 절차를 따른다.
3. root로 자식 Application을 다시 생성하고 ESO → Store → ExternalSecret 순으로
   Ready를 확인한다. Secret은 ESO가 원본에서 재생성하므로 수동으로 만들지 않는다.
4. Secret만 실수로 삭제한 경우 ExternalSecret과 Vault 연결을 유지한 상태에서
   ESO 재생성을 확인한다. 실제 비밀번호로 삭제 시험하지 말고 아래 가짜 값 시험을 사용한다.
5. 환경변수로 Secret을 읽는 파드는 복구 후 필요에 따라 재시작하고 실제 접속도 확인한다.

## 삭제 영향과 순서

| 작업 | 영향 |
| --- | --- |
| Git에서 선언 제거 | Prune이 꺼져 있어 기존 리소스는 자동 삭제되지 않음 |
| finalizer 없는 Application만 삭제 | 배포한 리소스가 자동 연쇄 삭제되지 않음 |
| ExternalSecret 삭제 | `creationPolicy: Owner` 때문에 생성 Secret도 GC될 수 있음 |
| Vault 원본 삭제 | `deletionPolicy: Retain`으로 기존 Secret 유지, 동기화 오류 발생 |
| Store·CA·인증 binding 제거 | 기존 Secret이 남아도 갱신·재생성 실패 |
| ESO 제거 | 기존 Secret이 남아도 갱신·재생성 중단 |
| ExternalSecret CRD 제거 | 해당 CR 전체 삭제, 생성 Secret도 ownerReference로 삭제될 수 있음 |
| `fluent-bit` namespace 삭제 | Fluent Bit과 ExternalSecret·Secret 모두 삭제 |

Application의 연쇄 삭제 동작은 [Argo CD 삭제 문서](https://argo-cd.readthedocs.io/en/stable/user-guide/app_deletion/)를 따른다.
Prune 비활성화는 수동 삭제나 Kubernetes ownerReference GC를 막지 않는다.

완전히 제거할 때는 다음 순서로 진행한다.

1. 소비자(Fluent Bit 등)를 중단하거나 대체 비밀값 공급 방식으로 전환한다.
2. root와 해당 자식의 자동 Sync·진행 중 Sync를 통제한다. Git에서 Application과
   대상 선언을 제거하고 root 재조정으로 다시 생성되지 않을 상태를 만든다.
   root의 Prune도 꺼져 있으므로 기존 자식은 별도로 정리해야 한다.
3. Secret 삭제까지 포함한 영향 확인 후 ExternalSecret을 삭제하고 생성 Secret 정리를 확인한다.
   Secret을 보존해야 한다면 이 절차 대신 소유권 이전 계획을 먼저 마련한다.
4. 다른 사용자가 없는지 확인한 뒤 Store·CA ConfigMap·정식 인증 binding을 제거한다.
5. 다른 ESO 사용자가 전혀 없을 때만 ESO 설치 리소스를 정리한다. chart에 포함된
   webhook·클러스터 RBAC도 대상 목록을 확인해 정리한다. 제거한 webhook이 계속
   API 요청을 막지 않도록 관련 ValidatingWebhookConfiguration 잔존 여부를 확인한다.
6. CRD 삭제는 기본 제거 절차에 포함하지 않는다. 모든 namespace의 관련 CR과
   ownerReference 영향을 조사한 뒤 별도로 결정한다. 운영 Vault 원본은 자동 삭제하지 않는다.

## 가짜 값 시험과 기록

운영 Fluent Bit 비밀번호와 분리된 `orbit/k3s/` 아래 임시 Vault 경로, `fluent-bit`
namespace 안의 고유 이름 ExternalSecret·Secret을 사용한다. 정식 ESO SA·binding·Store는
유지하고, 실패 시험에 필요하면 고유 이름 시험 Store만 추가한다.

| 시험 | 확인할 결과 |
| --- | --- |
| 최초 동기화 | Ready=True와 지정 키 생성 |
| 시험 Secret만 삭제 | ExternalSecret이 유지된 상태에서 Secret 재생성 |
| 시험 Vault 경로의 한 키 `patch` | 해당 키 갱신, 원본의 다른 키 보존 |
| 시험 Store의 잘못된 인증 역할·접근 경로 | 시험 ExternalSecret 오류와 기존 시험 Secret 유지 |
| 정상 설정 복원 | Ready=True와 동기화 재개 |
| Store 사용 불허 namespace | 해당 Store 사용 거부 |

가짜 값 비교도 일치 여부만 출력한다. 시험 리소스를 고유 이름으로 기록해 두고,
종료 시 이번에 만든 것만 삭제한다. ExternalSecret·시험 Secret → 시험 Store →
시험 Vault 값 순으로 정리하며 정식 binding과 namespace는 삭제하지 않는다.
운영 Vault 중단·seal, 실제 Fluent Bit 비밀번호 변경은 시험에 사용하지 않는다.

적용 기록에는 날짜, Git SHA, chart·이미지 버전, 실제 실행한 명령과 성공·실패 원인,
Ready·키 확인·시험 결과·정리 결과를 남긴다. 아직 실행하지 않은 항목은 미실행으로 둔다.
