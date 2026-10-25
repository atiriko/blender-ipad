"""Check Python framework markers, metadata, and repeat installation behavior."""
from pathlib import Path
import importlib.util
import plistlib
import tempfile

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('ios_python', ROOT / 'build_files/utils/prepare_ios_python.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
with tempfile.TemporaryDirectory() as directory:
    app = Path(directory) / 'Blender.app'
    relative = 'Assets/5.1/python/lib/python3.13'
    runtime = app / relative
    for name in ('lib-dynload/math.cpython-313-iphoneos.so',
                 'site-packages/numpy/_core/_multiarray_umath.cpython-313-iphoneos.so'):
        path = runtime / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'test binary')
    (runtime / 'lib-dynload/._math.cpython-313-iphoneos.so').write_bytes(b'metadata')
    (app / '._resource').write_bytes(b'metadata')
    module.package_extensions(app, relative, 'personal.test.blender')
    assert not list(app.rglob('._*')), 'AppleDouble metadata must not enter the app'
    assert not list(runtime.rglob('*.so'))
    for marker in runtime.rglob('*.fwork'):
        binary = app / marker.read_text().strip()
        assert binary.read_bytes() == b'test binary'
        assert (binary.parent / (binary.name + '.origin')).read_text().strip() == marker.relative_to(app).as_posix()
        info = plistlib.loads((binary.parent / 'Info.plist').read_bytes())
        assert info['CFBundleExecutable'] == binary.name
        assert '_' not in info['CFBundleIdentifier']
    assert len(list(runtime.rglob('*.fwork'))) == 2
    module.package_extensions(app, relative, 'personal.test.blender')
    assert len(list(runtime.rglob('*.fwork'))) == 2
    try:
        module.package_extensions(app, 'missing', 'personal.test.blender')
    except RuntimeError:
        pass
    else:
        raise AssertionError('Missing runtime must fail')
    print('Python extension framework packaging and repeat installation passed.')
