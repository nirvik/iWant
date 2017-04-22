from netifaces import interfaces, ifaddresses, AF_INET
import os
import sys
import ConfigParser
import time_uuid
from iwant.core.exception import MainException


def get_ips():
    ip_list = []
    for interface in interfaces():
        try:
            for link in ifaddresses(interface)[AF_INET]:
                ip_list.append(link['addr'])
        except:
            pass
    return ip_list


def generate_id():
    timeuuid = time_uuid.TimeUUID.with_utcnow()  # generate uuid
    return timeuuid


def get_basepath():
    home_directory_path = os.path.expanduser('~')
    if sys.platform == 'linux2' or sys.platform == 'linux'\
            or sys.platform == 'darwin':
        iwant_directory_path = os.path.join(home_directory_path, '.iwant')
    elif sys.platform == 'win32':
        iwant_directory_path = os.path.join(os.getenv('APPDATA'), '.iwant')

    return iwant_directory_path


def get_paths():
    Config = ConfigParser.ConfigParser()
    conf_path = get_basepath()
    try:
        Config.read(os.path.join(conf_path, '.iwant.conf'))
        CONFIG_PATH = conf_path
        SHARING_FOLDER = Config.get('Paths', 'share')
        DOWNLOAD_FOLDER = Config.get('Paths', 'download')
    except:
        raise MainException(2)

    return (SHARING_FOLDER, DOWNLOAD_FOLDER, CONFIG_PATH)


def update_config(shared_folder=None, download_folder=None):
    print 'trying to update the config'
    config = ConfigParser.ConfigParser()
    conf_path = get_basepath()
    try:
        config.read(os.path.join(conf_path, '.iwant.conf'))
        if shared_folder is not None:
            print 'setting shared folder'
            config.set('Paths', 'share', shared_folder)
        if download_folder is not None:
            print 'setting download folder'
            config.set('Paths', 'download', download_folder)
        print os.path.join(conf_path, '.iwant.conf')
        with open(os.path.join(conf_path, '.iwant.conf'), 'w') as configfile:
            config.write(configfile)

    except:
        raise MainException(2)
