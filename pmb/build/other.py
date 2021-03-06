"""
Copyright 2017 Oliver Smith

This file is part of pmbootstrap.

pmbootstrap is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

pmbootstrap is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with pmbootstrap.  If not, see <http://www.gnu.org/licenses/>.
"""
import os
import logging
import glob

import pmb.chroot
import pmb.helpers.run
import pmb.helpers.file
import pmb.parse.apkindex


def find_aport(args, package, must_exist=True):
    """
    Find the aport, that provides a certain subpackage.

    :param must_exist: Raise an exception, when not found
    :returns: the full path to the aport folder
    """
    path = args.aports + "/" + package
    if os.path.exists(path):
        return path

    for path_current in glob.glob(args.aports + "/*/APKBUILD"):
        apkbuild = pmb.parse.apkbuild(path_current)
        if package in apkbuild["subpackages"]:
            return os.path.dirname(path_current)
    if must_exist:
        raise RuntimeError("Could not find aport for package: " +
                           package)
    return None


def copy_to_buildpath(args, package, suffix="native"):
    # Sanity check
    aport = args.aports + "/" + package
    if not os.path.exists(aport + "/APKBUILD"):
        raise ValueError("Path does not contain an APKBUILD file:" +
                         aport)

    # Clean up folder
    build = args.work + "/chroot_" + suffix + "/home/user/build"
    if os.path.exists(build):
        pmb.chroot.root(args, ["rm", "-rf", "/home/user/build"],
                        suffix=suffix)

    # Copy aport contents
    pmb.helpers.run.root(args, ["cp", "-r", aport + "/", build])
    pmb.chroot.root(args, ["chown", "-R", "user:user",
                           "/home/user/build"], suffix=suffix)


def is_necessary(args, arch, apkbuild, apkindex_path=None):
    """
    Check if the package has already been built. Compared to abuild's check,
    this check also works for different architectures, and it recognizes
    changed files in an aport folder, even if the pkgver and pkgrel did not
    change.

    :param arch: package target architecture
    :param apkbuild: from pmb.parse.apkbuild()
    :param apkindex_path: override the APKINDEX.tar.gz path
    :returns: boolean
    """
    # Get new version from APKBUILD
    package = apkbuild["pkgname"]
    version_new = apkbuild["pkgver"] + "-r" + apkbuild["pkgrel"]

    # Get old version from APKINDEX
    if apkindex_path:
        index_data = pmb.parse.apkindex.read(
            args, package, apkindex_path, False)
    else:
        index_data = pmb.parse.apkindex.read_any_index(args, package, arch)
    if not index_data:
        return True

    # a) Binary repo has a newer version
    version_old = index_data["version"]
    if pmb.parse.apkindex.compare_version(version_old,
                                          version_new) == 1:
        logging.warning("WARNING: Package '" + package + "' in your aports folder"
                        " has version " + version_new + ", but the binary package"
                        " repositories already have version " + version_old + "!")
        return False

    # b) Aports folder has a newer version
    if version_new != version_old:
        return True

    # c) The version is the same. Check if all files in the aport folder have an
    # older timestamp, than the package. This way the pkgrel doesn't need to be
    # increased while developing locally.
    lastmod_target = float(index_data["timestamp"])
    path_sources = glob.glob(args.aports + "/" + package + "/*")
    if pmb.helpers.file.is_up_to_date(
            path_sources, lastmod_target=lastmod_target):
        return False
    return True


def index_repo(args, arch=None):
    """
    :param arch: when not defined, re-index all repos
    """
    pmb.build.init(args)

    if arch:
        paths = [args.work + "/packages/" + arch]
    else:
        paths = glob.glob(args.work + "/packages/*")

    for path in paths:
        path_arch = os.path.basename(path)
        path_repo_chroot = "/home/user/packages/user/" + path_arch
        logging.info("(native) index " + path_arch + " repository")
        commands = [
            ["apk", "index", "--output", "APKINDEX.tar.gz_",
             "--rewrite-arch", path_arch, "*.apk"],
            ["abuild-sign", "APKINDEX.tar.gz_"],
            ["mv", "APKINDEX.tar.gz_", "APKINDEX.tar.gz"]
        ]
        for command in commands:
            pmb.chroot.user(args, command, working_dir=path_repo_chroot)


def symlink_noarch_package(args, arch_apk):
    """
    :param arch_apk: for example: x86_64/mypackage-1.2.3-r0.apk
    """

    for arch in pmb.config.build_device_architectures:
        # Create the arch folder
        arch_folder = "/home/user/packages/user/" + arch
        arch_folder_outside = args.work + "/packages/" + arch
        if not os.path.exists(arch_folder_outside):
            pmb.chroot.user(args, ["mkdir", "-p", arch_folder])

        # Add symlink, rewrite index
        pmb.chroot.user(args, ["ln", "-sf", "../" + arch_apk, "."],
                        working_dir=arch_folder)
        index_repo(args, arch)


def ccache_stats(args, arch):
    suffix = "native"
    if args.arch:
        suffix = "buildroot_" + arch
    pmb.chroot.user(args, ["ccache", "-s"], suffix, log=False)


# set the correct JOBS count in abuild.conf
def configure_abuild(args, suffix, verify=False):
    path = args.work + "/chroot_" + suffix + "/etc/abuild.conf"
    prefix = "export JOBS="
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if not line.startswith(prefix):
                continue
            if line != (prefix + args.jobs + "\n"):
                if verify:
                    raise RuntimeError("Failed to configure abuild: " + path +
                                       "\nTry to delete the file (or zap the chroot).")
                pmb.chroot.root(args, ["sed", "-i", "-e",
                                       "s/^" + prefix + ".*/" + prefix + args.jobs + "/",
                                       "/etc/abuild.conf"], suffix)
                configure_abuild(args, suffix, True)
            return
    raise RuntimeError("Could not find " + prefix + " line in " + path)
