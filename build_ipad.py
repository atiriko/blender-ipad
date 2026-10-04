"""Prepare the checked-out experimental Blender iOS port on an Apple Silicon Mac."""
import argparse
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT
BUILD = ROOT.parent / "build_ios"


def run(command, cwd=ROOT):
    print("+ " + " ".join(str(arg) for arg in command), flush=True)
    subprocess.run([str(arg) for arg in command], cwd=cwd, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["setup", "configure", "build"])
    parser.add_argument("--team", default=os.environ.get("BLENDER_IOS_TEAM", ""))
    parser.add_argument("--bundle-id", default="personal.blender.ipad")
    parser.add_argument("--increased-memory", action="store_true",
                        help="Enable only when your signing profile supports this entitlement")
    parser.add_argument("--jobs", type=int, default=4)
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
        run(["git", "lfs", "pull"], SOURCE)
        # Fetch exact gitlink revisions, rather than updating the source or library branches.
        libraries = ["lib/macos_arm64", "lib/ios_arm64"]
        run(["git", "-c", "submodule.lib/macos_arm64.update=checkout",
             "-c", "submodule.lib/ios_arm64.update=checkout",
             "submodule", "update", "--init", "--checkout", *libraries], SOURCE)
        for library in libraries:
            run(["git", "lfs", "pull"], SOURCE / library)
        print("Dependencies downloaded. Next run the configure stage.")
    elif args.stage == "configure":
        for library in ("macos_arm64", "ios_arm64"):
            if not (SOURCE / "lib" / library / "python").is_dir():
                parser.error("Missing prebuilt libraries; run setup first.")
        command = ["cmake", "-S", SOURCE, "-B", BUILD, "-G", "Xcode",
                   "-DAPPLE_TARGET_DEVICE=ios", "-DCMAKE_BUILD_TYPE=Release",
                   f"-DBLENDER_IOS_BUNDLE_ID={args.bundle_id}",
                   f"-DBLENDER_IOS_DEVELOPMENT_TEAM={args.team}",
                   "-DBLENDER_IOS_INCREASED_MEMORY_LIMIT=" +
                   ("ON" if args.increased_memory else "OFF")]
        run(command)
        print(f"Open {BUILD / 'Blender.xcodeproj'} to select your signing team and device.")
    else:
        if not (BUILD / "CMakeCache.txt").is_file():
            parser.error("Run configure first.")
        run(["cmake", "--build", BUILD, "--config", "Release",
             "--target", "install", "--parallel", args.jobs])
        print("Build/install completed. Use Xcode to deploy and verify the app on your iPad.")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        sys.exit(error.returncode)
