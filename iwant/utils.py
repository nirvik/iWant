from netifaces import interfaces, ifaddresses, AF_INET
import ConfigParser
import time_uuid
import os, sys
from core.exception import MainException

def get_ips():
    ip_list = []
    for interface in interfaces():
        try:
            for link in ifaddresses(interface)[AF_INET]:
                ip_list.append(link['addr'])
        except:
            pass
    return ip_list

#def get_paths():
#    Config = ConfigParser.ConfigParser()
#    conf_path = get_basepath()
#    try:
#        Config.read(os.path.join(conf_path,'.iwant.conf'))
#        CONFIG_PATH = conf_path
#        SHARING_FOLDER = Config.get('Paths', 'share')
#        DOWNLOAD_FOLDER = Config.get('Paths', 'download')
#    except:
#        raise MainException(2)
#
#    return (SHARING_FOLDER, DOWNLOAD_FOLDER, CONFIG_PATH)
#
#def get_basepath():
#    iwant_directory_path = os.path.expanduser('~')
#    if sys.platform =='linux2' or sys.platform == 'linux' or sys.platform == 'darwin':
#        iwant_directory_path = os.path.join(iwant_directory_path, '/.iwant')
#    elif sys.platform == 'win32':
#        iwant_directory_path = os.path.join(iwant_directory_path, '\\AppData\\Roaming\\.iwant')
#
#    return iwant_directory_path

def generate_id():
    timeuuid = time_uuid.TimeUUID.with_utcnow()  # generate uuid
    return timeuuid
