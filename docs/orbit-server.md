# orbit-server 배포·검증·복구

관련 이슈: [#7](https://github.com/ORBIT-CLOUD-LABS/orbit-gitops/issues/7).
요구사항 원본은 [requirements.md](requirements.md), Sync 정책은 [README](../README.md)를 따른다.
이 문서는 초기 단일 Pod 배포의 실행 절차와 사전 검증 기록이다. 실제 서버 배포 완료 기록이 아니다.

## 이번 구현 범위

- `workloads/orbit-server/`: ConfigMap, Deployment, NodePort Service, PDB, Kustomization.
- `clusters/orbit-astra/apps/orbit-server.yaml`: Application `orbit-astra-orbit-server`.
- HPA 도입 전 기동·DB·업로드 검증을 위해 `replicas: 1`로 시작한다. #7의 최종 최소 2·최대 4 구성은 후속 작업이다.
- 이미지는 `ghcr.io/orbit-cloud-labs/orbit-server:6cb87138b7b797faeed566670e180619303fafbc`로 고정한다.
- CPU request/limit은 초기값 `500m`, 메모리 request/limit은 `768Mi`, Hikari 최대 연결은 5이다. CPU 적정성은 부하 사전 측정으로 판단한다.
- Service는 8080을 NodePort `30080`으로 노출한다. API와 `/actuator/prometheus`가 같은 포트를 사용한다.
- ConfigMap의 `CDN_BASE_URL`은 `http://192.168.100.102:30081`이다. 차량·부하 발생기에서도 이 주소에 접근 가능해야 한다.
- 기존 `origin-files-rw` PVC를 `/data/origin`에 쓰기로 마운트한다. `ORIGIN_ROOT_PATH`와 mountPath를 함께 변경한다.
- UID/GID `10001:10001`을 사용하고 fsGroup으로 NFS 소유권을 바꾸지 않는다. Secret은 기존 `orbit-server-secret`을 참조한다.
- `SPRING_PROFILES_ACTIVE`와 이전 S3 관련 환경 변수는 넣지 않는다.

startup probe는 liveness 경로를 5초 간격 24회로 검사해 기동에 약 2분을 허용한다.
liveness는 서버 상태만, readiness는 DB 연결까지 검사한다. 5초 preStop과 Spring graceful shutdown 30초를 위해 종료 유예를 40초로 둔다.
worker label이 있는 노드에만 배치하고 topology spread는 분산을 선호한다. 여러 Pod의 서로 다른 노드 배치를 강제하지는 않는다.
롤링 업데이트는 maxSurge 1·maxUnavailable 0이므로 일시적으로 추가 Pod와 DB 연결을 사용한다.

PDB `minAvailable: 1`은 계획된 축출에 적용된다. 단일 Pod 상태에서는 해당 Pod의 drain을 막을 수 있으므로
노드 점검 전 여분 Pod 준비와 배치 상태를 확인한다. 노드 장애·강제 삭제를 막거나 단일 Pod의 무중단 서비스를 보장하지 않는다.

## 병합 전 확인

아래 kubectl 명령은 대상 클러스터 kubeconfig가 있는 제어 노드에서 실행한다.
manifest 검사는 작업 브랜치를 checkout한 저장소에서 수행한다.

```bash
kubectl config current-context
kubectl get nodes -o wide
kubectl get namespace orbit
kubectl get appproject workloads -n argocd -o yaml
kubectl get application orbit-astra-root -n argocd -o yaml
kubectl get pvc origin-files-rw -n orbit
kubectl get svc -A -o wide
kubectl top nodes
kubectl get secret orbit-server-secret -n orbit \
  -o go-template='{{range $k, $v := .data}}{{$k}}{{"\n"}}{{end}}'
```

workloads에 orbit 목적지와 ConfigMap·Deployment·Service·PodDisruptionBudget이 허용되어 있어야 한다.
Secret 키는 ADMIN_TOKEN·DB_PASSWORD·ENROLLMENT_KEY이며 값은 출력하거나 증거에 남기지 않는다.
PVC Bound, NodePort 30080 미사용, worker 자원·label·taint, CDN 접근을 병합 직전에 다시 확인한다.
Secret 관리 절차는 [orbit-server-secret.md](orbit-server-secret.md), PVC·CDN 절차는 [cdn.md](cdn.md)를 따른다.
서로 다른 Application 사이의 Sync 순서는 보장되지 않으므로 CDN Application의 존재만으로 PVC 준비를 판단하지 않는다.

```bash
kubectl kustomize workloads/orbit-server
kubectl apply --dry-run=client -k workloads/orbit-server
kubectl apply --dry-run=server -k workloads/orbit-server
kubectl apply --dry-run=server -f clusters/orbit-astra/apps/orbit-server.yaml
git diff --check
```

dry-run은 스키마·API 수락 여부 검사이며 실제 이미지 기동, 볼륨 마운트, DB 인증, Argo CD 동작을 검증하지 않는다.
Application dry-run이 AppProject의 배포 허용 여부를 대신하지 않으므로 위 권한 검토도 필요하다.

## 자동 배포와 확인

리뷰 후 main 병합 시 root가 자식 Application을 생성하고, 자식이 main의 workloads/orbit-server를 자동 배포한다.
일반 배포를 수동 apply로 대신하지 않는다. root 자동 Sync는 infrastructure가 관리하며 대상 클러스터에 적용되어 있어야 한다.
자식은 자동 Sync·최대 5회 재시도(5s, factor 2, maxDuration 3m), Prune·Self Heal 비활성화이며 삭제 연쇄 finalizer는 없다.
부하 실험 중에는 이미지·설정 변경을 멈춘다.

다음은 배포 후 실행할 명령이다. 아직 실행 결과로 기록하지 않았다.

```bash
git rev-parse HEAD
kubectl get application orbit-astra-root orbit-astra-orbit-server -n argocd -o yaml
kubectl rollout status deployment/orbit-server -n orbit --timeout=300s
kubectl get pods -n orbit -l app=orbit-server -o wide
kubectl get deployment orbit-server -n orbit
kubectl get service orbit-server -n orbit
kubectl get pdb orbit-server -n orbit
kubectl get pods -n orbit -l app=orbit-server \
  -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.spec.nodeName}{" "}{.status.containerStatuses[0].imageID}{"\n"}{end}'
curl --fail --silent --show-error http://192.168.100.102:30080/actuator/health
curl --fail --silent --show-error http://192.168.100.102:30080/actuator/health/liveness
curl --fail --silent --show-error http://192.168.100.102:30080/actuator/health/readiness
curl --fail --silent --show-error http://192.168.100.102:30080/actuator/prometheus
```

Pod 1개 Ready·재시작 0, Service의 Ready endpoint, health 응답 UP,
Prometheus 메트릭의 `application="orbit-server"` 태그를 확인한다.
Argo CD의 적용 revision·Sync/Health·operation을 확인해 수동 Sync 없이 적용됐는지 기록한다.

```bash
kubectl get endpointslice -n orbit -l kubernetes.io/service-name=orbit-server -o yaml
ssh orbit@192.168.100.106 'sudo mysql vehicle -e "SELECT installed_rank, version, description, success FROM flyway_schema_history ORDER BY installed_rank"'
```

Flyway V1·V2가 존재하고 모든 행의 success가 1인지 확인한다.
DB 세부 절차는 [infrastructure vehicle-db.md](https://github.com/ORBIT-CLOUD-LABS/orbit-infrastructure/blob/develop/docs/vehicle-db.md)를 따른다.
서버 로그와 Pod 이벤트로 오류를 조사할 수 있으나 인증 정보는 공유 기록에서 제외한다.

기본 응답 확인 후 현재 API 계약에 맞춰 다음을 별도로 검증한다.

1. 등록 키로 `POST /api/v1/vehicles/register`를 호출하고 차량 등록 성공을 확인한다. 키·발급 토큰은 기록하지 않는다. #3의 남은 검증과 연결한다.
2. 전용 model/version으로 `POST /api/v1/admin/artifacts`에 시험 파일을 업로드한다. UID 10001의 실제 NFS 쓰기 검증이기도 하다.
3. 응답의 path·byte·sha256을 Origin·각 Edge 다운로드 결과와 비교한다. 각 Edge 선택·파일 비교 절차는 cdn.md를 따른다.
4. 차량·부하 발생기 위치에서 CDN_BASE_URL 접근을 확인한다.

증거에는 확인 시각, Git·Argo revision, Pod imageID·worker, Ready·재시작 수, HTTP·Flyway·파일 비교 결과만 남긴다.

## 설정 갱신과 복구

ConfigMap 이름은 고정이며 envFrom 환경 변수는 Pod 기동 시 읽는다. ConfigMap만 수정해 Sync해도 기존 Pod는 재시작되지 않는다.
새 설정을 반영할 때 ConfigMap Sync 완료 후 다음 명령으로 재시작하고 실제 응답까지 확인한다.
Secret 교체도 같은 제약이 있으며 별도 Secret 문서를 따른다.

```bash
kubectl rollout restart deployment/orbit-server -n orbit
kubectl rollout status deployment/orbit-server -n orbit --timeout=300s
```

- 배포 실패: Pod 상태·이벤트로 이미지 pull, Secret, PVC, NFS 권한, DB 인증·migration 오류를 구분한다.
- 재시도 소진: 원인을 해결한 뒤 새 Git revision을 반영하거나 Prune 없는 수동 Sync로 재시도한다.
- 이전 정상 버전으로 복구: 작업 브랜치에서 문제 변경을 git revert하고 리뷰·main 반영 후 자동 Sync와 Ready·실제 요청 결과를 확인한다. ConfigMap만 되돌렸다면 Pod 재시작도 필요하다.
- 첫 배포를 추가 전 상태로 되돌릴 때는 Prune=false이므로 revert만으로 리소스가 삭제되지 않는다. 별도의 명시적 정리 계획이 필요하다.
- 이미지·설정 revert로 DB migration·업로드 파일·CDN 캐시는 되돌아가지 않는다. 이전 이미지의 DB 호환성도 확인한다.
- 배포 중지: 자식 자동 Sync는 이 저장소, root는 infrastructure 원본에서 각각 중지한다. root만 중지해도 기존 자식은 계속 동작한다.
- 삭제: Git 파일 삭제만으로 Application·워크로드가 없어지지 않는다. 자동 Sync 중지·재생성 방지 후 대상과 순서를 확인해 명시적으로 정리한다. 공유 PVC·PV·NFS 데이터·Secret은 서버 정리 대상으로 포함하지 않는다.

## 실제 사전 검증 기록 — 2026-10-16 KST

- orbit namespace 존재, worker 3대 Ready, worker label·taint 및 workloads 프로젝트의 목적지·리소스 허용 범위를 조회했다.
- orbit-server-secret에 필수 키 3개가 존재한다. 값의 유효성은 미검증이다.
- origin-files-rw는 Bound·RWX이다. 서버 UID의 실제 쓰기는 미검증이다.
- Service 목록에서 NodePort 30080을 사용하는 Service가 없었다.
- 제어 노드에서 worker 192.168.100.102~104 각각의 30081로 기존 CDN fixture를 내려받았다. 모두 HTTP 200·67108864 byte였다. 이번 확인에서는 파일 해시를 검사하지 않았다.
- Origin 1·Edge 2 Ready, 재시작 0이었다.
- worker별 현재 사용량은 CPU 약 2%, 메모리 11~13%였다. 초기 Pod를 배치할 자원 여유 확인이며 서버 성능 측정이 아니다.
- worker 3대에서 containerd의 k8s.io namespace에 위 SHA 이미지를 별도 인증 정보 없이 실제 pull·unpack했다. 모두 성공했다. kubelet을 통한 실제 Pod 기동 검증과 구분한다.
- Kustomize 렌더링 성공. 최초 2개 구성의 client/server dry-run, 1개로 조정 후 server dry-run이 성공했다. 렌더링 결과를 제어 노드에 표준 입력으로 전달해 검사했다.
- Application server dry-run 성공. 실제 Application 생성·자동 Sync·앱 기동·DB·차량 등록·업로드 검증은 하지 않았다.

## 남은 작업

이 기록만으로 #7을 종료하지 않는다. main 반영 후 위 실제 배포 검증을 수행한다.
[orbit#23](https://github.com/ORBIT-CLOUD-LABS/orbit/issues/23)의 사전 측정으로 CPU와 목표 사용률을 정한 뒤
HPA 최소 2·최대 4, 확장 안정화 30초·한 번에 1개 정책을 추가하고 Deployment의 replicas를 제거한다.
HPA CPU 값과 scale-out·scale-in은 그 후 별도로 검증한다.
