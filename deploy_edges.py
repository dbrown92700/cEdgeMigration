#!/usr/bin/env python3

from settings import *
from includes import *
from ios import ios
from ping3 import ping
import os
import sys
import json
from time import sleep
from vmanage_api import rest_api_lib
from datetime import datetime


# ################################ DATA COLLECTION PHASE ##########################

# Validate vManage login
try:
    vm_session2 = rest_api_lib(vmanage2, vmanage_user, vmanage_password)
except Exception as e:
    print(f'vManage:{vmanage2} attempted login failed with error {e}')
    exit()
if vm_session2.token == '':
    print(f'vManage:{vmanage2} did not return a valid login.  Check settings.py and credentials and try again.')
    exit()
else:
    print(f'vManage:{vmanage2} login success.\n')
vm_session2.logout()

# Prompt the user to select a subdirectory from the config directory
work_dir = get_work_dir()
# Mirror console stdout output to log file
t = datetime.now()
sys.stdout = Logger(f'{configdir}/{work_dir}/console.{t.year}{t.month:02}{t.day:02}.log')

print(f'\nDeploying configs in directory {configdir}/{work_dir}\n')

edgesCompleted = 0
edgeStatuses = {}

try:
    # Check for the presence of an existing status file and load status data stored from previous run

    status_file = open(f'{configdir}/{work_dir}/status.txt', 'r', encoding='utf-8-sig')
    print(f'--------- Existing Status File --- {timestamp()} -----------------------------------------------')
    noStatus = False
    edges = json.loads(status_file.read())
    for edge in edges:
        if Statuses[edge['status']] == 'Certificate Installed' or \
                Statuses[edge['status']] == 'OVA Deployment Failed':
            edgesCompleted += 1
        print(f"   {edge['hostname']}: {Statuses[edge['status']]}")
except FileNotFoundError:
    # If status file from previous run doesn't exist
    # Parses all the bootstrap files in that directory to create a edges
    # list of edge's hostname, credentials, UUID and system-ip

    print(f'--------- Initializing Statuses --- {timestamp()} -----------------------------------------------')
    edges = []
    boostrap_files = os.listdir(f'{configdir}/{work_dir}')
    for file in boostrap_files:
        if '.cfg' not in file:
            continue
        else:
            edge = {'hostname': file.replace('.cfg', ''), 'status': 0, 'login-username': c8k_user,
                    'login-password': c8k_password}
            with open(f'{configdir}/{work_dir}/{file}', 'r') as config_file:
                for line in config_file.read().split('\n'):
                    for param in ['- uuid', 'system-ip', 'site-id']:
                        if line.find(param) > -1:
                            p_value = f'{line.replace(param, "").lstrip(" :-")}'
                            edge[param.lstrip('- ')] = p_value
            edges.append(edge)
            print(edge)

if input('\nType "yes" to continue: \n') != 'yes':
    exit()

write_status(f'{configdir}/{work_dir}', edges)

# ################################ DEPLOYMENT PHASE ##########################

# This loop iterates through all the steps until every C8Kv in the parameters file is fully deployed

runNumber = 0
while edgesCompleted < len(edges):

    t = datetime.now()
    print(f'------------------------- Run {runNumber} --- {timestamp()} ------------------------------------------')
    runNumber += 1

    # Scan 'Not Started' edges and check for ping-ability

    print('Scanning edges with status - Not Started')
    for edge in edges:
        if Statuses[edge['status']] == 'Not Started':
            # ping edge twice to allow for ARP resolution
            response = None
            for ping_run in range(5):
                if response is None:
                    response = ping(edge['system-ip'], timeout=1)
            if (response is None) or (not response):
                print(f'  {edge["hostname"]}: C8000v is not Pingable')
            else:
                edge['status'] += 1
                print(f'  {edge["hostname"]}: C8000v is Pingable - Moving to {Statuses[edge["status"]]}')
                write_status(f'{configdir}/{work_dir}', edges)

# SSH STATUS: Scan Pingable edges and see if SSH works

    print('Scanning edges with status - Pingable')
    for edge in edges:
        if Statuses[edge['status']] == 'Pingable':
            edge_ssh = ios(edge['system-ip'], edge['login-username'], edge['login-password'])
            print(f'  {edge["hostname"]}: {edge_ssh.status}')
            if edge_ssh.status == 'Connected':
                edge['status'] += 1
                write_status(f'{configdir}/{work_dir}', edges)
                edge_ssh.disconnect()
                print(f'    SSH Works - Moving to {Statuses[edge["status"]]}')

    # SCP CONFIG: Scan SSH Works edges, enable SCP, copy sdwan config

    print('Scanning edges with status - SSH Works')
    for edge in edges:
        if Statuses[edge['status']] == 'SSH Works':
            edge_ssh = ios(edge['system-ip'], edge['login-username'], edge['login-password'])
            edge_ssh.send_command(command='enable', expect='#')
            edge_ssh.send_command(command='config terminal', expect='config')
            edge_ssh.send_command(command='ip scp server enable', expect='config')
            edge_ssh.send_command(command='aaa authorization exec default local', expect='config')
            edge_ssh.send_command(command='exit', expect='#')
            edge_ssh.send_file(f'{configdir}/{work_dir}/{edge["hostname"]}.cfg', 'ciscosdwan_cloud_init.cfg')
            response = edge_ssh.send_command('dir').split('\n')
            result = 'SDWAN config SCP Fail. Will re-attempt'
            for line in response:
                if line.find('ciscosdwan_cloud_init.cfg') > -1:
                    edge['status'] += 1
                    result = f'SDWAN config SCP Success. Moving to {Statuses[edge["status"]]}.'
                    write_status(f'{configdir}/{work_dir}', edges)
            print(f'  {edge["hostname"]}: {result}')
            edge_ssh.disconnect()

    # CONTROLLER-MODE ENABLE: Scan Config Copied edges and enable Controller Mode

    print('Scanning edges with status - Config Copied')
    for edge in edges:
        if Statuses[edge['status']] == 'Config Copied':
            edge_ssh = ios(edge['system-ip'], edge['login-username'], edge['login-password'])
            response = edge_ssh.send_command('controller-mode enable', 'confirm').split('\n')
            try:
                response = edge_ssh.send_command('\n', '#').split('\n')
            except:
                response = 'Not Reachable'
            edge_ssh.disconnect()
            edge['controllerModeTime'] = int(datetime.now().strftime('%s'))
            edge['status'] += 1
            write_status(f'{configdir}/{work_dir}', edges)
            print(f'  {edge["hostname"]}: controller-mode enable Command Sent. Moving to {Statuses[edge["status"]]}')

    # CHECK CONTROL CONNECTION: Scan Awaiting Registration edges and see if they're registered to vManage
    # Uses vManage API to check registration status of device by system-ip in parameters.csv

    print('Scanning edges with status - Awaiting Registration')
    for edge in edges:
        if Statuses[edge['status']] == 'Awaiting Registration':
            vm_session2 = rest_api_lib(vmanage2, vmanage_user, vmanage_password)
            try:
                sdwanStatus = vm_session2.get_request(f'device?deviceId={edge["system-ip"]}')['data'][0]['reachability']
            except:
                sdwanStatus = 'sys-ip Not Found in vManage'
            vm_session2.logout()
            if sdwanStatus == 'reachable':
                edge['status'] += 1
                print(f'  {edge["hostname"]}:  Registered to vManage. Moving to {Statuses[edge["status"]]}')
                edge['registeredTime'] = int(datetime.now().strftime('%s'))
                write_status(f'{configdir}/{work_dir}', edges)
                edgesCompleted += 1
            else:
                print(f'  {edge["hostname"]}:  {sdwanStatus}')
                lapsed = (datetime.now() - datetime.fromtimestamp(edge['controllerModeTime'])).seconds
                print(f'     {lapsed} seconds since controller-mode enabled.')
                if lapsed > 360:
                    print(f'!!!!!!!!!!!\n\n{edge["hostname"]} reboot has exceeded 6 minutes.\n'
                          f'   To reset it, access the edge ESXi console and...\n'
                          f'      > Login with credentials admin / admin\n'
                          f'      > Set the new password to admin when prompted\n'
                          f'      > Type "request platform software sdwan software reset" command\n\n'
                          f'   The script will reset the reboot time for this edge.\n\n')
                    answer = input(f'    Hit return to continue:\n')
                    if answer == 'yes':
                        edge['controllerModeTime'] = int(datetime.now().strftime('%s'))
                        print(f'!!!!!!!!!!!  {edge["hostname"]} reboot time set to Now.\n\n')

    # DEPLOYMENT STATUS REPORT: Print Current Status of edges

    print(f'\n------------ Current status of edges --- {timestamp()} --------------------------------')
    stats = []
    for edge in edges:
        print(f'  {edge["hostname"]}: {Statuses[edge["status"]]}')
        stats.append(edge["status"])

    for x in range(len(Statuses)):
        print(f'{Statuses[x]}:{stats.count(x):<3}', end=' ')

    # Placeholder for code below to push status information to an external reporting server
    # Code execution is currently blocked by "if False:"
    if False:
        post_headers = {'Content-Type': 'application/json'}
        post_response = requests.request('POST', f'{reporting_server}', headers=post_headers, data=json.dumps(edges))

    if edgesCompleted < len(edges):
        print(f'-----------------------{edgesCompleted} sites are fully complete.--------------------------------\n\n')
        sys.stdout.flush()
        print(f'    seconds before next run.', end='\r')
        for time in range(sleep_time, 0, -1):
            print(f'{time:3}', end='\r')
            sleep(1)
    else:
        print(f'{timestamp()}: All Sites completed.')
    print('\n\n')

    # COMPLETION: Finish when all edges are 'Complete' status, or continue iteration.
