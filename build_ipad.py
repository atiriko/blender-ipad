"""Prepare the checked-out experimental Blender iOS port on an Apple Silicon Mac."""
import argparse
import hashlib
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT
BUILD = ROOT.parent / "build_ios"


def run(command, cwd=ROOT):
    print("+ " + " ".join(str(arg) for arg in command), flush=True)
    subprocess.run([str(arg) for arg in command], cwd=cwd, check=True)


PYTHON_IOS_RELEASE = "3.13-b15"
PYTHON_IOS_ARCHIVE = "Python-3.13-iOS-support.b15.tar.gz"
PYTHON_IOS_SHA256 = "80175765a31babe43b0910395cf86ba4e8412adf1902b069d55b74d523ecc5d1"
PYTHON_IOS_ROOT = ROOT / ".local" / "ios-python" / "runtime"


def setup_fmt_headers():
    """Match OpenImageIO's bundled fmt ABI, including Blender's ranges header."""
    archive = ROOT / ".local" / "fmt-9.1.0.tar.gz"
    archive.parent.mkdir(parents=True, exist_ok=True)
    if not archive.is_file():
        url = "https://github.com/fmtlib/fmt/archive/refs/tags/9.1.0.tar.gz"
        with urllib.request.urlopen(url, timeout=120) as response:
            archive.write_bytes(response.read())
    if hashlib.sha256(archive.read_bytes()).hexdigest() != "5dea48d1fcddc3ec571ce2058e13910a0d4a6bab4cc09a809d8b1dd1c88ae6f2":
        raise RuntimeError(f"Checksum mismatch: {archive}")
    with tarfile.open(archive) as bundle:
        members = [m for m in bundle.getmembers()
                   if m.isfile() and m.name.startswith("fmt-9.1.0/include/fmt/")]
        for member in members:
            if not (archive.parent / member.name).resolve().is_relative_to(archive.parent.resolve()):
                raise RuntimeError(f"Unsafe archive entry: {member.name}")
        bundle.extractall(archive.parent, members=members)


def setup_python_runtime():
    """Use an ABI-compatible iOS runtime without modifying pinned submodules."""
    work = PYTHON_IOS_ROOT.parent
    work.mkdir(parents=True, exist_ok=True)
    archive = work / PYTHON_IOS_ARCHIVE
    if not archive.is_file():
        url = ("https://github.com/beeware/Python-Apple-support/releases/download/"
               f"{PYTHON_IOS_RELEASE}/{PYTHON_IOS_ARCHIVE}")
        print(f"Downloading {url}", flush=True)
        with urllib.request.urlopen(url, timeout=120) as response:
            archive.write_bytes(response.read())
    if hashlib.sha256(archive.read_bytes()).hexdigest() != PYTHON_IOS_SHA256:
        raise RuntimeError(f"Checksum mismatch: {archive}")
    if (PYTHON_IOS_ROOT / "Python.framework" / "Python").is_file():
        setup_python_packages()
        return
    with tarfile.open(archive) as bundle:
        members = [m for m in bundle.getmembers() if m.name.startswith((
            "Python.xcframework/ios-arm64/", "Python.xcframework/lib/"))]
        for member in members:
            target = work / member.name
            if not target.resolve().is_relative_to(work.resolve()):
                raise RuntimeError(f"Unsafe archive entry: {member.name}")
            if member.issym() and not (target.parent / member.linkname).resolve().is_relative_to(work.resolve()):
                raise RuntimeError(f"Unsafe archive link: {member.name}")
        bundle.extractall(work, members=members)
    device = work / "Python.xcframework" / "ios-arm64"
    PYTHON_IOS_ROOT.mkdir(parents=True, exist_ok=True)
    shutil.copytree(device / "Python.framework", PYTHON_IOS_ROOT / "Python.framework", dirs_exist_ok=True)
    shutil.copytree(device / "include", PYTHON_IOS_ROOT / "include", dirs_exist_ok=True)
    shutil.copytree(work / "Python.xcframework" / "lib", PYTHON_IOS_ROOT / "lib", dirs_exist_ok=True)
    shutil.copytree(device / "lib-arm64", PYTHON_IOS_ROOT / "lib", dirs_exist_ok=True)
    setup_python_packages()
    print(f"iOS Python runtime prepared at {PYTHON_IOS_ROOT}")


def setup_python_packages():
    wheel_name = "numpy-2.3.5.post1-cp313-cp313-ios_13_0_arm64_iphoneos.whl"
    wheel_hash = "e2506422471eb7a7568e444f27659e32b0942ddc083cc96d7a60e778197b56dc"
    wheel = PYTHON_IOS_ROOT.parent / wheel_name
    if not wheel.is_file():
        url = "https://pypi.anaconda.org/beeware/simple/numpy/2.3.5.post1/" + wheel_name
        print(f"Downloading {url}", flush=True)
        with urllib.request.urlopen(url, timeout=120) as response:
            wheel.write_bytes(response.read())
    if hashlib.sha256(wheel.read_bytes()).hexdigest() != wheel_hash:
        raise RuntimeError(f"Checksum mismatch: {wheel}")
    packages = PYTHON_IOS_ROOT / "lib" / "python3.13" / "site-packages"
    packages.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(wheel) as bundle:
        for name in bundle.namelist():
            if not (packages / name).resolve().is_relative_to(packages.resolve()):
                raise RuntimeError(f"Unsafe wheel entry: {name}")
        bundle.extractall(packages)
    # certifi is pure Python and data, so the pinned host package is portable.
    certifi = ROOT / "lib" / "macos_arm64" / "python" / "lib" / "python3.13" / "site-packages" / "certifi"
    shutil.copytree(certifi, packages / "certifi", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["setup", "setup-python", "configure", "build"])
    parser.add_argument("--team", default=os.environ.get("BLENDER_IOS_TEAM", ""))
    parser.add_argument("--signing-identity", default=os.environ.get("BLENDER_IOS_SIGNING_IDENTITY", ""),
                        help="Certificate SHA-1 or name used to sign bundled libraries")
    parser.add_argument("--bundle-id", default="personal.blender.ipad")
    parser.add_argument("--increased-memory", action="store_true",
                        help="Enable only when your signing profile supports this entitlement")
    parser.add_argument("--jobs", type=int, default=1,
                        help="Compiler jobs (default 1 to support 8 GB Macs)")
    parser.add_argument("--unsigned", action="store_true",
                        help="Build and package the app without a provisioning team; it cannot deploy yet")
    args = parser.parse_args()
    if sys.platform != "darwin" or platform.machine() != "arm64":
        parser.error("Use an Apple Silicon Mac for this initial build workflow.")
    if any(char.isspace() for char in str(ROOT)):
        parser.error("Copy the workspace to a path without spaces, e.g. ~/blender-ipad; upstream host-tool commands require this.")
    for tool in ("git", "cmake", "make", "xcodebuild", "xcrun"):
        if not shutil.which(tool):
            parser.error(f"Missing {tool}; install full Xcode, CMake, and Git LFS first.")
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    run(["xcrun", "--sdk", "iphoneos", "--show-sdk-path"])
    if args.stage == "setup":
        run(["git", "lfs", "version"], SOURCE)
        run(["git", "lfs", "install", "--local"], SOURCE)
        # GitHub mirrors do not host Blender's upstream LFS assets.
        run(["git", "config", "--local", "lfs.url",
             "https://projects.blender.org/blender/blender.git/info/lfs"], SOURCE)
        # Runtime assets are needed for the app; the regression corpus is not.
        run(["git", "-c", "lfs.activitytimeout=60",
             "-c", "lfs.transfer.maxretries=2", "lfs", "pull",
             "--exclude", "tests/**"], SOURCE)
        # Fetch exact gitlink revisions, rather than updating the source or library branches.
        libraries = ["lib/macos_arm64", "lib/ios_arm64"]
        run(["git", "-c", "submodule.lib/macos_arm64.update=checkout",
             "-c", "submodule.lib/ios_arm64.update=checkout",
             "submodule", "update", "--init", "--checkout", *libraries], SOURCE)
        for library in libraries:
            run(["git", "-c", "lfs.activitytimeout=60",
                 "-c", "lfs.transfer.maxretries=2", "lfs", "pull"], SOURCE / library)
        setup_python_runtime()
        setup_fmt_headers()
        print("Dependencies downloaded. Next run the configure stage.")
    elif args.stage == "setup-python":
        setup_python_runtime()
        setup_fmt_headers()
    elif args.stage == "configure":
        setup_fmt_headers()
        for library in ("macos_arm64", "ios_arm64"):
            if not (SOURCE / "lib" / library / "python").is_dir():
                parser.error("Missing prebuilt libraries; run setup first.")
        if not (PYTHON_IOS_ROOT / "Python.framework" / "Python").is_file():
            parser.error("Missing Python 3.13 iOS runtime; run setup-python first.")
        command = ["cmake", "-S", SOURCE, "-B", BUILD, "-G", "Xcode",
                   "-DAPPLE_TARGET_DEVICE=ios", "-DCMAKE_BUILD_TYPE=Release",
                   f"-DBLENDER_IOS_PYTHON_ROOT={PYTHON_IOS_ROOT}",
                   f"-DBLENDER_IOS_FMT_INCLUDE_DIR={ROOT}/.local/fmt-9.1.0/include",
                   "-DWITH_PYTHON_NUMPY=ON", "-DWITH_PYTHON_INSTALL_NUMPY=ON",
                   f"-DPYTHON_NUMPY_PATH={PYTHON_IOS_ROOT}/lib/python3.13/site-packages",
                   "-DWITH_MOD_FLUID=ON", "-DWITH_LIBMV=OFF",
                   f"-DBLENDER_IOS_BUNDLE_ID={args.bundle_id}",
                   f"-DBLENDER_IOS_DEVELOPMENT_TEAM={args.team}",
                   f"-DBLENDER_IOS_SIGNING_IDENTITY={args.signing_identity}",
                   "-DBLENDER_IOS_INCREASED_MEMORY_LIMIT=" +
                   ("ON" if args.increased_memory else "OFF")]
        run(command)
        print(f"Open {BUILD / 'Blender.xcodeproj'} to select your signing team and device.")
    else:
        if not (BUILD / "CMakeCache.txt").is_file():
            parser.error("Run configure first.")
        command = ["cmake", "--build", BUILD, "--config", "Release",
                   "--target", "install", "--parallel", args.jobs]
        if args.unsigned:
            command += ["--", "CODE_SIGNING_ALLOWED=NO"]
        run(command)
        if args.unsigned:
            print("Unsigned app packaged. Configure a signing team before deploying to an iPad.")
        else:
            print("Build/install completed. Use Xcode to deploy and verify the app on your iPad.")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        sys.exit(error.returncode)
