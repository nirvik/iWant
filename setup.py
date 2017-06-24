import iwant
import os
try:
    from setuptools import setup, find_packages
except ImportError:
    from distutils.core import setup

requirement_list = [r.strip() for r in open('requirements.txt', 'r').readlines() if r]
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

print read('README.md')
setup(
    name='iwant',
    version=iwant.__version__,
    install_requires= requirement_list,
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
        'Topic :: System :: Operating System'
    ],
    long_description=read('README')
)

