# #15 Nginx 자동 배포 검증 이력과 #19 정리

이 문서는 완료한 검증과 이후 정리 과정을 보존하는 기록이다.
[#19](https://github.com/ORBIT-CLOUD-LABS/orbit-gitops/issues/19) 작업 브랜치에서
테스트용 Application·Deployment·Service 선언 3개를 제거했다. main 반영과 실제 클러스터 삭제는
아직 수행하지 않았다. Git 파일 제거만으로 클러스터 리소스가 삭제되지는 않는다.

검증 당시 기존 `orbit-gitops-test` namespace에 임시 Nginx Deployment 1개와 ClusterIP Service를
배포했다. 외부 NodePort·Ingress·영구 스토리지·별도 Secret 선언은 사용하지 않았다.
원래 선언은 [#16 머지 커밋](https://github.com/ORBIT-CLOUD-LABS/orbit-gitops/tree/e4efc2515857d7bdc478e112cb52026ece799d6a/workloads/deploy-test)에서 확인할 수 있다.
아래 배포·복구 명령은 당시 검증 절차이며, 제거한 임시 앱을 다시 배포하기 위한 현재 운영 절차가 아니다.

## 당시 적용 전 확인 사항

- infrastructure #58의 root 자동 Sync·retry 설정을 대상 클러스터에 적용한다.
- root와 자식의 repoURL·targetRevision을 확인한다. 운영 선언은 모두 `main`이다.
  브랜치 검증에서는 root를 Ansible의 `argocd_gitops_revision`으로 전환하고,
  테스트 자식도 같은 브랜치를 읽게 해야 한다. root만 바꾸면 자식은 계속 main을 읽는다.
- root가 읽는 모든 자식 diff를 검토한다. 기존 smoke-test의 수동 정책은 유지한다.
- Prune·Self Heal 비활성화, retry limit 5 / 5s / factor 2 / maxDuration 3m을 확인한다.
- 당시 `deployment.yaml`에서 태그와 함께 멀티 아키텍처 index digest를 고정했다.

## 당시 최초 배포와 Git 변경 검증 절차

1. 리뷰된 선언을 main에 반영한다. root·자식의 수동 Refresh·Sync나 리소스 직접 apply 없이
   Application 생성과 Pod Ready를 기다린다. 시간 초과 시 conditions·operationState를 확인하고
   실패로 기록한다. 수동 Sync로 성공시켰다면 자동 배포 성공으로 기록하지 않는다.
2. 아래 조회로 root·자식 Sync/Health, 실제 적용 revision과 실행 이미지·imageID를 기록한다.

   ```bash
   git rev-parse HEAD
   kubectl -n argocd get application orbit-astra-root orbit-astra-deploy-test \
     -o custom-columns='NAME:.metadata.name,TARGET:.spec.source.targetRevision,REVISION:.status.sync.revision,SYNC:.status.sync.status,HEALTH:.status.health.status'
   kubectl -n argocd get application orbit-astra-deploy-test \
     -o jsonpath='{.status.conditions}{"\n"}{.status.operationState}{"\n"}'
   kubectl -n orbit-gitops-test rollout status deployment/gitops-deploy-test --timeout=180s
   kubectl -n orbit-gitops-test get pods -l app.kubernetes.io/name=gitops-deploy-test \
     -o custom-columns='NAME:.metadata.name,UID:.metadata.uid,READY:.status.containerStatuses[*].ready,IMAGE:.spec.containers[*].image,IMAGE_ID:.status.containerStatuses[*].imageID'
   ```

3. 대상 클러스터에 연결한 터미널에서 Service를 port-forward하고, 다른 터미널에서 HTTP 200과
   기본 Nginx 페이지를 확인한다. 결과를 남긴 뒤 port-forward를 종료한다.

   ```bash
   kubectl -n orbit-gitops-test port-forward service/gitops-deploy-test 18085:80
   ```

   ```bash
   curl --fail --silent --show-error -i http://127.0.0.1:18085/
   ```

4. `deployment.yaml`의 Pod template annotation `orbit.dev/deploy-test-revision`을
   `v1`에서 `v2`로 바꾸는 별도 Git 변경을 리뷰·반영한다. 이미지·Service는 유지한다.
5. 자식 `.status.sync.revision`이 새 커밋에 도달하고 Deployment의 Pod template annotation이
   `v2`가 될 때까지 확인한 다음 rollout 완료를 기다린다. 변경 감지 전에 `rollout status`만
   실행하면 이전 배포 성공을 읽을 수 있다.

   ```bash
   kubectl -n orbit-gitops-test get deployment gitops-deploy-test \
     -o go-template='{{index .spec.template.metadata.annotations "orbit.dev/deploy-test-revision"}}{{"\n"}}'
   ```

6. 새 ReplicaSet과 새 Pod UID·Ready, 적용 revision·이미지·HTTP 응답을 다시 기록한다.
   변경 전후 모두 수동 Sync 없이 완료됐는지 명시한다. 재시도 실패를 유발하지 않았다면
   retry는 설정 확인만 수행했다고 기록한다.

## 당시 복구와 중지 절차

문제가 생기면 변경 커밋을 Git revert하고, 새 revision의 자동 반영과 Pod·HTTP 복구를 확인한다.
배포를 중지하려면 자식의 `automated.enabled`를 Git에서 false로 바꾼다.
root 중지가 필요하면 infrastructure의 Ansible 원본을 변경·적용한다.
root만 중지해도 기존 자식 자동 Sync는 계속 동작한다.

## #19 정리 대상과 순서

| 종류 | 대상 |
| --- | --- |
| Git 파일 | `clusters/orbit-astra/apps/deploy-test.yaml` |
| Git 디렉터리 | `workloads/deploy-test/` (Deployment·Service) |
| Application | `argocd/orbit-astra-deploy-test` |
| Deployment | `orbit-gitops-test/gitops-deploy-test` (소유 ReplicaSet·Pod 포함) |
| Service | `orbit-gitops-test/gitops-deploy-test` |

이 목록은 #19에 등록했다. Git 정의를 먼저 제거하고 main에 반영한다. 운영 root가 삭제 커밋을 읽은 뒤
Prune 비활성으로 남은 위 Application·Deployment·Service만 명시적으로 삭제한다.
Application에 삭제 연쇄 finalizer가 없는지 먼저 확인한다. 정의가 남은 상태에서 리소스만
지우면 이후 Sync에서 다시 생성될 수 있다. Application 삭제만으로 워크로드는 제거되지 않는다.
운영·테스트 클러스터 각각에서 Application을 먼저 삭제해 자식 자동 배포를 중지한 뒤
Deployment·Service를 삭제한다. 소유 ReplicaSet·Pod·EndpointSlice도 제거되는지 확인한다.
임시 HTTP 서비스가 중단되며 영구 데이터 삭제는 없다. `orbit-gitops-test` namespace,
smoke-test, #52 테스트 리소스와 인증정보는 정리 대상에서 제외한다.

## 검증 기록

2026-10-15: ASTRA SSH 접속과 기존 #52 테스트 클러스터 상태를 조회했다.
Kubernetes v1.33.13 노드 3개가 Ready이며 root는 `task/52-auto-sync-test`를 읽고
자동 Sync 활성화, Synced / Healthy였다. 운영 클러스터 적용을 의미하지 않는다.
Nginx 공식 레지스트리에서 고정 digest와 linux/amd64 이미지 존재를 확인했다.
작성한 Deployment·Service·Application 각각을 테스트 클러스터에서
`kubectl apply --dry-run=server -f -`로 검증했고 모두 통과했다. 실제 리소스는 생성하지 않았다.
`git diff --check`도 통과했다.

### 테스트 브랜치 자동 배포·재배포 (2026-10-15)

대상은 ASTRA의 기존 libvirt 테스트망 `192.168.122.0/24`이며 운영 클러스터는 변경하지 않았다.
테스트용 Ansible 작업본에서 `inventory/test.ini`, `--tags argocd_gitops`,
`argocd_gitops_revision=task/15-deploy-test-auto-sync`로 적용했다.
실행 결과는 `ok=12 changed=1 unreachable=0 failed=0`이며 root 연결 revision만 변경됐다.
root와 테스트 자식 모두 `task/15-deploy-test-auto-sync`를 읽는다.

| 확인 항목 | 최초 배포 v1 | 재배포 v2 |
| --- | --- | --- |
| Git·자식 적용 revision | `abb0a29ec0c8d9b3253f0613fd70de8663e691cf` | `4c8693741b5e4bb9f3f0bb16db7233ab17b54209` |
| Pod template annotation | `v1` | `v2` |
| ReplicaSet | `gitops-deploy-test-84748584b9` | `gitops-deploy-test-57dc444888` |
| Pod | `gitops-deploy-test-84748584b9-z96zg` | `gitops-deploy-test-57dc444888-mpjv9` |
| Pod UID | `b3a5e3bb-619d-45bd-8467-5391cdf99bc9` | `179969e4-fc0d-4210-a2b8-cf369c542448` |
| Pod Ready | `1/1` | `1/1` |
| Application | Synced / Healthy | Synced / Healthy |
| Service HTTP | 200, 기본 Nginx 페이지 | 200, 기본 Nginx 페이지 |

v1은 17:23:51, v2는 17:25:51 (KST)에 테스트 control-plane에서
Service ClusterIP `10.103.154.30:80`으로 직접 요청해 확인했다.
노드 호스트에서 Service DNS 이름은 해석되지 않아 ClusterIP로 요청했다.
Pod 내부 DNS 동작과 port-forward 경로를 검증한 결과는 아니다.

이미지는 전후 모두 `nginx:1.30.6-alpine`이며 선언 digest와 실행 imageID는
`sha256:ff8328b4279ec385af48cde9ef486e7165ad74b7065cb3cd86c377384e2e2dd5`로 같았다.
v2의 새 ReplicaSet은 1/1 Ready, 기존 ReplicaSet은 0/0으로 축소됐고
`kubectl rollout status`가 성공했다. 자식 operation은 17:25:32 (KST)에
`initiatedBy.automated: true`, `phase: Succeeded`였다.
수동 Refresh·Sync, Deployment 직접 apply, rollout restart는 실행하지 않았다.

root 자동 Sync도 성공했으나 기존 `orbit-issue52-test`가 새 브랜치에 없어
`requiresPruning: true`로 남아 root는 OutOfSync / Healthy다. Prune 비활성 정책에 따라
이전 테스트 Application과 리소스를 삭제하지 않았다. 기존 smoke-test도 수동 정책을 유지했다.
재시도는 설정만 확인했으며 실패 유발·재시도 소진 동작은 이번에 검증하지 않았다.

### 검증 종료와 머지 준비 (2026-10-15)

테스트 root를 Ansible로 먼저 `task/52-auto-sync-test`에 복구했다.
실행 결과는 `ok=12 changed=1 unreachable=0 failed=0`, root의 자동 Sync operation은
Succeeded였다. 이후 Git의 테스트 자식 선언은 `targetRevision: main`으로 되돌렸다.
Prune 비활성으로 `orbit-astra-deploy-test`는 `requiresPruning: true`로 남아
root는 OutOfSync / Healthy다. 잔여 테스트 자식은 기존 #15 브랜치 연결을 유지하며,
Git 선언을 main으로 되돌려도 복구된 #52 root는 이 자식 정의를 관리하지 않는다.
후속 정리에서 잔여 Application·Deployment·Service를 명시적으로 제거한다.
이 시점에 Git revert 복구와 리소스 정리는 실행하지 않았다. 후속 정리 이슈는 이후 #19로 등록했다.

### main 반영 후 운영 클러스터 확인 (2026-10-15)

PR #16 머지 후 운영 클러스터(`astra-control-plane`, `192.168.100.101`)에서
수동 Refresh·Sync 없이 `e4efc2515857d7bdc478e112cb52026ece799d6a`가 적용됐다.
root·자식 모두 Synced / Healthy이며 자식 operation은 17:42:33 (KST)에
`initiatedBy.automated: true`, `phase: Succeeded`였다.

Pod `gitops-deploy-test-57dc444888-xknk2`의 UID는
`802fc4f7-20d7-42c2-9ac0-47db581aef4b`이며 1/1 Ready, 재시작 0회였다.
실행 imageID는 테스트 때와 동일한 고정 digest였다.
17:43:45 (KST)에 운영 control-plane에서 Service ClusterIP `10.101.216.173:80`으로 요청해
HTTP 200과 기본 Nginx 페이지를 확인했다.

### #19 삭제 전 확인과 진행 상태 (2026-10-15)

운영(`192.168.100.101`, 노드 4개)과 테스트(`192.168.122.10`, 노드 3개)를 각각 조회했다.
두 클러스터의 kube-system namespace UID가 서로 다름을 확인해 대상을 구분했다.
양쪽 모두 대상 Application·Deployment·Service에 finalizer가 없고, Deployment·Service의
Argo CD tracking-id가 `orbit-astra-deploy-test`를 가리켰다.
ReplicaSet→Deployment, Pod→ReplicaSet, EndpointSlice→Service 소유 관계도 확인했다.
대상 Pod에는 API 접근용 projected 볼륨만 있으며 PVC를 사용하지 않았다.

조회한 다른 Application의 관리 리소스, 워크로드·ConfigMap·Ingress·NetworkPolicy에서
대상 이름 참조를 찾지 못했고, 다른 Service가 대상 Pod를 함께 선택하지 않았다.
이는 조회 범위의 결과이며 클러스터 밖 클라이언트 참조까지 확인한 것은 아니다.

테스트 자식은 기존 #15 브랜치를 commit SHA로 해석하지 못해 ComparisonError / Sync Unknown,
Health Healthy였다. 테스트 root는 기존 #52 브랜치를 유지하며 잔여 자식 때문에 OutOfSync였다.
운영 root·자식·CDN·smoke-test와 테스트 #52 앱의 상태 및 정리 제외 대상을 확인했다.

- 완료: 삭제 대상·소유 관계·finalizer·참조 확인, 작업 브랜치의 YAML 3개 제거, README와 이력 문서 정리.
- 대기: 정리 PR 생성·main 반영, 운영 root의 삭제 커밋 확인, 양쪽 클러스터 실제 삭제·재생성 여부 확인.

아직 클러스터 리소스를 삭제하지 않았다. `orbit-gitops-test` namespace, smoke-test,
#52 리소스·인증정보와 운영 CDN은 유지한다. 실제 삭제 직전에 대상·finalizer·참조를 다시 확인하고,
실행한 삭제와 검증 결과만 이 문서에 추가한다.
