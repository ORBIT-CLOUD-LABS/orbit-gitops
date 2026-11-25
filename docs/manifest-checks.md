# 매니페스트 PR 검사

Argo CD가 자동 Sync하므로 머지된 선언은 바로 클러스터에 들어간다. 잘못된 선언은
머지 전에 PR 검사에서 막는다.

## 검사 내용

워크플로 `.github/workflows/manifest-checks.yml`(검사 이름 `manifest-checks`)이 모든 PR에서 돈다.

| 순서 | 검사 | 실패 예 |
| --- | --- | --- |
| 1 | 검사 스크립트 단위 테스트 | 검사 스크립트를 고치다 규칙이 깨짐 |
| 2 | overlay마다 `kustomize build` | 없는 파일 참조, kustomization 문법 오류 |
| 3 | 빌드 결과에 `kubeconform -strict -kubernetes-version 1.35.9` | 오타 필드(`containerz`), 잘못된 타입 |
| 4 | 모든 컨테이너(initContainers 포함)에 CPU·메모리 requests·limits | `resources.requests.memory 없음` |
| 5 | 모든 이미지가 `<이름>:<버전>@sha256:<digest>` | `latest`·`prod`·`sha-` 태그, 태그만 있거나 digest만 있는 이미지 |

- overlay는 `ota/`, `cdn/` 아래에서 `base`를 뺀 `kustomization.yaml` 디렉터리다
  (`ota/main`, `ota/sub` 등). 새 서비스 디렉터리는 `scripts/ci/validate-overlays.sh`의
  `SERVICE_DIRS`에 추가한다.
- overlay가 하나도 없으면 "검사할 overlay가 없습니다"를 출력하고 통과한다.
- CRD(ExternalSecret 등) 스키마는 CRDs-catalog의 고정 커밋에서 읽는다. 카탈로그에 없는 CRD는
  `-strict`에서 실패하므로, 새 CRD를 쓰면 카탈로그 커밋을 올리거나 스키마 위치를 추가한다.
- `addons/`, `clusters/`는 아직 이 워크플로가 검사하지 않는다.

### 왜 paths 필터를 쓰지 않는가

필수 검사로 지정한 워크플로가 `paths` 필터로 건너뛰어지면 검사 결과가 생기지 않고,
GitHub는 그 PR을 "검사 대기"로 두어 머지할 수 없다. 그래서 모든 PR에서 돌고,
overlay가 없으면 안에서 통과한다.

## 로컬 실행

저장소 루트에서 실행한다. `kustomize` v5.6.0, `kubeconform` v0.6.7, `python3`와 PyYAML이 필요하다.

```bash
bash scripts/ci/validate-overlays.sh
python3 -m unittest discover -s scripts/ci/tests
```

렌더링 결과 하나만 검사할 때:

```bash
kustomize build ota/main | python3 scripts/ci/check_manifests.py -
```

## 도구 버전 올리기

워크플로 `env`의 버전과 SHA256을 함께 바꾼다. SHA256은 각 프로젝트 릴리스 페이지의
`checksums.txt`(kustomize) 또는 `CHECKSUMS`(kubeconform)에서 `linux_amd64`/`linux-amd64`
tar.gz 값을 쓴다. Kubernetes 스키마 버전은 클러스터 k3s 버전을 올릴 때
`validate-overlays.sh`의 `KUBERNETES_VERSION`과 이 문서, `AGENTS.md`를 같이 고친다.

## Ruleset 설정 (GitHub 화면, 관리자)

워크플로만으로는 머지를 막지 않는다. Argo CD가 읽는 브랜치(현재 `develop`)의 ruleset에서
아래를 설정해야 검사 실패 PR의 머지가 막힌다.

Settings → Rules → Rulesets → 해당 브랜치 ruleset

1. 기존 규칙은 그대로 둔다: 승인 1명, 대화 해결 필수, squash 머지.
2. Require status checks to pass 켜기 → Add checks에서 `manifest-checks` 추가
   (PR에서 워크플로가 한 번 돌아야 목록에 나온다).
3. Bypass list에 GitHub App `orbit-cloud-gitops-bot` 추가.
   orbit-server 릴리스 워크플로가 이 App으로 `ota/base` 이미지 줄을 직접 커밋하기 때문이다.
   사람 계정은 우회 목록에 넣지 않는다.

## 설정 뒤 확인

각각 PR을 열어 `manifest-checks`가 실패하고 머지 버튼이 막히는지 본다. 확인 뒤 PR은 닫는다.

- 이미지 줄을 태그만(`1.2.4`, digest 없음)으로 바꾼 PR
- 컨테이너 `resources.requests`를 뺀 PR
- 오타 필드(예: `containerz`)를 넣은 PR
