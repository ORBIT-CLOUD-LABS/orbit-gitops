---
status: Team Review
created: 2026-10-15
updated: 2026-10-15
decision_date:
---

# CDN 배포·검증

구현: [#9](https://github.com/ORBIT-CLOUD-LABS/orbit-gitops/issues/9).
요구사항 원본 위치는 [requirements.md](requirements.md), 정책은 [README](../README.md)를 따른다.
이 문서는 배포 실행 기록이 아니다. main 반영 후 실제 배포·서버 업로드 검증 전까지 #9를 종료하지 않는다.

## 선언과 선행 조건

- `workloads/cdn/`: NFS 정적 PV·PVC 두 쌍, Origin 1 Pod·ClusterIP, Edge 2 Pod·NodePort `30081`, 두 Nginx 설정.
- `clusters/orbit-astra/apps/cdn.yaml`: `orbit-astra-cdn`, `workloads` 프로젝트, `orbit` namespace, `main`의 `workloads/cdn`을 읽는다.
- NFS `192.168.100.105:/srv/nfs/origin`: Origin `orbit-origin-nfs-ro` / `origin-files`, 서버 `orbit-origin-nfs-rw` / `origin-files-rw`. 각 PV claimRef와 PVC volumeName으로 정적 바인딩한다.
- 두 PV는 같은 export의 접근 선언이다. `1Gi`는 바인딩 용량 값이며 NFS quota나 독립 저장소·합산 용량을 뜻하지 않는다. ReclaimPolicy는 `Retain`, StorageClass는 빈 문자열, 마운트는 NFSv4.1·hard이다.
- Origin은 PV nfs·PVC volume·volumeMount의 readOnly를 모두 true로 설정한다. 서버는 #7에서 RW PVC를 UID/GID `10001:10001`로 마운트한다. Edge는 NFS를 마운트하지 않는다.
- NFS·Ansible은 이번 변경 범위가 아니다. infrastructure #43의 기존 export·권한·worker 클라이언트를 사용한다. 디렉터리 0755, 파일 0644이며 NFS 소유권을 fsGroup이나 root로 변경하지 않는다.

infrastructure [#52](https://github.com/ORBIT-CLOUD-LABS/orbit-infrastructure/issues/52)가 root 자동 Sync와 AppProject 권한을 담당한다. develop 원본에는 PV·PVC 허용이 반영돼 있으나 대상 클러스터 적용 여부는 별도 확인한다. workloads에 `orbit` 목적지, core PV(cluster scope)·PVC·Service·ConfigMap, apps Deployment가 필요하다. root·AppProject·namespace를 GitOps에 중복 생성하지 않는다. NodePort 충돌도 main 반영 전에 확인한다.

```bash
kubectl config current-context
kubectl get nodes -o wide
kubectl get namespace orbit
kubectl get appproject workloads -n argocd -o yaml
kubectl get application orbit-astra-root -n argocd -o yaml
kubectl get svc -A
```

원본 phase1.md에는 NodePort·PVC·export가 미확정으로 남아 있다. 이번 #9 구현 지시와 #43 적용값에 따라 위 값을 사용하며, 원본 공통 문서 정리는 별도 작업이다. 실제 `CDN_BASE_URL`의 접근 가능한 worker IP는 배포 후 #7에서 확인한다.

## 설정과 적용 영향

두 Deployment 이미지는 `docker.io/library/nginx@sha256:ed84151ed2d47ef93c0939eb9b9754c6990db6092cd2081e11988a47a83d47ea`로 고정한다. Deployment 파일의 `image: nginx`는 Kustomize 치환 대상이므로 반드시 `-k`로 렌더링한다.

| Pod당 값 | Origin | Edge |
| --- | --- | --- |
| CPU request / limit | 100m / 500m | 100m / 500m |
| memory request / limit | 64Mi / 256Mi | 64Mi / 256Mi |
| ephemeral-storage request / limit | 128Mi / 512Mi | 128Mi / 2Gi |
| cache max_size / emptyDir sizeLimit | 없음 | 1g / 1536Mi |

Edge는 Pod마다 disk-backed emptyDir를 사용하고 worker 분산은 preferred podAntiAffinity로 설정한다. 배치 노드를 실제 기록한다. 캐시는 Pod 교체 시 사라지며 max_size는 즉시 강제되는 quota가 아니다. 용량·eviction·throttling은 배포 후 확인한다.

Nginx는 `/firmware/`만 제공하며 숨김 경로를 거부한다. Edge의 cache key는 scheme·upstream host·request URI, 200 TTL은 30분, cache lock은 활성, stale·upstream 재시도는 비활성이다. `X-Cache-Status`·`X-Edge-ID`와 시각 포함 JSON stdout 로그를 제공한다. 캐시·로그 필드는 실제 요청 결과로 확인한다.

모든 probe는 `/healthz`로 Nginx 응답만 검사한다. 시험 파일·NFS 상태·Origin 연결·해시를 보장하지 않는다. startup은 2초×30회, readiness 5초·liveness 10초×3회, timeout은 모두 1초다.

sync-wave는 PV·PVC `-2`, Service·ConfigMap `-1`, Origin Deployment `0`, Edge Deployment `1`이다. 같은 Application 안의 순서이며 다른 자식 Application의 준비를 보장하지 않는다. #7은 PVC가 Bound된 뒤 검증한다.

configMapGenerator 기본 해시를 유지한다. conf 변경 시 ConfigMap 이름과 Pod template 참조가 바뀌어 rollout한다. subPath 파일의 자동 reload에 의존하지 않는다. Origin의 단일 고정 replica도 rolling update 중 일시적으로 Pod가 더 생길 수 있다. Edge 새 Pod의 cold cache는 Origin 요청량을 늘릴 수 있다.

자동 Sync·최대 5회 재시도(5s×2, 최대 대기 3m)는 #15 기준이다. Prune·Self Heal은 false, 삭제 연쇄 finalizer는 없다. main 병합과 #52 실제 적용 후 자동 배포되며 일반 배포를 수동 apply로 대신하지 않는다.

## 배포 전 검사

```bash
kubectl kustomize workloads/cdn
kubectl apply --dry-run=client -k workloads/cdn
kubectl apply --dry-run=server -k workloads/cdn
kubectl apply --dry-run=server -f clusters/orbit-astra/apps/cdn.yaml
orbit_nginx_image='docker.io/library/nginx@sha256:ed84151ed2d47ef93c0939eb9b9754c6990db6092cd2081e11988a47a83d47ea'
orbit_cdn_dir="$PWD/workloads/cdn"
docker run --rm --entrypoint nginx --mount "type=bind,src=$orbit_cdn_dir/origin.conf,dst=/etc/nginx/conf.d/default.conf,readonly" "$orbit_nginx_image" -t
docker run --rm --entrypoint nginx --add-host cdn-origin.orbit.svc.cluster.local:127.0.0.1 --mount "type=bind,src=$orbit_cdn_dir/edge.conf,dst=/etc/nginx/conf.d/default.conf,readonly" "$orbit_nginx_image" -t
```

API dry-run에는 대상 API 서버가 필요하며 AppProject 권한 검증을 대신하지 않는다. Docker의 임시 hosts 값은 문법 검사 전용이며 배포 설정에 넣지 않는다.

## main 반영 후 증거

검사 시작 UTC 시각·Git revision·Argo 적용 revision·Pod imageID·Pod와 worker 이름을 기록한다. 수동 Sync 없이 자동 적용됐는지도 Application operation에서 확인한다.

```bash
kubectl get application orbit-astra-root orbit-astra-cdn -n argocd -o yaml
kubectl get pv orbit-origin-nfs-ro orbit-origin-nfs-rw
kubectl get pvc,pod,svc -n orbit
kubectl rollout status deployment/cdn-origin -n orbit --timeout=180s
kubectl rollout status deployment/cdn-edge -n orbit --timeout=180s
kubectl get pods -n orbit -l app=cdn-edge -o wide
kubectl get endpointslice -n orbit -l kubernetes.io/service-name=cdn-edge -o yaml
kubectl get pv orbit-origin-nfs-ro -o jsonpath='{.spec.nfs.readOnly}{"\n"}'
kubectl get deployment cdn-origin -n orbit -o jsonpath='{.spec.template.spec.volumes[?(@.name=="origin-files")].persistentVolumeClaim.readOnly}{"\n"}{.spec.template.spec.containers[0].volumeMounts[?(@.name=="origin-files")].readOnly}{"\n"}'
kubectl exec -n orbit deployment/cdn-origin -- awk '$5 == "/srv/origin" { print; seen=1; n=split($6,a,","); for(i=1;i<=n;i++) if(a[i]=="ro") ro=1 } END { exit !(seen && ro) }' /proc/self/mountinfo
```

PVC 두 개의 Bound, Origin 1·Edge 2 Ready, Ready Edge endpoint 두 개를 확인한다. 선언의 true 세 개와 mountinfo의 ro를 기록한다. `test ! -w`만으로는 UID·권한에 의한 거부와 구분할 수 없다. 원본을 수정하지 않고 실제 ro를 판정한다.

Origin Service와 각 Edge Pod로 별도 port-forward한다. A/B는 실제 서로 다른 Pod 이름을 선택한다. 각 명령은 별도 터미널에서 유지하고 완료 후 Ctrl-C로 종료한다.

```bash
kubectl port-forward -n orbit service/cdn-origin 18080:80
# 별도 터미널에서 실제 Pod 이름으로 치환한다.
kubectl port-forward -n orbit pod/EDGE_A_POD 18081:8080
kubectl port-forward -n orbit pod/EDGE_B_POD 18082:8080
```

같은 관리 단말에서 실행한다. Mac에서는 sha256sum을 shasum -a 256으로 치환한다.

```bash
orbit_check_dir=$(mktemp -d /tmp/orbit-cdn9.XXXXXX)
orbit_check_start=$(date -u +%Y-%m-%dT%H:%M:%SZ)
for orbit_port in 18080 18081 18082; do
  curl --fail --silent --show-error -D "$orbit_check_dir/$orbit_port-first.headers" -o "$orbit_check_dir/$orbit_port.bin" "http://127.0.0.1:$orbit_port/firmware/NFS43FIXTURE/1.0.0/firmware.bin"
  curl --fail --silent --show-error -D "$orbit_check_dir/$orbit_port-second.headers" -o /dev/null "http://127.0.0.1:$orbit_port/firmware/NFS43FIXTURE/1.0.0/firmware.bin"
done
sha256sum "$orbit_check_dir/18080.bin" "$orbit_check_dir/18081.bin" "$orbit_check_dir/18082.bin"
wc -c "$orbit_check_dir/18080.bin" "$orbit_check_dir/18081.bin" "$orbit_check_dir/18082.bin"
kubectl logs -n orbit deployment/cdn-origin --since-time="$orbit_check_start" --timestamps > "$orbit_check_dir/origin.log"
# EDGE_A_POD / EDGE_B_POD는 실제 이름으로 치환한다.
kubectl logs -n orbit EDGE_A_POD --since-time="$orbit_check_start" --timestamps > "$orbit_check_dir/edge-a.log"
kubectl logs -n orbit EDGE_B_POD --since-time="$orbit_check_start" --timestamps > "$orbit_check_dir/edge-b.log"
```

#43 fixture 기대값은 67108864 byte, SHA-256 `91800c95b2c809c3d1c8df22ec87e4eb593a2117f8f4fe4de148a16ffd11e2f8`이다. Origin·각 Edge 파일 3개가 일치하고 각 Edge는 같은 X-Edge-ID로 MISS→HIT가 되어야 한다. 이미 warm이면 첫 HIT를 MISS로 기록하지 않는다. 별도 전용 경로나 계획된 캐시 초기화로 cold를 준비하며 무단 Pod 삭제는 수행하지 않는다.

동시 접근이 없는 구간에서 직접 Origin 다운로드 2회와 Edge MISS가 만든 Origin GET을 구분하고, HIT 후 Origin GET이 늘지 않는지 시각·URI로 대응한다. 숨김 경로와 없는 파일도 403/404이며 캐시되지 않는지 확인한다.

#7 준비 후 별도 model/version을 사용하고 현재 API 계약·인증에 따라 `POST /api/v1/admin/artifacts`로 실제 업로드한다. 응답 path·byte·sha256과 Origin·각 Edge 다운로드를 비교한다. 토큰은 증거에 포함하지 않는다. 접근 가능한 worker IP의 `http://<worker IP>:30081/firmware/...` 응답을 확인하고 `CDN_BASE_URL=http://<worker IP>:30081`을 #7에 전달한다. 미검증 동안 #9를 닫지 않는다.

## 복구와 삭제

Git revert로 revision을 되돌리고 자동 적용 후 Pod·HTTP 응답을 확인한다. NFS 데이터나 캐시는 Git revert로 복원되지 않는다. Prune=false이므로 Git 파일 삭제만으로 리소스가 사라지지 않는다. 현재 Pod 참조·롤백 대상이 아닌 이전 ConfigMap만 별도 확인 후 정리한다. PV·PVC나 NFS 원본 삭제는 이 복구 절차에 포함하지 않는다. 자동 Sync 중지는 root·자식을 각각의 원본에서 관리한다.

## 구현 검증 기록 — 2026-10-15

- `kubectl kustomize workloads/cdn`: 리소스 10개 생성, PV·PVC·Deployment·Service·ConfigMap 각 2개.
- kubeconform v0.8.0 strict, Kubernetes v1.33.0 스키마: 10개 Valid, Invalid·Errors·Skipped 0.
- Argo CD v3.5.5 공식 Application CRD 스키마: Application 1개 Valid.
- 고정 digest 이미지 pull과 두 설정의 `nginx -t`: 모두 성공.
- 정적 검사: PVC volumeName·PV claimRef·accessModes·Retain, namespace scope, Service selector, 고정 digest, RO 선언 3개, probe·resources, Edge 독립 emptyDir 일치.
- conf 두 개의 변경 전후 렌더링 비교: 생성 ConfigMap 이름과 Deployment 참조가 모두 변경됨. 실제 클러스터 rollout 검증과 구분한다.
- 문서 상대 링크·코드 블록·CDN 셸 예제 문법 및 `git diff --check`: 통과.
- client/server dry-run: kubeconfig가 없어 API 연결 실패. 실제 클러스터의 권한·NodePort 충돌·Bound·Ready·RO mount·파일 해시·각 Edge MISS→HIT·서버 업로드·자동 Sync는 미검증이다.

이 기록은 로컬 검증이다. 실제 배포 완료나 #9 종료 근거로 사용하지 않는다.
