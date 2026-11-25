# prod 태그

GHCR의 orbit-server 이미지에 붙는 `prod` 태그는 **이 저장소 `main`(Argo CD가 읽는 운영 브랜치)의 `ota/base`에 적힌 이미지**를 가리킨다.
GHCR만 보고도 운영 버전을 알 수 있게 하는 표시용이다.

- Argo CD와 매니페스트는 `prod`를 쓰지 않는다. 매니페스트에는 `<버전>@sha256:<digest>`만 둔다.
- **실제로 떠 있는 버전은 Argo CD에서 확인한다.** Sync가 실패했거나 진행 중이면 `prod`와 클러스터가 다를 수 있다.

## 움직이는 때

워크플로 `.github/workflows/prod-tag.yml`

- `main`에 push되고 `ota/base/kustomization.yaml`이 바뀌었을 때 돈다. orbit-server 배포 PR을 머지했든, 그 커밋을 되돌린 revert를 머지했든 같다.
- 배포 PR이 열려 있기만 한 버전은 아직 운영이 아니므로 `prod`를 옮기지 않는다.
- 브랜치 최신 커밋의 orbit-server 항목(`newTag`, `digest`)을 읽고, 그 버전 태그의 digest가 같은지 확인한 뒤 같은 digest에 `prod`를 붙인다.
  다시 빌드하지 않으므로 digest가 바뀌지 않는다.
- 이미 같은 digest면 아무것도 하지 않는다. 늦게 시작한 실행도 최신 커밋 기준으로 읽으므로 이전 버전으로 되돌리지 않는다.
- 놓친 경우 Actions에서 `Prod tag`를 수동 실행(workflow_dispatch)하면 지금 `main` 기준으로 맞춘다.

## 권한 설정 (관리자, 한 번)

이 저장소 워크플로의 `GITHUB_TOKEN`이 orbit-server 패키지에 태그를 쓰려면 패키지 설정에서 쓰기 권한을 준다.

Org → Packages → `orbit-server` → Package settings → Manage Actions access → Add repository → `orbit-gitops`, Role: **Write**

## 설정 뒤 확인

1. orbit-server 릴리스 뒤 `docker buildx imagetools inspect ghcr.io/orbit-cloud-labs/orbit-server:prod`의 digest가 새 버전 태그와 같은지
2. 그 릴리스 커밋을 이 저장소에서 revert → `prod`가 이전 버전 digest로 돌아가는지
