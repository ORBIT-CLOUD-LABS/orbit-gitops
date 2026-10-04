## Related Issue

Closes #

## Summary

<!--
무엇을, 왜 변경했는지 2~4개의 불릿으로 작성합니다.
YAML 수정 내용보다 클러스터에 반영되는 결과를 우선 작성합니다.

필요한 경우 아래 항목을 추가합니다.
- Image Changes: 변경한 application과 image tag 또는 digest
- Manifest Changes: Deployment, Service, ConfigMap 또는 Gateway 변경
- Environment Changes: 대상 cluster, namespace 또는 overlay 변경
- Sync Impact: Pod 재시작, rollout, 자원 재생성 또는 서비스 중단 가능성
- Configuration Changes: 환경 변수, resource limit 또는 replica 변경
-->

-

## Verification

<!--
저장소에서 사용하는 도구에 해당하는 검증만 작성합니다.

예:
- kustomize build 결과 확인
- helm template 결과 확인
- kubectl apply --dry-run=client 결과 확인
- Argo CD diff에서 Deployment image tag 변경만 확인
-->

-

- [ ] 변경한 manifest가 정상적으로 렌더링되는지 확인했습니다.
- [ ] 대상 환경과 namespace가 올바른지 확인했습니다.
- [ ] 배포할 image tag 또는 digest가 존재하는지 확인했습니다.
- [ ] 의도하지 않은 자원 삭제·재생성이 없는지 확인했습니다.
- [ ] Secret이나 credential을 평문으로 추가하지 않았습니다.

<!--
## To Reviewer

Argo CD 반영 범위, sync 순서, 서비스 중단 가능성,
rollback 방법 또는 환경별 차이가 있을 때만 작성합니다.
-->