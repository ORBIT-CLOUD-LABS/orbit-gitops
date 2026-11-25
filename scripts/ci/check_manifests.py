#!/usr/bin/env python3
"""kustomize build 결과(여러 문서 YAML)를 읽어 배포 규칙을 검사한다.

검사 항목
- 모든 컨테이너(initContainers 포함)에 CPU·메모리 requests와 limits가 있다.

사용법: check_manifests.py <렌더링된 YAML 파일>...  ('-'는 표준 입력)
위반이 하나라도 있으면 목록을 출력하고 종료 코드 1로 끝난다.
"""

import sys

import yaml

# Pod spec이 들어 있는 위치. 키가 없으면 Pod spec이 없는 리소스로 보고 건너뛴다.
POD_SPEC_PATHS = {
    "Pod": ("spec",),
    "Deployment": ("spec", "template", "spec"),
    "StatefulSet": ("spec", "template", "spec"),
    "DaemonSet": ("spec", "template", "spec"),
    "ReplicaSet": ("spec", "template", "spec"),
    "Job": ("spec", "template", "spec"),
    "CronJob": ("spec", "jobTemplate", "spec", "template", "spec"),
}

CONTAINER_FIELDS = ("initContainers", "containers")
REQUIRED_RESOURCES = ("cpu", "memory")


def pod_spec(doc):
    path = POD_SPEC_PATHS.get(doc.get("kind"))
    if path is None:
        return None
    node = doc
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node if isinstance(node, dict) else None


def iter_containers(spec):
    for field in CONTAINER_FIELDS:
        for container in spec.get(field) or []:
            if isinstance(container, dict):
                yield field, container


def resource_errors(container):
    errors = []
    resources = container.get("resources") or {}
    for section in ("requests", "limits"):
        values = resources.get(section) or {}
        for name in REQUIRED_RESOURCES:
            if name not in values:
                errors.append(f"resources.{section}.{name} 없음")
    return errors


def describe(doc):
    meta = doc.get("metadata") or {}
    namespace = meta.get("namespace")
    name = meta.get("name", "<이름 없음>")
    where = f"{namespace}/{name}" if namespace else name
    return f"{doc.get('kind')} {where}"


def check_documents(docs):
    violations = []
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        spec = pod_spec(doc)
        if spec is None:
            continue
        for field, container in iter_containers(spec):
            target = f"{describe(doc)} {field}[{container.get('name', '?')}]"
            for error in resource_errors(container):
                violations.append(f"{target}: {error}")
    return violations


def load(path):
    if path == "-":
        return list(yaml.safe_load_all(sys.stdin))
    with open(path, encoding="utf-8") as stream:
        return list(yaml.safe_load_all(stream))


def main(argv):
    if not argv:
        print("사용법: check_manifests.py <렌더링된 YAML 파일>...", file=sys.stderr)
        return 2
    violations = []
    for path in argv:
        for violation in check_documents(load(path)):
            violations.append(f"{path}: {violation}")
    for violation in violations:
        print(violation)
    if violations:
        print(f"위반 {len(violations)}건", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
