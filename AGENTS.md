# AGENTS.md

Phase2 k3s 클러스터의 배포 선언(Argo CD가 읽는 원본)을 작성·수정·리뷰하는 AI 에이전트용 지침.
세부 규칙은 아래 문서에 있고, 이 문서는 어떤 문서를 언제 볼지를 정한다.

## 작업 전 읽을 문서

| 상황 | 문서 |
| --- | --- |
| 요구사항·공통 값 확인 (항상) | [docs/requirements.md](docs/requirements.md) |
| Issue·Branch·커밋·PR·리뷰 | Org 공통 [CONTRIBUTING.md](https://github.com/ORBIT-CLOUD-LABS/.github/blob/main/CONTRIBUTING.md) |

## 핵심 규칙 요약

문서를 다 읽지 못했더라도 아래는 반드시 지킨다.

### 선언

- 미확정 공통 값(포트, Edge 목록, namespace, Sync 정책 등)은 확정된 것처럼 고정하지 말고 사용자에게 확인한다.
- 이미지·Helm chart는 버전을 고정한다. 이미지는 커밋 SHA tag 또는 digest를 쓰고, `latest` 같은 이동 tag를 배포에 쓰지 않는다.

### 비밀값

- 비밀값의 원본은 Vault(`https://10.0.0.201:8200`, KV v2)다. 클러스터 Secret은 External Secrets Operator(ESO)가 Vault에서 만든다.
- k3s 앱 비밀값은 Vault `secret/orbit/k3s/` 아래에 둔다. ESO는 이 경로만 읽는다.
- Git에는 ExternalSecret의 Vault 경로·키 참조만 둔다. 실제 값을 커밋하지 않는다.
- Secret을 클러스터에 수동으로 만들어 쓰지 않는다.
- Vault 토큰, CA 개인키, 장기 ServiceAccount 토큰, PAT를 클러스터나 Git에 넣지 않는다. Vault 공개 CA 인증서만 둘 수 있다.

### k3s 클러스터

- control plane `polaris`에는 `node-role.kubernetes.io/control-plane=true:NoSchedule` taint가 있다.
  워커(`sol`, `terra`, `luna`)에는 역할 라벨이 없으므로 `node-role.kubernetes.io/worker`로 노드를 선택하지 않는다.
- `polaris`는 arm64, 워커는 amd64다. 모든 노드에 뜨는 DaemonSet은 multi-arch 이미지와 control plane toleration이 필요하다.
- k3s 기본 애드온(metrics-server, CoreDNS, Traefik, ServiceLB, local-path-provisioner)이 실행 중이다. 같은 것을 따로 배포하지 않는다.
- 내부망은 `10.0.0.0/24`다. Phase1 대역 `192.168.100.x`를 쓰지 않는다.

## 검증

PR에는 실제로 실행한 검증만 적는다. 실행하지 않은 검증을 완료로 표시하지 않는다.

```bash
kubectl apply --dry-run=client -f <파일 또는 디렉터리>      # manifest 형식
kubectl kustomize <디렉터리>                                 # kustomization이 있을 때
helm template <chart> -f <values>                            # Helm을 쓸 때
kubeconform -strict -kubernetes-version 1.35.9 <파일>        # 스키마 (k3s v1.35.9+k3s1)
```
