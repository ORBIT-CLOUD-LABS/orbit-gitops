import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import ota_image  # noqa: E402

DIGEST = 'sha256:' + 'a' * 64


def kustomization(**entry):
    base = {'name': ota_image.IMAGE, 'newTag': '1.2.4', 'digest': DIGEST}
    base.update(entry)
    return {'images': [{'name': 'example/sidecar', 'newTag': '1'}, {k: v for k, v in base.items() if v is not None}]}


class OrbitServerImageTest(unittest.TestCase):
    def test_reads_version_and_digest(self):
        self.assertEqual(ota_image.orbit_server_image(kustomization()), ('1.2.4', DIGEST))

    def test_new_name_entry(self):
        doc = kustomization(name='orbit-server', newName=ota_image.IMAGE)
        self.assertEqual(ota_image.orbit_server_image(doc), ('1.2.4', DIGEST))

    def test_missing_digest_fails(self):
        with self.assertRaisesRegex(ota_image.ImageError, 'digest가 없습니다'):
            ota_image.orbit_server_image(kustomization(digest=None))

    def test_moving_or_sha_tag_fails(self):
        for tag in ('prod', 'latest', 'sha-1a2b3c4', 'v1.2.4'):
            with self.subTest(tag=tag), self.assertRaisesRegex(ota_image.ImageError, '버전 형식'):
                ota_image.orbit_server_image(kustomization(newTag=tag))

    def test_bad_digest_fails(self):
        with self.assertRaisesRegex(ota_image.ImageError, 'digest 형식'):
            ota_image.orbit_server_image(kustomization(digest='sha256:abc'))

    def test_missing_or_duplicate_entry_fails(self):
        doc = kustomization()
        for images in ([], doc['images'] + doc['images'][1:]):
            with self.subTest(count=len(images)), self.assertRaisesRegex(ota_image.ImageError, '정확히 하나'):
                ota_image.orbit_server_image({'images': images})


class MainTest(unittest.TestCase):
    def run_main(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / 'kustomization.yaml'
            if text is not None:
                path.write_text(text, encoding='utf-8')
            with mock.patch('builtins.print') as printed:
                code = ota_image.main([str(path)])
        return code, printed

    def test_prints_version_and_digest(self):
        text = f'images:\n  - name: {ota_image.IMAGE}\n    newTag: "1.2.4"\n    digest: {DIGEST}\n'
        code, printed = self.run_main(text)
        self.assertEqual(code, 0)
        printed.assert_called_once_with('1.2.4', DIGEST)

    def test_missing_file_prints_nothing(self):
        code, printed = self.run_main(None)
        self.assertEqual(code, 0)
        printed.assert_not_called()

    def test_broken_yaml_fails(self):
        code, _ = self.run_main('images: [\n')
        self.assertEqual(code, 1)


if __name__ == '__main__':
    unittest.main()
