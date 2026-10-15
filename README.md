# ORBIT GitOps

`orbit-astra` 단일 클러스터의 배포 원본이다. root Application과 AppProject,
저장소 인증 Secret은 `orbit-infrastructure/ansible/roles/argocd_gitops`가 bootstrap한다.
ApplicationSet은 환경·클러스터 증가로 Application 정의가 반복될 때 검토한다.

| 경로 | 내용 |
| --- | --- |
| `clusters/orbit-astra/apps/` | root가 읽는 자식 Application 정의만 저장 |
| `workloads/<app>/` | 업무 앱 또는 연결 검증용 manifest |
| `platform/<addon>/` | 플랫폼 애드온 manifest 및 추가 규칙 |
| [docs/requirements.md](docs/requirements.md) | 요구사항 원본·공통 값 참조 |
| [docs/cdn.md](docs/cdn.md) | CDN 구성·선행 조건·검증·복구 |

## 최초 연결

이 저장소의 manifest를 `main`에 반영한 뒤 infrastructure의
[GitOps bootstrap 절차](https://github.com/ORBIT-CLOUD-LABS/orbit-infrastructure/blob/develop/docs/argocd-gitops.md)를 따른다.
infrastructure #52의 root 자동 Sync 설정을 대상 클러스터에 적용하면
`orbit-astra-root`가 자식 Application을 자동 생성·갱신한다. main 병합만으로
root 설정이 바뀌지는 않는다. namespace·AppProject·저장소 인증은 Ansible이 먼저 준비한다.
기존 `orbit-astra-smoke-test`는 수동 Sync해야 ConfigMap이 생성된다.
`orbit-astra-cdn`은 자동 Sync로 Origin·Edge와 정적 PV·PVC를 배포한다.

## 작업 규칙

- root 경로는 관리자 리뷰 대상으로 취급한다. `spec.project`, source, destination, sync 정책을 확인한다.
- 업무 앱은 `workloads`, 애드온은 `platform` 프로젝트를 사용한다. `default` 또는 `bootstrap`을 자식에 사용하지 않는다.
- 기본 destination은 `https://kubernetes.default.svc`이다. `argocd` namespace에 업무·애드온을 배포하지 않는다.
- root 자동 Sync·재시도는 infrastructure에서, 자식 정책은 이 저장소에서 관리한다.
- #15 및 #7~#10 자식은 아래 자동 Sync·제한된 재시도 기준을 적용한다. 기존 smoke-test는 수동 정책을 유지한다.
- root와 자식의 Prune·Self Heal은 비활성화한다. UI 수동 Sync에서도 Prune을 선택하지 않는다.
- 개인키, 토큰, 평문 Secret을 커밋하지 않는다. root나 자식에 삭제 연쇄 finalizer를 추가하지 않는다.
- 앱 추가 시 infrastructure AppProject의 허용 namespace·리소스를 먼저 검토한다.
- Helm chart와 이미지의 버전을 고정하고, 테스트·롤백·삭제 영향과 수동 적용 순서를 PR에 기록한다.

## Sync 정책

기존 smoke-test는 ConfigMap의 `message`를 `gitops-v1`에서 `gitops-v2`로 변경하면 자식이 OutOfSync가 된다.
수동 Sync 전에는 실제 값이 v1이고, Sync 후 v2인지 확인한다. 마지막으로 v1으로 되돌려 다시 Sync한다.
실제 클러스터 변경을 직접 수행해도 Self Heal이 꺼져 있어 자동 복구되지 않아야 한다.

#15의 자식 기준에 맞춰 자동 Sync와 최대 5회 재시도를 사용한다.

```yaml
syncPolicy:
  automated:
    enabled: true
    prune: false
    selfHeal: false
  retry:
    limit: 5
    backoff:
      duration: 5s
      factor: 2
      maxDuration: 3m
```

root와 자식 정책은 독립적이다. main 반영 시 배포가 시작될 수 있으므로 namespace·권한·
Secret·의존 리소스를 먼저 준비한다. 재시도 소진 후 원인을 수정하고 새 Git revision을
반영하거나 Prune 없는 수동 Sync로 복구한다. 일반 배포 검증은 수동 Sync 없이 수행한다.
Self Heal 비활성 상태에서도 새 Git revision이나 수동 Sync는 직접 변경한 값을 덮어쓸 수 있다.
배포 중지는 root는 Ansible, 자식은 이 저장소에서 자동 Sync를 비활성화한다.
root만 중지해도 자식의 자동 Sync는 계속 동작한다.

Prune이 꺼져 있어 Git 파일 삭제만으로 리소스가 제거되지 않는다. 삭제 연쇄 finalizer도
추가하지 않는다. 이전 해시 ConfigMap은 현재 참조와 롤백 필요성을 확인한 뒤 별도로 정리한다.
롤백은 Git revert로 반영하고 실제 Pod·HTTP 복구를 확인한다. PV·PVC나 NFS 파일 삭제를
복구 절차에 포함하지 않는다.

부하 실험 중에는 Git·이미지·설정 변경을 멈추고 측정 revision을 고정한다.
orbit 원본 `docs/phase1.md`의 수동 Sync 설명은 #9·#15의 최신 결정과 차이가 있다.
원본 정책 정리는 orbit에서 별도로 수행하며 요구사항 원본을 이 저장소에 복사하지 않는다.
