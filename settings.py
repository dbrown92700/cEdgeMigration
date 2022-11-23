# Reads settings from .env or prompts user for settings that don't exist

import dotenv
from cryptography.fernet import Fernet
import os
from getpass import getpass

# To define a unique setting key for your environment execute Fernet.generate_key() using python
setting_key = b'FHqV8uwORJofYN2U40ze8oJcgouQv9zLYEirItfUJPI='
basedir = os.path.abspath(__file__).removesuffix('/settings.py')
configdir = basedir + '/WorkingDir'


def get_setting(variable, prompt, secret):
    # Get environment variable or prompt user
    dotenv.load_dotenv(f'{basedir}/.env')
    try:
        response = os.environ[variable]
        if secret:
            print(f'{variable} = *******')
            response = Fernet(setting_key).decrypt((response.encode('ascii'))).decode('ascii')
        else:
            print(f'{variable} = {response}')

    except KeyError:
        if secret:
            response = getpass(prompt)
            dotenv.set_key(f'{basedir}/.env', variable,
                           Fernet(setting_key).encrypt(bytes(response, 'ascii')).decode('ascii'))
        else:
            response = input(prompt)
            dotenv.set_key(f'{basedir}/.env', variable, response)
    return response


print('Settings:')

vmanage1 = get_setting('VMANAGE1_ADDRESS', 'Input Source vManage Address: ', False)
vmanage2 = get_setting('VMANAGE2_ADDRESS', 'Input Destination vManage Address: ', False)
vmanage_user = get_setting('VMANAGE_USER', 'Input vManage Username: ', False)
vmanage_password = get_setting('VMANAGE_PASSWORD', 'Input vManage Password: ', True)
c8k_user = get_setting('EDGE_USER', 'Input router Username: ', False)
c8k_password = get_setting('EDGE_PASSWORD', 'Input Router Password: ', True)
sleep_time = get_setting('SLEEP_TIME', 'Input wait time in seconds between deployment runs: ', False)
vedge_prefix = get_setting('VEDGE_PREFIX', 'Input vEdge Hostname prefix to remove: ', False)
cedge_prefix = get_setting('CEDGE_PREFIX', 'Input cEdge Hostname prefix to add: ', False)
vedge_suffix = get_setting('VEDGE_SUFFIX', 'Input vEdge Hostname suffix to remove: ', False)
cedge_suffix = get_setting('CEDGE_SUFFIX', 'Input cEdge Hostname suffix to add: ', False)
# google_maps_key = get_setting('SLEEP_TIME', 'Input Google Maps Timezone API Key: ', True)

if input('Type "reset" to clear the settings, or anything else to proceed: ') == 'reset':
    os.remove(f'{basedir}/.env')
    print('Settings cleared.  Restart script to proceed.')
    exit()
