from datetime import datetime
import sys
import os
import json
from getpass import getpass
from settings import configdir
# from settings import google_maps_key as g_key
from time import sleep

# Definition of the phases of C8K deployment
Statuses = ['Not Started', 'Pingable', 'SSH Works', 'Config Copied',
            'Awaiting Registration', 'Complete']


# Logger class is used to send console output to a file and console simultaneously
class Logger(object):
    def __init__(self, logfile):
        self.terminal = sys.stdout
        self.log = open(logfile, "a")

#    def open(self, logfile):

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)

    def flush(self):
        self.terminal.flush()
        self.log.flush()


# Writes edge status to a file in JSON format
def write_status(stat_dir, edges_stat):
    with open(f'{stat_dir}/status.temp', 'w') as statusFile:
        statusFile.write(json.dumps(edges_stat, indent=2))
    os.replace(f'{stat_dir}/status.temp', f'{stat_dir}/status.txt')


# Timestamp format used for printing output
def timestamp():
    t = datetime.now()
    return f'{t.day:02}/{t.month:02}/{t.year} {t.hour:02}:{t.minute:02}:{t.second:02}'


# Prompt the user to select a subdirectory from the config directory
def get_work_dir():
    directories = next(os.walk(configdir))[1]
    print('Directory List')
    for number, directory in enumerate(directories):
        print(f'{number:2}: {directory}')
    working_dir = directories[int(input('\nWhich directory do you wish to deploy: \n'))]
    return working_dir


# Prompt user for vManage credentials
def get_credentials(system):
    print(f'\nProvide your {system} credentials below:\n'
          f'  Note that password will not be displayed.')
    vmanage_user = input('Enter username: ')
    vmanage_password = getpass('Enter password: ')
    return vmanage_user, vmanage_password


def action_status(vmsess, job_id):
    # Monitors a vmanage task until it is complete and returns 'Failed' or 'Success' with details
    while 1:
        status = vmsess.get_request(f"device/action/status/{job_id}")
        status_result = status['summary']
        if status_result['status'] in ["done", "complete"]:
            if 'Failure' in status_result['count']:
                return 'Failed', f"{status['data'][0]['activity']}"
            else:
                return 'Success', f"{status_result['count']}"
        sleep(5)

# def get_timezone(lat, long):
#     # API Call to Google Maps API to get timezone from lat, long
#     url = f'https://maps.googleapis.com/maps/api/timezone/json?' \
#           f'location={lat},' \
#           f'{long}' \
#           f'&timestamp={int(datetime.now().timestamp())}&key={g_key}'
#     response = json.loads(requests.get(url).text)
#     return response
