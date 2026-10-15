# orbit-server Secret

구현: [#3](https://github.com/ORBIT-CLOUD-LABS/orbit-gitops/issues/3). 사용처: orbit-server 배포 구성 [#7](https://github.com/ORBIT-CLOUD-LABS/orbit-gitops/issues/7).
이 문서에는 키 이름과 절차만 기록한다. 값은 Git·Issue·PR·문서·채팅 어디에도 남기지 않는다.

## 키

`orbit` namespace 의 Secret `orbit-server-secret` 하나에 세 키를 둔다.
orbit-server Deployment 는 `envFrom.secretRef` 로 이 Secret 을 환경 변수로 받는다.
기준 이미지는 `ghcr.io/orbit-cloud-labs/orbit-server:6cb87138b7b797faeed566670e180619303fafbc` 이다 (#7 과 같은 값).

| 키 | 용도 | 값의 출처 |
| --- | --- | --- |
| `DB_PASSWORD` | vehicle DB 앱 계정 `vehicle_app` 비밀번호 | 제어 노드 `~/orbit-infrastructure/ansible/secrets/vault.yml` 의 `vault_vehicle_db_password` ([infrastructure#44](https://github.com/ORBIT-CLOUD-LABS/orbit-infrastructure/issues/44)) |
| `ENROLLMENT_KEY` | 차량 공통 등록 키. 차량이 `Authorization: Bearer {enrollment-key}` 로 등록하고 차량별 토큰을 받는다 | 생성 시 랜덤 생성 |
| `ADMIN_TOKEN` | 펌웨어 업로드·캠페인 등록·대시보드 API 관리자 토큰 | 생성 시 랜덤 생성 |

- `DB_PASSWORD` 가 vault 값과 다르면 서버가 DB 로그인에 실패한다.
- `ENROLLMENT_KEY` 는 모든 차량이 공유한다. 유출되면 누구나 차량으로 등록할 수 있다.
- 세 키 모두 비어 있으면 orbit-server 가 기동하지 않는다 (`@NotBlank` 검증).
- S3 접근 키(`ORIGIN_ACCESS_KEY`·`ORIGIN_SECRET_KEY`)는 NFS 전환([orbit-server#62](https://github.com/ORBIT-CLOUD-LABS/orbit-server/issues/62)) 이후 이미지에서 쓰지 않는다.

## 관리 방식과 순서

Secret 은 Argo CD 관리 대상이 아니다. control plane 에서 수동으로 만든다.
orbit-server Application 은 자동 Sync 이므로 #7 이 main 에 반영되기 **전에** 만들어 둔다.
없으면 파드가 `CreateContainerConfigError` 로 멈춘다.
Sealed Secrets·External Secrets 같은 정식 관리 방식은 후속 Issue 에서 정한다.

정해진 별도 보관소가 없으므로 생성된 Secret 이 값의 원본이다.
차량 에이전트 설정이나 관리자 API 호출에 값이 필요하면 권한 있는 사람이 control plane 에서 읽는다.

## 생성

control plane 의 bash 에서 실행한다. 값이 셸 기록이나 프로세스 인자에 남지 않도록 `read -rs` 와
`--from-env-file` 을 쓴다. `--from-literal` 은 쓰지 않는다.

첫 줄 `read` 를 먼저 실행해 비밀번호를 입력한 뒤 나머지를 붙여 넣는다. 블록 전체를 한 번에 붙여 넣으면
`read` 가 비밀번호 대신 다음 줄을 입력값으로 가져갈 수 있다.

```bash
read -rsp 'DB_PASSWORD (vault_vehicle_db_password): ' DB_PASSWORD; echo
ENROLLMENT_KEY=$(openssl rand -hex 32)
ADMIN_TOKEN=$(openssl rand -hex 32)

kubectl create secret generic orbit-server-secret -n orbit \
  --from-env-file=<(printf 'DB_PASSWORD=%s\nENROLLMENT_KEY=%s\nADMIN_TOKEN=%s\n' \
    "$DB_PASSWORD" "$ENROLLMENT_KEY" "$ADMIN_TOKEN")

unset DB_PASSWORD ENROLLMENT_KEY ADMIN_TOKEN
```

## 확인

값을 출력하지 않고 키 이름만 확인한다. 결과는 `ADMIN_TOKEN`, `DB_PASSWORD`, `ENROLLMENT_KEY` 세 줄이어야 한다.

```bash
kubectl get secret orbit-server-secret -n orbit \
  -o go-template='{{range $k, $v := .data}}{{$k}}{{"\n"}}{{end}}'
```

## 값 읽기

필요할 때만 실행하고 출력값을 기록하지 않는다.

```bash
kubectl get secret orbit-server-secret -n orbit -o jsonpath='{.data.ENROLLMENT_KEY}' | base64 -d; echo
```

## 교체

환경 변수는 파드 시작 시에만 읽으므로 Secret 을 바꾼 뒤 재시작해야 반영된다.
`apply` 는 Secret 의 `data` 전체를 덮어쓴다. 바꾸지 않는 키도 현재 값을 읽어 함께 넘겨야 사라지지 않는다.
재시작은 Secret 갱신이 성공했을 때만 실행되도록 `&&` 로 잇는다.

```bash
get() { kubectl get secret orbit-server-secret -n orbit -o jsonpath="{.data.$1}" | base64 -d; }
DB_PASSWORD=$(get DB_PASSWORD); ENROLLMENT_KEY=$(get ENROLLMENT_KEY); ADMIN_TOKEN=$(get ADMIN_TOKEN)

# 바꿀 키만 다시 지정한다. 예:
#   ADMIN_TOKEN=$(openssl rand -hex 32)
#   ENROLLMENT_KEY=$(openssl rand -hex 32)
#   read -rsp 'DB_PASSWORD: ' DB_PASSWORD; echo

kubectl create secret generic orbit-server-secret -n orbit \
  --from-env-file=<(printf 'DB_PASSWORD=%s\nENROLLMENT_KEY=%s\nADMIN_TOKEN=%s\n' \
    "$DB_PASSWORD" "$ENROLLMENT_KEY" "$ADMIN_TOKEN") \
  --dry-run=client -o yaml | kubectl apply -f - \
  && kubectl rollout restart deployment/orbit-server -n orbit

unset -f get; unset DB_PASSWORD ENROLLMENT_KEY ADMIN_TOKEN
```

키를 다시 지정하는 줄도 생성 때와 같이 하나씩 실행한다. 붙여 넣은 블록 안의 `read` 는 다음 줄을 입력값으로 가져갈 수 있다.

- `DB_PASSWORD` 는 vault 값과 Ansible 로 바꾼 DB 계정 비밀번호를 먼저 맞춘 뒤 교체한다.
- `ENROLLMENT_KEY` 를 바꾸면 기존 키를 쓰는 차량은 새로 등록하지 못한다. 현재 서버는 키 하나만 허용하므로
  차량 설정과 함께 바꾼다. 무중단 교체 방법은 orbit `docs/flow.md` §7 협의 항목이다.
- `ADMIN_TOKEN` 을 바꾸면 대시보드·관리 도구 설정도 바꾼다.

## 삭제 영향

Secret 을 지워도 실행 중인 파드는 유지된다. 이후 재시작·재스케줄되는 파드는 `CreateContainerConfigError` 로 기동하지 못한다.
