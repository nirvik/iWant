import iwant
import os
try:
    from setuptools import setup, find_packages
except ImportError:
    from distutils.core import setup

requirement_list = [r.strip() for r in open('requirements.txt', 'r').readlines() if r]
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()
setup(
    name='iwant',
    version=iwant.__version__,
    install_requires= requirement_list,
    extras_require={':sys_platform == "win32"': ['pypiwin32']},
    author='Nirvik Ghosh',
    author_email='nirvik1993@gmail.com',
    packages = find_packages(),
    include_package_data = True,
    entry_points = {
        'console_scripts':[
            'iwanto=iwant.cli.main:main'
            ],
    },
    url='https://github.com/nirvik/iWant',
    description="CLI based decentralized peer to peer file sharing",
    classifiers=[
        'Framework :: Twisted',
        'Topic :: Communications :: File Sharing',
        'Topic :: System :: Networking',
        'Topic :: System :: Operating System',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License'
    ],
    long_description=read('README.rst')
)

