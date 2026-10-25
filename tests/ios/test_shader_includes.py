"""Check the native shader tool's include resolution on external-volume copies."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT.parent / 'build_ios/build_darwin_tools/Release/bin/shader_tool'
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root / 'types.bsl.hh').write_text(
        '// Test shader.\n#pragma once\nnamespace scene { struct Types { float value; }; }\n')
    (root / 'prefix_types.bsl.hh').write_text(
        '// Test shader.\n#pragma once\nnamespace decoy { struct Types { float wrong; }; }\n')
    (root / '._types.bsl.hh').write_bytes(b'\x00\x05\x16\x07metadata, not shader source')
    source = root / 'main.bsl.hh'
    source.write_text('// Test shader.\n#pragma once\n#include "types.bsl.hh"\n'
                      'namespace scene { float sample(Types data) { return data.value; } }\n')
    output = root / 'processed.bsl.hh'
    subprocess.run([str(TOOL), str(source), str(output), str(root / 'metadata.hh'),
                    str(root / 'infos.hh'), str(root)], check=True)
    text = output.read_text()
    assert 'scene_Types' in text, text
    assert 'decoy_Types' not in text, text
print('Shader include lookup ignores AppleDouble and matches exact filenames.')
