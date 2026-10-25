"""Validate the configured install script using a fake codesign executable."""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
source = (ROOT / 'build_files/cmake/platform/ios_sign_libraries.cmake.in').read_text()
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    binary = root / 'bin'
    binary.mkdir()
    (root / 'lib').mkdir()
    (root / 'lib' / 'test.dylib').touch()
    (root / 'lib' / '._test.dylib').touch()
    signer = binary / 'codesign'
    signer.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$@" >> "$SIGN_LOG"\n'
        'if [ "$1" = "--verify" ] && [ "$SIGN_FAIL_ACTION" = "verify" ]; then exit 1; fi\n'
        'case "$*" in *--preserve-metadata*) '
        'if [ "$SIGN_FAIL_ACTION" = "app" ]; then exit 1; fi;; esac\n'
        'exit "${SIGN_RESULT:-0}"\n')
    signer.chmod(0o755)
    env = dict(os.environ, PATH=str(binary) + ':' + os.environ['PATH'],
               SIGN_LOG=str(root / 'sign.log'))

    def run(identity='', result='0', xcode='', allowed='YES', fail_action=''):
        script = source.replace('@BLENDER_IOS_SIGNING_IDENTITY@', identity)
        script = script.replace('@TARGETDIR_LIB@', 'lib').replace('@TARGETDIR_VER@', '5.1')
        script = script.replace('@PYTHON_VERSION@', '3.11')
        path = root / 'sign.cmake'
        path.write_text(script)
        return subprocess.run(['cmake', '-DCMAKE_INSTALL_PREFIX=' + directory,
                               '-P', str(path)], capture_output=True, text=True,
                              env=dict(env, SIGN_RESULT=result,
                                       EXPANDED_CODE_SIGN_IDENTITY=xcode,
                                       CODE_SIGNING_ALLOWED=allowed,
                                       SIGN_FAIL_ACTION=fail_action))

    assert run().returncode != 0, 'Missing identity must fail'
    assert run('test identity', xcode='other identity').returncode == 0
    args = (root / 'sign.log').read_text().splitlines()
    assert args == ['--sign', 'test identity', '--force', str(root / 'lib' / 'test.dylib')]
    assert run('test identity', '1').returncode != 0, 'Signing failure must stop install'
    assert run(xcode='xcode identity').returncode == 0
    (root / 'Blender.app').mkdir()
    (root / 'Blender.app' / '._resource').write_bytes(b'metadata')
    (root / 'sign.log').unlink()
    assert run('app identity').returncode == 0
    assert not (root / 'Blender.app' / '._resource').exists()
    args = (root / 'sign.log').read_text().splitlines()
    assert args == [
        '--sign', 'app identity', '--force', str(root / 'lib' / 'test.dylib'),
        '--sign', 'app identity', '--force',
        '--preserve-metadata=entitlements,requirements,flags',
        '--generate-entitlement-der', str(root / 'Blender.app'),
        '--verify', '--deep', '--strict', str(root / 'Blender.app'),
    ], 'The installed app must be signed and verified after its libraries'
    assert run('app identity', fail_action='app').returncode != 0
    assert run('app identity', fail_action='verify').returncode != 0
    assert run('-').returncode != 0, 'Ad hoc signing cannot deploy to a device'
    before = (root / 'sign.log').read_bytes()
    (root / 'Blender.app' / '._resource').write_bytes(b'metadata')
    assert run(allowed='NO').returncode == 0
    assert not (root / 'Blender.app' / '._resource').exists()
    assert (root / 'sign.log').read_bytes() == before, 'Unsigned packaging must not sign libraries'
    print('Library signing identity selection and failure handling passed.')
