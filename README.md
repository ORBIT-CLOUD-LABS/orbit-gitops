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

CI/CD 배포 경로 검증 #15와 후속 #7~#10의 자식 Application 기준이다.
기존 Phase1 실험의 이미지·설정 고정 원칙은 유지하며, 부하 실험 중에는 Git 변경을 멈춘다.
원본 `orbit/docs/phase1.md`의 수동 Sync 설명과 차이가 있으므로 원본 정책 정리는
orbit 저장소에서 별도로 수행한다. 이 저장소에 원본을 복사하거나 직접 수정하지 않는다.

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

root와 자식의 자동 Sync는 독립적이다. main 반영 후 선행 조건이 준비되지 않은 앱도
배포가 시작될 수 있으므로 Secret·namespace·권한·의존 리소스는 먼저 준비한다.
재시도 소진 후에는 원인을 고쳐 새 Git revision을 반영하거나 Prune 없는 수동 Sync로 복구한다.
롤백은 Git revert로 수정 revision을 만들고 실제 리소스 복구까지 확인한다.

Self Heal 비활성화는 클러스터 직접 변경만으로 자동 복구하지 않는다는 뜻이다.
이후 Git 변경이나 수동 Sync에서는 Git 값으로 덮어쓸 수 있다. 배포 중지는 root는
Ansible, 자식은 이 저장소에서 자동 Sync를 비활성화한다. root만 중지해도 자식은 계속 동작한다.

Prune이 꺼져 있어 Git 파일 삭제만으로 Application·배포 리소스가 제거되지 않는다.
삭제 연쇄 finalizer도 추가하지 않는다. 정리 목록과 순서를 검토하고 명시적으로 삭제한다.
Nginx 배포·HTTP·rollout 검증과 정리 절차는 [deploy-test.md](docs/deploy-test.md)를 따른다.

기존 smoke-test는 `message` v1→v2→v1 변경과 각 단계 수동 Sync로 확인한다.
Self Heal이 꺼져 있으므로 직접 변경만으로 자동 복구되지 않아야 한다.
