# 플랫폼 애드온

애드온별 manifest는 `platform/<addon>/`에 둔다. 자식 Application은
`clusters/orbit-astra/apps/<addon>.yaml`에 추가하며 `spec.project: platform`을 사용한다.

현재 platform 프로젝트는 `orbit-platform` namespace의 ConfigMap만 허용한다.
실제 애드온을 추가하기 전에 infrastructure의 `argocd_gitops` 롤에서 대상 namespace,
필요한 namespaced 리소스 종류, ClusterRole·CRD 등 클러스터 리소스 종류를 검토하여
명시적으로 허용한다. 외부 Helm chart를 직접 참조하면 해당 chart 저장소도 AppProject의
sourceRepos에 명시적으로 추가해야 한다.

Application에는 고정 버전과 수동 Sync 정책을 지정한다. CRD, 컨트롤러, 의존 앱의 적용 순서와
삭제 영향도 PR에 적는다. 최초 애드온 검증에서는 각 앱을 순서대로 수동 Sync한다.
