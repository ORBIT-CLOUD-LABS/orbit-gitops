import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import check_manifests  # noqa: E402

FULL_RESOURCES = {
    "requests": {"cpu": "100m", "memory": "128Mi"},
    "limits": {"cpu": "200m", "memory": "128Mi"},
}
GOOD_IMAGE = "ghcr.io/orbit-cloud-labs/orbit-server:1.2.4@sha256:" + "a" * 64


def container(name="app", image=GOOD_IMAGE, resources=None):
    item = {"name": name, "image": image}
    if resources is not None:
        item["resources"] = resources
    return item


def deployment(containers, init_containers=None, kind="Deployment"):
    spec = {"containers": containers}
    if init_containers is not None:
        spec["initContainers"] = init_containers
    return {
        "apiVersion": "apps/v1",
        "kind": kind,
        "metadata": {"name": "orbit-server", "namespace": "ota"},
        "spec": {"template": {"spec": spec}},
    }


class ResourceCheckTest(unittest.TestCase):
    def test_full_resources_pass(self):
        docs = [deployment([container(resources=FULL_RESOURCES)])]
        self.assertEqual(check_manifests.check_documents(docs), [])

    def test_missing_resources_fail(self):
        docs = [deployment([container()])]
        violations = check_manifests.check_documents(docs)
        self.assertEqual(len(violations), 4)
        self.assertIn("resources.requests.cpu 없음", violations[0])

    def test_missing_memory_limit_fail(self):
        resources = {
            "requests": {"cpu": "100m", "memory": "128Mi"},
            "limits": {"cpu": "200m"},
        }
        violations = check_manifests.check_documents([deployment([container(resources=resources)])])
        self.assertEqual(len(violations), 1)
        self.assertIn("resources.limits.memory 없음", violations[0])

    def test_init_container_checked(self):
        docs = [deployment([container(resources=FULL_RESOURCES)], [container(name="migrate")])]
        violations = check_manifests.check_documents(docs)
        self.assertEqual(len(violations), 4)
        self.assertIn("initContainers[migrate]", violations[0])

    def test_cronjob_checked(self):
        doc = {
            "kind": "CronJob",
            "metadata": {"name": "cleanup"},
            "spec": {"jobTemplate": {"spec": {"template": {"spec": {"containers": [container()]}}}}},
        }
        self.assertEqual(len(check_manifests.check_documents([doc])), 4)

    def test_pod_checked(self):
        doc = {"kind": "Pod", "metadata": {"name": "debug"}, "spec": {"containers": [container()]}}
        self.assertEqual(len(check_manifests.check_documents([doc])), 4)

    def test_non_workload_ignored(self):
        docs = [
            {"kind": "Service", "metadata": {"name": "orbit-server"}, "spec": {"ports": []}},
            {"kind": "ConfigMap", "metadata": {"name": "c"}, "data": {}},
            None,
        ]
        self.assertEqual(check_manifests.check_documents(docs), [])


class ImageCheckTest(unittest.TestCase):
    def check(self, image):
        return check_manifests.image_errors(image)

    def test_version_with_digest_pass(self):
        self.assertEqual(self.check(GOOD_IMAGE), [])

    def test_v_prefix_and_suffix_pass(self):
        digest = "@sha256:" + "b" * 64
        self.assertEqual(self.check("docker.io/fluent/fluent-bit:v3.1.9" + digest), [])
        self.assertEqual(self.check("bitnami/kubectl:1.35.0-debian-12-r0" + digest), [])

    def test_registry_port_pass(self):
        image = "registry.local:5000/orbit/orbit-server:1.0.0@sha256:" + "c" * 64
        self.assertEqual(self.check(image), [])

    def test_tag_only_fail(self):
        errors = self.check("ghcr.io/orbit-cloud-labs/orbit-server:1.2.4")
        self.assertEqual(len(errors), 1)
        self.assertIn("digest", errors[0])

    def test_digest_only_fail(self):
        errors = self.check("ghcr.io/orbit-cloud-labs/orbit-server@sha256:" + "a" * 64)
        self.assertEqual(len(errors), 1)
        self.assertIn("버전 태그 없음", errors[0])

    def test_moving_tags_fail(self):
        for tag in ("latest", "prod"):
            with self.subTest(tag=tag):
                errors = self.check(f"ghcr.io/orbit-cloud-labs/orbit-server:{tag}@sha256:" + "a" * 64)
                self.assertEqual(len(errors), 1)
                self.assertIn("이동 태그", errors[0])

    def test_sha_tag_fail(self):
        errors = self.check("ghcr.io/orbit-cloud-labs/orbit-server:sha-1a2b3c4@sha256:" + "a" * 64)
        self.assertEqual(len(errors), 1)
        self.assertIn("sha-", errors[0])

    def test_non_version_tag_fail(self):
        errors = self.check("ghcr.io/orbit-cloud-labs/orbit-server:main@sha256:" + "a" * 64)
        self.assertEqual(len(errors), 1)
        self.assertIn("버전 형식", errors[0])

    def test_bad_digest_fail(self):
        errors = self.check("ghcr.io/orbit-cloud-labs/orbit-server:1.2.4@sha256:abc")
        self.assertEqual(len(errors), 1)
        self.assertIn("digest 형식", errors[0])

    def test_missing_image_fail(self):
        self.assertEqual(self.check(None), ["image 없음"])

    def test_document_reports_image_violation(self):
        image = "ghcr.io/orbit-cloud-labs/orbit-server:latest"
        docs = [deployment([container(image=image, resources=FULL_RESOURCES)])]
        violations = check_manifests.check_documents(docs)
        self.assertEqual(len(violations), 1)
        self.assertIn("Deployment ota/orbit-server containers[app]", violations[0])


if __name__ == "__main__":
    unittest.main()
