"""Package CPython iOS extension modules as frameworks with .fwork markers."""

import argparse
from pathlib import Path
import plistlib
import shutil


def package_extensions(app, python_relative, bundle_id):
    app = Path(app)
    python = app / python_relative
    if not python.is_dir():
        raise RuntimeError(f"Missing installed Python standard library: {python}")
    # External-volume metadata must not become extension frameworks or resources.
    for sidecar in app.rglob("._*"):
        if sidecar.is_file() and not sidecar.is_symlink():
            sidecar.unlink()
    for base in (python / "lib-dynload", python / "site-packages"):
        for extension in sorted(base.rglob("*.so")):
            relative = extension.relative_to(base)
            module = ".".join((*relative.parts[:-1], relative.name.split(".")[0]))
            framework = app / "Frameworks" / f"{module}.framework"
            framework.mkdir(parents=True, exist_ok=True)
            info = {
                "CFBundleExecutable": module,
                "CFBundleIdentifier": f"{bundle_id}.{module}".replace("_", "-"),
                "CFBundlePackageType": "FMWK",
                "CFBundleVersion": "1",
                "CFBundleShortVersionString": "1.0",
                "CFBundleSupportedPlatforms": ["iPhoneOS"],
                "MinimumOSVersion": "16.0",
            }
            (framework / "Info.plist").write_bytes(plistlib.dumps(info))
            binary = framework / module
            shutil.move(str(extension), binary)
            marker = extension.with_suffix(".fwork")
            marker.write_text(binary.relative_to(app).as_posix() + "\n")
            (framework / f"{module}.origin").write_text(marker.relative_to(app).as_posix() + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", required=True, type=Path)
    parser.add_argument("--python-relative", required=True)
    parser.add_argument("--bundle-id", required=True)
    args = parser.parse_args()
    package_extensions(args.app, args.python_relative, args.bundle_id)
