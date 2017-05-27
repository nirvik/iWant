from netifaces import interfaces, ifaddresses, AF_INET
import os
import sys
import ConfigParser
import time_uuid
from functools import wraps
from iwant.core.exception import MainException


def get_ips():
    ip_list = []
    for interface in interfaces():
        try:
            for link in ifaddresses(interface)[AF_INET]:
                ip_list.append((link['addr'], interface))
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
    config = ConfigParser.ConfigParser()
    conf_path = get_basepath()
    if shared_folder:
        if not os.path.isdir(shared_folder):
            raise MainException(1)
    if download_folder:
        if not os.path.isdir(download_folder):
            raise MainException(2)
    try:
        config.read(os.path.join(conf_path, '.iwant.conf'))
        if shared_folder is not None:
            # print 'setting shared folder'
            config.set('Paths', 'share', shared_folder)
        if download_folder is not None:
            # print 'setting download folder'
            config.set('Paths', 'download', download_folder)
        # print os.path.join(conf_path, '.iwant.conf')
        with open(os.path.join(conf_path, '.iwant.conf'), 'w') as configfile:
            config.write(configfile)

    except Exception as e:
        print e
        raise MainException(3)


def check_config_status():
    conf_path = get_basepath()
    SHARING_FOLDER = ''
    DOWNLOAD_FOLDER = ''
    if not os.path.exists(conf_path):
        os.mkdir(conf_path)
        create_config(conf_path)
    else:
        try:
            # if the config folder is present, but the config file is not
            # present
            SHARING_FOLDER, DOWNLOAD_FOLDER, _ = get_paths()
        except MainException:
            create_config(conf_path)
    if not os.path.exists(SHARING_FOLDER):
        new_shared_folder = raw_input('Enter absolute shared folder path:')
        update_config(shared_folder=new_shared_folder)
    if not os.path.exists(DOWNLOAD_FOLDER):
        new_donwload_folder = raw_input('Enter absolute download folder path:')
        update_config(download_folder=new_donwload_folder)


def create_config(conf_path):
    config = ConfigParser.ConfigParser()
    config.add_section('Paths')
    config.set('Paths', 'Share', '')
    config.set('Paths', 'Download', '')
    with open(os.path.join(conf_path, '.iwant.conf'), 'w') as configfile:
        config.write(configfile)

SERVER_LOG_INFO = 'server log'
CLIENT_LOG_INFO = 'client log'
ERROR_LOG = 'error log'
WARNING_LOG = 'warning log'


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def color(func):
    is_windows = True if os.name == 'nt' else False

    @wraps(func)
    def wrapper(message, type=SERVER_LOG_INFO):
        if not is_windows:
            if type == WARNING_LOG:
                print bcolors.WARNING + func(message) + bcolors.ENDC
            elif type == ERROR_LOG:
                print bcolors.FAIL + func(message) + bcolors.ENDC
            elif type == SERVER_LOG_INFO:
                print bcolors.OKGREEN + func(message) + bcolors.ENDC
            elif type == CLIENT_LOG_INFO:
                print bcolors.OKBLUE + func(message) + bcolors.ENDC
            else:
                print func(message)
        else:
            print func(message)
    return wrapper


@color
def print_log(data, type=SERVER_LOG_INFO):
    return data
