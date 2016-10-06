import os, sys
try:
    from setuptools import setup, find_packages
except ImportError:
    from distutils.core import setup

requirement_list = [r.strip() for r in open('requirements.txt', 'r').readlines() if r]

if sys.platform == 'win32':
    if not os.path.exists(os.environ['USERPROFILE'] + '\\AppData\\iwant'):
        os.mkdir(os.environ['USERPROFILE'] + '\\AppData\\iwant')
    non_package_data = [(os.environ['USERPROFILE'] + '\\AppData\\iwant', ['iwant\\.iwant.conf'])]

elif sys.platform == 'linux2' or sys.platform == 'linux':
    if not os.path.exists('/var/log/iwant'):
        os.mkdir('/var/log/iwant')
    non_package_data = [('/home/'+os.getenv('SUDO_USER'), ['iwant/.iwant.conf'])]

elif sys.platform == 'darwin':
    # TODO
    pass

setup(
        name='iwant',
        version='1.0.0',
        install_requires= requirement_list,
        author='Nirvik Ghosh',
        author_email='nirvik1993@gmail.com',
        packages = find_packages(),
        include_package_data = True,
        data_files = non_package_data,  # [('/home/'+os.getenv('SUDO_USER'), ['iwant/.iwant.conf'])],
        entry_points = {
            'console_scripts':[
                'iwanto-start=iwant.main:main',
                'iwanto=iwant.ui:main'
                ],
        },
        url="https://github.com/nirvik/iWant",
        description="CLI based decentralized peer to peer file sharing"
)

