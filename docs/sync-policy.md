# Phase2 자식 Application Sync 정책

root Application `orbit-k3s-root`는 이 저장소 `develop`의
`clusters/orbit-k3s/apps/`를 읽는다. root의 정책은 orbit-infrastructure에서 관리한다.

자식 Application은 다음을 기본으로 한다.

| 항목 | 값 |
| --- | --- |
| 자동 Sync | `automated.enabled: true` |
| Prune | `false` |
| Self Heal | `false` |
| 실패 재시도 | 5회, 5초부터 2배씩 증가, 최대 간격 3분 |
| 삭제 연쇄 finalizer | 추가하지 않음 |
| Namespace 생성 | infrastructure가 생성. `CreateNamespace=true` 사용하지 않음 |

Git 변경은 자동 배포된다. 클러스터에서만 바꾼 설정은 Self Heal로 즉시 복구하지
않으며, 다음 동기화 시 Git 값으로 돌아갈 수 있다. Prune이 꺼져 있으므로 Git에서
파일을 지워도 기존 리소스가 자동 삭제되지는 않는다. 수동 삭제는 별도 작업이다.

ESO Helm Application은 큰 CRD의 client-side apply annotation 한도를 피하도록
`ServerSideApply=true`를 사용한다. `Replace=true`나 `Force=true`는 사용하지 않는다.
이 옵션을 모든 자식 Application에 일괄 적용하지는 않는다.

자동 Sync를 멈출 때는 해당 자식 Application의 Git 선언에서 `enabled: false`로
변경한다. root만 멈춰도 이미 생성된 자식의 자동 Sync는 계속될 수 있다.

한 PR에 ESO와 연결 선언을 함께 담을 수 있다. 별도 Application 간 sync-wave만으로
ESO CRD·webhook·Store가 준비됐다고 판단하지 않는다. 첫 배포 결과는 ESO 준비 →
ClusterSecretStore `Ready=True` → ExternalSecret `Ready=True`와 Secret 생성 순으로
확인하고, CRD가 없어 실패한 동기화는 CRD 준비 후 재시도한다.
