# #15 Nginx 자동 배포 검증

기존 `orbit-gitops-test` namespace에 임시 Nginx Deployment 1개와 ClusterIP Service를 둔다.
외부 NodePort·Ingress·스토리지·Secret은 사용하지 않는다. namespace는 먼저 존재해야 한다.
`workloads` AppProject에 해당 namespace, Deployment, Service가 허용돼 있어야 한다.

## 적용 전

- infrastructure #58의 root 자동 Sync·retry 설정을 대상 클러스터에 적용한다.
- root와 자식의 repoURL·targetRevision을 확인한다. 운영 선언은 모두 `main`이다.
  브랜치 검증에서는 root를 Ansible의 `argocd_gitops_revision`으로 전환하고,
  테스트 자식도 같은 브랜치를 읽게 해야 한다. root만 바꾸면 자식은 계속 main을 읽는다.
- root가 읽는 모든 자식 diff를 검토한다. 기존 smoke-test의 수동 정책은 유지한다.
- Prune·Self Heal 비활성화, retry limit 5 / 5s / factor 2 / maxDuration 3m을 확인한다.
- 이미지 고정값은 `deployment.yaml`에 있다. 태그와 함께 멀티 아키텍처 index digest를 고정한다.

## 최초 배포와 Git 변경

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

## 복구와 중지

문제가 생기면 변경 커밋을 Git revert하고, 새 revision의 자동 반영과 Pod·HTTP 복구를 확인한다.
배포를 중지하려면 자식의 `automated.enabled`를 Git에서 false로 바꾼다.
root 중지가 필요하면 infrastructure의 Ansible 원본을 변경·적용한다.
root만 중지해도 기존 자식 자동 Sync는 계속 동작한다.

## 후속 정리 이슈의 대상

| 종류 | 대상 |
| --- | --- |
| Git 파일 | `clusters/orbit-astra/apps/deploy-test.yaml` |
| Git 디렉터리 | `workloads/deploy-test/` (Deployment·Service) |
| Application | `argocd/orbit-astra-deploy-test` |
| Deployment | `orbit-gitops-test/gitops-deploy-test` (소유 ReplicaSet·Pod 포함) |
| Service | `orbit-gitops-test/gitops-deploy-test` |

이 목록을 후속 이슈에 옮기고 Git 정의를 먼저 제거한다. root가 삭제 커밋을 읽은 뒤
Prune 비활성으로 남은 위 Application·Deployment·Service만 명시적으로 삭제한다.
Application에 삭제 연쇄 finalizer가 없는지 먼저 확인한다. 정의가 남은 상태에서 리소스만
지우면 이후 Sync에서 다시 생성될 수 있다. Application 삭제만으로 워크로드는 제거되지 않는다.
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

#15의 Git 변경 자동 배포·Pod Ready·HTTP·rollout·복구·정리는
아직 실행하지 않았으며, 위 절차는 완료 기록이 아니다. 후속 정리 이슈도 아직 생성하지 않았다.
