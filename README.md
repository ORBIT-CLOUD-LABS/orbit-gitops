# ORBIT GitOps

`orbit-astra` 단일 클러스터의 배포 원본이다. root Application과 AppProject,
저장소 인증 Secret은 `orbit-infrastructure/ansible/roles/argocd_gitops`가 bootstrap한다.
ApplicationSet은 환경·클러스터 증가로 Application 정의가 반복될 때 검토한다.

| 경로 | 내용 |
| --- | --- |
| `clusters/orbit-astra/apps/` | root가 읽는 자식 Application 정의만 저장 |
| `workloads/<app>/` | 업무 앱 또는 연결 검증용 manifest |
| `platform/<addon>/` | 플랫폼 애드온 manifest 및 추가 규칙 |

## 최초 연결

이 저장소의 manifest를 `main`에 반영한 뒤 infrastructure의
[GitOps bootstrap 절차](https://github.com/ORBIT-CLOUD-LABS/orbit-infrastructure/blob/develop/docs/argocd-gitops.md)를 따른다.
root `orbit-astra-root`를 수동 Sync하면 자식 `orbit-astra-smoke-test`가 생성된다.
자식을 수동 Sync해야 `orbit-gitops-test`의 `gitops-smoke-test` ConfigMap이 생성된다.
namespace는 Ansible이 먼저 만든다.

## 작업 규칙

- root 경로는 관리자 리뷰 대상으로 취급한다. `spec.project`, source, destination, sync 정책을 확인한다.
- 업무 앱은 `workloads`, 애드온은 `platform` 프로젝트를 사용한다. `default` 또는 `bootstrap`을 자식에 사용하지 않는다.
- 기본 destination은 `https://kubernetes.default.svc`이다. `argocd` namespace에 업무·애드온을 배포하지 않는다.
- root와 자식의 자동 Sync, Prune, Self Heal은 모두 비활성화한다. UI 수동 Sync에서도 Prune을 선택하지 않는다.
- 개인키, 토큰, 평문 Secret을 커밋하지 않는다. root나 자식에 삭제 연쇄 finalizer를 추가하지 않는다.
- 앱 추가 시 infrastructure AppProject의 허용 namespace·리소스를 먼저 검토한다.
- Helm chart와 이미지의 버전을 고정하고, 테스트·롤백·삭제 영향과 수동 적용 순서를 PR에 기록한다.

## 검증과 정책

ConfigMap의 `message`를 `gitops-v1`에서 `gitops-v2`로 변경하면 자식이 OutOfSync가 된다.
수동 Sync 전에는 실제 값이 v1이고, Sync 후 v2인지 확인한다. 마지막으로 v1으로 되돌려 다시 Sync한다.
실제 클러스터 변경을 직접 수행해도 Self Heal이 꺼져 있어 자동 복구되지 않아야 한다.

자동 Sync는 반복 수동 배포·롤백 검증과 PR 승인 절차가 마련된 앱부터 켠다.
Prune은 관리 리소스 목록, 영구 데이터 보호, 삭제 복구 절차가 확인된 뒤 별도로 켠다.
Self Heal은 운영 중 직접 수정 처리와 Git 반영·복구 규칙이 합의된 뒤 켠다.
root 정책과 자식 정책은 독립적이므로 각각 검토한다. root Prune은 자식 Application 삭제까지
이어지므로 초기 단계에서 계속 끈다.
