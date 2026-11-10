# 요구사항 참조

요구사항의 원본(source of truth)은 orbit 레포 `docs/`에 있다. 이 레포에 복사하지 않는다.

## 위치

| 항목 | 값 |
| --- | --- |
| 레포 | https://github.com/ORBIT-CLOUD-LABS/orbit |
| 경로 | `docs/` |

## 읽는 방법

1. 로컬에 있으면 읽기 전에 `git -C ../orbit pull`로 최신화한다.
2. 로컬에 없으면 GitHub에서 읽는다.

   ```bash
   # 파일 목록
   gh api repos/ORBIT-CLOUD-LABS/orbit/contents/docs --jq '.[].name'
   # 파일 내용
   gh api repos/ORBIT-CLOUD-LABS/orbit/contents/docs/<파일명> -H 'Accept: application/vnd.github.raw'
   ```

3. 둘 다 안 되면 추측해서 작성하지 말고 사용자에게 요구사항을 요청한다.

## Phase2 문서

| 문서 | 이 레포에서 보는 내용 |
| --- | --- |
| `flow.md` | Edge 구성·서버 설정 키(`orbit.cdn.*`, `orbit.signing.*`)·S3·RDS(§0), Edge 헬스체크(§2 ⑤ 아래), Edge nginx 설정(§2 ⑥), 인증·비밀값(§5), 협의 항목(§7) |
| `infrastructure.md` | 노드·배치(§1~2), 모니터링 VM(§3), Vault(§4), 게이트웨이 nginx(§5), 내부망(§7) |
| `api.md`, `api-spec.md` | 서버 내부 작업(Edge 목록 설정, 헬스체크, URL 서명 등)처럼 배포 설정과 닿는 부분만 참고 |
| `전체구성.md` | 클러스터 안팎 구성 요약 |

- 앱 흐름·설정 값은 `flow.md`, 노드·네트워크·외부 서비스 배치는 `infrastructure.md`를 따른다.
- 두 문서가 서로 다르거나 이 레포의 선언과 다르면 임의로 고르지 말고 질문한다.

## 미확정 값

아래는 원본에서 "제안"·예시 상태이거나 정해지지 않은 값이다. 확정 전에는 manifest에 고정하지 않는다.

- `flow.md`, `api.md`, `api-spec.md`는 문서 상태가 "설계중"이다. 값을 쓰기 전에 확정 여부를 확인한다.
- `flow.md` §7의 모든 항목 (Edge 개수·이름·좌표, 헬스체크 주기, `fallback-count`, `location-max-age`, `default-edge-id`, `signed-url-ttl` 등)
- `flow.md` §0·§2 ⑤의 Edge `base-url` 예시 주소 (Phase1 대역 `192.168.100.x`로 남아 있음)
- S3 버킷 이름·리전, RDS 엔드포인트
- 앱 namespace, 서버의 외부 노출 방식(NodePort 번호 등)

## 규칙

- 배포 선언을 작성하기 전에 관련 요구사항을 먼저 읽는다.
- 요구사항 문서는 읽기만 한다. orbit 레포를 수정하지 않는다. 오류를 발견하면 orbit 레포에 Issue로 올린다.
- 요구사항이 모호하거나 이 레포의 선언과 다르면 임의로 해석하지 말고 질문한다.
- Phase1 선언과 기록은 이전 이력에서 참고만 한다. Phase2 값의 근거로 쓰지 않는다.
