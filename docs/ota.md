# OTA 서버 선언 (ota/)

OTA Main(`ota-main`)과 OTA Sub(`ota-sub`) 클러스터에 orbit-server를 배포하는 선언이다.
두 클러스터가 같은 `ota/base`를 쓰고, 다른 값만 overlay에 둔다.

```text
ota/
├── base/   Deployment, Service, Ingress, ConfigMap, ExternalSecret, HPA (namespace ota)
├── main/   ota-main. base + PDB
└── sub/    ota-sub. base + HPA 최소 1대
```

## 요청 흐름

rp-core(TLS 종료) → rp-ota → 클러스터 입구 VIP의 Traefik HTTP 입구(NodePort 30080) → Ingress → Service `orbit-server:8080`.
rp-ota는 Main이 응답하지 않을 때만 Sub로 넘긴다. 두 클러스터는 같은 RDS와 S3를 쓴다.

Ingress는 Host `ota.orbit-labs.space`의 `/api`만 받는다. `/actuator`(health, prometheus)는 인증 없이 열려 있어 클러스터 밖으로 내보내지 않는다.

## 값과 근거

| 항목 | 값 | 근거 |
| --- | --- | --- |
| namespace | `ota` | 클러스터 이름 ota-main·ota-sub와 맞춤. namespace는 orbit-infrastructure가 만든다 |
| replica | Main 2~4, Sub 1~4 (HPA, CPU 70%) | Sub는 평소 요청이 없다. 넘어오면 HPA가 30초마다 1대씩 늘린다 |
| PDB | Main만 `minAvailable: 1` | Sub는 1대라 PDB가 노드 drain을 막는다 |
| CPU | request 500m, limit 750m | Phase1 부하 측정값. 이유는 deployment.yaml 주석 |
| 메모리 | 768Mi (request = limit) | Phase1 측정값 |
| DB 연결 | Pod당 5 | 두 클러스터 최대 8대 × 5 = 40, rolling update 중 최대 45. db.t3.micro 연결 상한 안 |
| probe | startup 최대 2분, liveness, readiness(DB 포함) | 서버의 health group 설정과 맞춤 |
| 종료 | preStop 5초, graceful 30초, grace period 40초 | |
| S3 | `orbit-firmware-origin-backup`, `ap-northeast-2`, 엔드포인트 비움 | S3 인터페이스 엔드포인트의 사설 DNS가 기본 주소를 받는다 |
| CDN Edge | 서울·대전·부산 3개, 기본 서울, `https://cdn.orbit-labs.space/<seoul|daejeon|busan>` | `ota/base/cdn-edges.yaml`. 파일로 넣는다(`SPRING_CONFIG_IMPORT`) |

Edge 주소는 이름 하나(`cdn.orbit-labs.space`)에 Edge마다 경로를 나눈다. rp-core·rp-cdn이 이 이름 하나만 받기 때문이다.
서버는 URL 서명에 Edge 주소를 넣지 않고 Origin 경로(`/firmware/...`)만 넣어, 같은 서명이 모든 Edge에서 통한다(예비 URL).
그래서 CDN 클러스터는 `/seoul` 같은 앞 경로를 떼고(StripPrefix) Edge nginx에 넘겨야 `secure_link` 검증이 맞는다.
Edge를 바꾸면 CDN 쪽 Edge 선언도 함께 고친다.

노드 역할 라벨로 노드를 고르지 않는다. 클러스터 VM 3대가 모두 server라 hostname 기준으로 고르게 나눈다.

## 비밀값 (Vault)

ExternalSecret `orbit-server-secret`이 아래 키를 읽는다. 키가 하나라도 없으면 Secret이 만들어지지 않는다.

| Vault 경로 | 키 | 환경 변수 |
| --- | --- | --- |
| `secret/orbit/k3s/orbit-server` | `db-url` | `DB_URL` (Terraform 출력 `orbit_server_db_url`, `sslMode=REQUIRED`) |
| | `db-username` | `DB_USERNAME` |
| | `db-password` | `DB_PASSWORD` |
| | `origin-access-key` | `ORIGIN_ACCESS_KEY` (Origin 쓰기 IAM 사용자) |
| | `origin-secret-key` | `ORIGIN_SECRET_KEY` |
| | `enrollment-key` | `ENROLLMENT_KEY` |
| | `admin-token` | `ADMIN_TOKEN` |
| `secret/orbit/k3s/cdn-url-signing` | `key-id` | `CDN_URL_SIGNING_KEY_ID` |
| | `secret` | `CDN_URL_SIGNING_SECRET` |

- `DB_URL`에는 RDS 엔드포인트가 들어 있어 공개 저장소인 이 저장소에 두지 않는다.
- URL 서명 값은 CDN Edge가 같은 값을 써야 하므로 두 앱이 같이 읽는 경로에 둔다. kid도 값과 함께 바뀌어야 하므로 같은 곳에 둔다.
- Secret이나 ConfigMap 값이 바뀌어도 Pod는 바로 바뀌지 않는다. ConfigMap은 이름 hash가 바뀌어 다음 동기화에서 Pod가 새로 뜨고, Secret은 바꾼 뒤 `kubectl -n ota rollout restart deployment/orbit-server`로 다시 띄운다.

## 배포 전 필요한 것

1. orbit-infrastructure: 두 OTA 클러스터에 namespace `ota`, AppProject `orbit-k3s-workloads`
2. ESO와 ClusterSecretStore가 새 클러스터에 있고, Store의 namespace 조건에 `ota`가 들어 있음
3. Vault에 위 표의 키
4. `ota/base/kustomization.yaml`의 이미지 항목. orbit-server 첫 릴리스의 버전과 digest로 넣고, 그 뒤로는 릴리스가 고친다
5. 서명 공개 키(`orbit.signing.public-keys`). 없으면 서버가 뜨지 않으므로 develop에 머지하기 전에 넣는다

## 확인

```bash
kustomize build ota/main
kustomize build ota/sub
```

배포 뒤:

```bash
kubectl -n ota get externalsecret orbit-server-secret      # Ready=True
kubectl -n ota get deploy,hpa,pdb
kubectl -n ota rollout status deployment/orbit-server
```
