import os, sys
from iwant.utils import get_basepath
try:
    from setuptools import setup, find_packages
except ImportError:
    from distutils.core import setup

requirement_list = [r.strip() for r in open('requirements.txt', 'r').readlines() if r]


iwant_config_path = get_basepath()
print iwant_config_path
if not os.path.exists(iwant_config_path):
    os.mkdir(iwant_config_path)
non_package_data = [(iwant_config_path, ['iwant/.iwant.conf'])]

setup(
        name='iwant',
        version='1.0.0',
        install_requires= requirement_list,
        author='Nirvik Ghosh',
        author_email='nirvik1993@gmail.com',
        packages = find_packages(),
        include_package_data = True,
        data_files = non_package_data,
        entry_points = {
            'console_scripts':[
                'iwanto=iwant.cli.main:ui',
                'iwanto-start=iwant.cli.main:main'
                ],
        },
        url="https://github.com/nirvik/iWant",
        description="CLI based decentralized peer to peer file sharing"
)

