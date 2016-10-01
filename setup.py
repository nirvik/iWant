import os
try:
    from setuptools import setup, find_packages
except ImportError:
    from distutils.core import setup

requirement_list = [r.strip() for r in open('requirements.txt', 'r').readlines() if r]

setup(
        name='iwant',
        version='1.0.0',
        install_requires= requirement_list,
        author='Nirvik Ghosh',
        author_email='nirvik1993@gmail.com',
        packages = find_packages(),
        include_package_data = True,
        data_files = [('/home/'+os.getenv('SUDO_USER'), ['iwant/.iwant.conf'])],
        entry_points = {
            'console_scripts':[
                'iwanto-start=iwant.main:main',
                'iwanto=iwant.ui:main'
                ],
        },
        url="https://github.com/nirvik/iWant",
        description="CLI based decentralized peer to peer file sharing"
)

