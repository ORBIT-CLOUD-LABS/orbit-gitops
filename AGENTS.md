# AGENTS.md

`orbit-astra` 클러스터의 배포 선언(Argo CD 가 읽는 원본)을 작성·수정·리뷰하는 AI 에이전트용 지침.
세부 규칙은 아래 문서에 있고, 이 문서는 어떤 문서를 언제 볼지를 정한다.

## 요구사항

요구사항의 원본(source of truth)은 orbit 레포에 있다. 이 레포에 복사하지 않는다.
작업 전에 읽는 방법과 규칙은 [docs/requirements.md](docs/requirements.md).
Phase1 작업은 orbit `docs/phase1.md` 를 먼저 읽는다.

## 작업 전 읽을 문서

| 상황 | 문서 |
| --- | --- |
| 배포 구성·공통 값 확인 (항상) | [docs/requirements.md](docs/requirements.md) |
| 디렉터리 구조, Argo CD 프로젝트, Sync 정책, 작업 규칙 | [README.md](README.md) |
| CDN 배포·검증·복구 | [docs/cdn.md](docs/cdn.md) |
| 플랫폼 애드온 추가 | [platform/README.md](platform/README.md) |
| Issue·Branch·커밋·PR·리뷰 | Org 공통 [CONTRIBUTING.md](https://github.com/ORBIT-CLOUD-LABS/.github/blob/main/CONTRIBUTING.md) |

## 핵심 규칙 요약

문서를 다 읽지 못했더라도 아래는 반드시 지킨다.

- 자식 Application 은 `clusters/orbit-astra/apps/` 에만 두고, 업무 앱은 `workloads`, 애드온은 `platform` 프로젝트를 쓴다.
- root 자동 Sync는 infrastructure가 관리한다. #15의 배포 검증 자식은 자동 Sync와 제한된 재시도를 사용하고, #7~#10도 각 작업에서 같은 기준을 적용한다. 기존 smoke-test는 수동 Sync를 유지한다. Prune·Self Heal은 켜지 않는다. 상세 기준은 README를 따른다.
- HPA 가 개수를 정하는 Deployment 에는 `replicas` 를 적지 않는다.
- 개인키·토큰·평문 Secret 을 커밋하지 않는다. Secret 은 클러스터에 수동으로 만들고 이름만 참조한다.
- 이미지·Helm chart 는 버전(이미지는 커밋 SHA tag 또는 digest)을 고정한다. `latest`·`phase1` 같은 이동 tag 를 배포에 쓰지 않는다.
- 새 namespace·리소스 종류·chart 저장소를 쓰면 orbit-infrastructure 의 AppProject 허용 범위를 먼저 확인한다.
- 미확정 공통 값(포트, PVC 이름, 경로 등)은 확정된 것처럼 고정하지 말고 사용자에게 확인한다.

## Phase1 디렉터리 담당

여러 명이 동시에 수정하므로 디렉터리를 나눠 PR 충돌을 피한다. 공유 파일은 클러스터·GitOps 담당이 최종 반영한다. ([orbit#25](https://github.com/ORBIT-CLOUD-LABS/orbit/issues/25))

| 경로 | 담당 역할 |
| --- | --- |
| `workloads/orbit-server/`, `clusters/orbit-astra/apps/orbit-server.yaml`, `clusters/orbit-astra/apps/metrics-server.yaml` | 클러스터·GitOps |
| `workloads/cdn/`, `clusters/orbit-astra/apps/cdn.yaml` | 스토리지·CDN |
| 수집기 리소스, `clusters/orbit-astra/apps/` 의 수집기 Application | 모니터링 |

## 검증

PR 에는 실제로 실행한 검증만 적는다. 실행하지 않은 검증을 완료로 표시하지 않는다.

```bash
kubectl apply --dry-run=client -f <파일 또는 디렉터리>   # manifest 형식
kubectl kustomize <디렉터리>                              # kustomization 이 있을 때
helm template <chart> -f <values>                         # Helm 을 쓸 때
```
