try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

requirement_list = [r.strip() for r in open('requirements.txt', 'r').readlines() if r]

setup(
        name='iwant',
        version='1.0.0',
        install_requires= requirement_list,
        author='Nirvik Ghosh',
        author_email='nirvik1993@gmail.com',
        packages=['iwant','iwant.communication','iwant.communication.election_communication','iwant.consensus','iwant.constants.events','iwant.constants.states','iwant.constants','iwant.shared','iwant.utils','iwant.filehashIndex'],
        entry_points = {
            #'console_scripts':['iwanto-start=iwant:main','iwanto=iwant:userinterface'],
        },
        url="https://github.com/nirvik/iWant",
        description="CLI based decentralized peer to peer file sharing")
