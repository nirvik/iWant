import os, sys
import ConfigParser
try:
    from setuptools import setup, find_packages
except ImportError:
    from distutils.core import setup

requirement_list = [r.strip() for r in open('requirements.txt', 'r').readlines() if r]

def get_basepath():
    iwant_directory_path = os.path.expanduser('~')
    if sys.platform =='linux2' or sys.platform == 'linux' or sys.platform == 'darwin':
        iwant_directory_path = os.path.join(iwant_directory_path, '.iwant')
    elif sys.platform == 'win32':
        iwant_directory_path = os.path.join(os.getenv('APPDATA'),'.iwant')
    return iwant_directory_path

iwant_config_path = get_basepath()
print iwant_config_path
if not os.path.exists(iwant_config_path):
    os.mkdir(iwant_config_path)

config = ConfigParser.ConfigParser()
config.add_section('Paths')
config.set('Paths', 'Share', '/home/nirvik/Pictures')
config.set('Paths', 'Download', '/run/media/nirvik/Data/iWantDownload')

with open(os.path.join(iwant_config_path, '.iwant.conf'), 'w') as configfile:
    config.write(configfile)


setup(
        name='iwant',
        version='1.0.1',
        install_requires= requirement_list,
        author='Nirvik Ghosh',
        author_email='nirvik1993@gmail.com',
        packages = find_packages(),
        include_package_data = True,
        entry_points = {
            'console_scripts':[
                'iwanto=iwant.cli.main:ui',
                'iwanto-start=iwant.cli.main:main'
                ],
        },
        url="https://github.com/nirvik/iWant",
        description="CLI based decentralized peer to peer file sharing"
)

