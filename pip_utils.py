"""
Morzio Hair Factory
Copyright (C) 2025 Demingo Hill (Noizirom)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

from sys import executable
from subprocess import check_call, check_output
from pathlib import Path


def pip_install(package_name):
    check_call([executable, "-m", "pip", "install", package_name])


def pip_uninstall(package_name):
    check_call([executable, "-m", "pip", "uninstall", package_name, "-y"])


def pip_list():
    installed = check_output([executable, "-m", "pip", "freeze"]).decode('utf-8')
    return (i.split("==")[0] for i in installed.split("\r\n")[:-1])


def not_installed(name):
    return name not in pip_list()


def read_requirements(req_dir):
    with open(str(Path(req_dir).joinpath("requirements.txt")), 'r') as f:
        for line in f:
            yield line.split("\n")[0]


def requirements_not_installed_mask(req_dir):
    pl = pip_list()
    req_pkg = read_requirements(req_dir)
    return (name not in pl for name in req_pkg)


def requirements_not_installed_dict(req_dir):
    pl = pip_list()
    req_pkg = read_requirements(req_dir)
    return {name: name not in pl for name in req_pkg}


def pip_install_wheel_from(package_name, source_dir):
    check_call([executable, "-m", "pip", "install", '--no-index', f'--find-links={str(source_dir)}', package_name])


def pip_install_wheel_from_requirements(source_dir, req_dir=None):
    if req_dir == None:
        req_dir = source_dir
    check_call([executable, "-m", "pip", "install", '--no-index', f'--find-links={str(source_dir)}', '-r', f'{str(Path(req_dir).joinpath("requirements.txt"))}'])

