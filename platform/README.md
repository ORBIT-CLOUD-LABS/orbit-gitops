# 플랫폼 애드온

애드온별 manifest는 `platform/<addon>/`에 둔다. 자식 Application은
`clusters/orbit-astra/apps/<addon>.yaml`에 추가하며 `spec.project: platform`을 사용한다.

실제 애드온을 추가하기 전에 infrastructure의 `argocd_gitops` 롤에서 대상 namespace,
필요한 namespaced 리소스 종류, ClusterRole·CRD 등 클러스터 리소스 종류를 검토하여
명시적으로 허용한다. 외부 Helm chart를 직접 참조하면 해당 chart 저장소도 AppProject의
sourceRepos에 명시적으로 추가해야 한다.

Application에는 고정 버전과 README의 자동 Sync·제한된 재시도 기준을 적용한다.
Prune·Self Heal은 비활성화한다. CRD, 컨트롤러, 의존 앱의 선행 조건을 준비한 뒤
Application을 반영하며 적용 순서와 삭제 영향도 PR에 적는다. main 반영만으로
배포가 시작될 수 있으므로 필요한 Secret·권한·namespace를 먼저 준비한다.
