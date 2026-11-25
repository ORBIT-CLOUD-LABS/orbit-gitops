#!/usr/bin/env python3
"""ota/base/kustomization.yaml에서 orbit-server 이미지의 버전과 digest를 읽는다.

출력: <버전> <digest> (예: 1.2.4 sha256:...)
파일이 없으면 아무것도 출력하지 않고 0으로 끝난다. 형식이 틀리면 1로 끝난다.
"""
import re
import sys

import yaml

IMAGE = 'ghcr.io/orbit-cloud-labs/orbit-server'
VERSION = re.compile(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)')
DIGEST = re.compile(r'sha256:[0-9a-f]{64}')


class ImageError(RuntimeError):
    pass


def orbit_server_image(document):
    if not isinstance(document, dict):
        raise ImageError('Kustomization 파일이 아닙니다')
    entries = [
        entry for entry in document.get('images') or []
        if isinstance(entry, dict) and IMAGE in (entry.get('name'), entry.get('newName'))
    ]
    if len(entries) != 1:
        raise ImageError('orbit-server images 항목이 정확히 하나여야 합니다')
    version = str(entry_value(entries[0], 'newTag'))
    digest = str(entry_value(entries[0], 'digest'))
    if not VERSION.fullmatch(version):
        raise ImageError(f'newTag가 버전 형식이 아닙니다: {version}')
    if not DIGEST.fullmatch(digest):
        raise ImageError(f'digest 형식이 잘못됐습니다: {digest}')
    return version, digest


def entry_value(entry, key):
    if key not in entry:
        raise ImageError(f'orbit-server images 항목에 {key}가 없습니다')
    return entry[key]


def main(argv):
    if len(argv) != 1:
        print('사용법: ota_image.py <kustomization.yaml>', file=sys.stderr)
        return 2
    try:
        with open(argv[0], encoding='utf-8') as stream:
            text = stream.read()
    except FileNotFoundError:
        return 0
    try:
        version, digest = orbit_server_image(yaml.safe_load(text))
    except (ImageError, yaml.YAMLError) as error:
        print(f'이미지 읽기 실패: {error}', file=sys.stderr)
        return 1
    print(version, digest)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
