#!/usr/bin/env python3
import csv
from settings import *
from includes import *
import json
from vmanage_api import rest_api_lib
import os


if __name__ == "__main__":

    # Prompt for edges list file.  Print list.  Ask for validation to proceed.

    files = os.listdir(configdir)
    print('CSV Files in Config Directory:')
    csv_files = []
    for file in files:
        if '.csv' in file:
            print(f' - {file}')
            csv_files.append(file)
    while True:
        edgesCsvFile = input('\nWhich file do you want to deploy?\n')
        if edgesCsvFile in csv_files:
            break
        print('CSV file not found.\n')
    with open(f'{configdir}/{edgesCsvFile}', 'r', encoding='utf-8-sig') as csv_file:
        # reading the csv file using DictReader
        edges = list(csv.DictReader(csv_file))
    print('Devices listed in this file:')
    for edge in edges:
        edge['host-name2'] = f'sdw{edge["overlay2"]}'+edge['host-name1'].removeprefix('sdw')
        print(f' - {edge["host-name1"]} -> {edge["host-name2"]} on Overlay {edge["overlay2"]}')
    if input('\nType "yes" to migrate these devices: \n') != 'yes':
        exit()

    # Prompt for vManage Credentials and login to each vManage

    # vmanageUser, vmanagePassword = get_credentials('vManage 1.0')
    try:
        vm_session1 = rest_api_lib(vmanage1, vmanage_user, vmanage_password)
    except Exception as e:
        print(f'vManage1 attempted login failed with error {e}')
        exit()
    if vm_session1.token == '':
        print(f'vManage1 did not return a valid login.  Check settings.py and credentials and try again.')
        exit()
    else:
        print(f'vManage1 login success.\n')
    # vmanageUser, vmanagePassword = get_credentials('vManage 2.0')
    try:
        vm_session2 = rest_api_lib(vmanage2, vmanage_user, vmanage_password)
    except Exception as e:
        print(f'vManage2 host {vmanage2} login failed with error {e}')
        exit()
    if vm_session2.token == '':
        print(f'vManage2 host {vmanage2} did not return a valid login.  '
              f'Check settings.py and credentials and try again.')
        exit()
    else:
        print(f'vManage2 host {vmanage2} login success.\n')

    # Get System IPs for each hostname

    device_list = vm_session1.get_request('device')['data']
    for device in device_list:
        for edge in edges:
            if edge['host-name1'] == device['host-name']:
                edge['system-ip'] = device['system-ip']
                edge['uuid1'] = device['uuid']
                print(f'Added sys-ip & uuid to: {edge}')

    # Get Attached TemplateId1 and Name1 for each hostname

    vedge_list1 = vm_session1.get_request('system/device/vedges')['data']
    for device in vedge_list1:
        for edge in edges:
            print(f'Lookup template for {edge}')
            try:
                if edge['uuid1'] == device['uuid']:
                    edge['templateName1'] = device['template']
                    edge['templateId1'] = device['templateId']
            except KeyError:
                print(f'\nHostname {edge["host-name"]} not found\n')
                exit()

    # Get TemplateId2 for each host-name

    template_list1 = vm_session2.get_request('template/device')['data']
    for template in template_list1:
        for edge in edges:
            if edge['templateName2'] == template['templateName']:
                edge['templateId2'] = template['templateId']

    # Get UUID for each host-name

    c8k_edges = vm_session2.get_request('system/device/vedges?model=vedge-C8000V&state=tokengenerated')['data']
    if len(c8k_edges) < len(edges):
        print(f'TOO FEW C8K AVAILABLE ... There are:\n{len(c8k_edges)} C8000v in "Token Generated" state and\n'
              f'{len(edges)} devices in the CSV file list.')
        exit()
    for edge in edges:
        edge['uuid2'] = c8k_edges.pop()['uuid']

    # Migrate Edges

    for edge in edges:
        print(f'\n{edge["host-name"]} Configuration:')

        # Download template1 variables

        payload = {
            "templateId": edge['templateId1'],
            "deviceIds":
                [
                    edge['uuid1']
                ],
            "isEdited": False,
            "isMasterEdited": False
        }
        edge['template1'] = vm_session1.post_request('template/device/config/input',
                                                     payload=payload)['data'][0]

        # Map variables to template2

        with open(f'{configdir}/../MapFiles/{edge["templateName2"]}.csv', 'r', encoding='utf-8-sig') as map_file:
            conversions = list(csv.DictReader(map_file))
        mapper = None
        for conversion in conversions:
            if conversion['templateName1'] == edge["templateName1"]:
                mapper = conversion
                break
        if mapper is None:
            print(f'   WARNING: Target template map, {edge["templateName2"]}, not found'
                  f'for Source template, {edge["templateName1"]}')
            continue
        edge['template2'] = {"csv-status": "complete",
                             "csv-deviceId": edge["uuid2"],
                             "csv-deviceIP": "-",
                             "csv-host-name": "-"}
        for value in mapper:
            if value == 'templateName1':
                continue
            elif mapper[value][0:2] == 'EQ':
                edge['template2'][value] = mapper[value].removeprefix('EQ ')
            elif mapper[value][0:3] == 'VAR':
                edge['template2'][value] = edge[mapper[value].removeprefix('VAR ')]
            else:
                edge['template2'][value] = edge['template1'][mapper[value]]
            if edge['template2'][value] in ['TRUE', 'True', 'true']:
                edge['template2'][value] = True
            if edge['template2'][value] in ['FALSE', 'false', 'False']:
                edge['template2'][value] = False
            if value in ['//system/gps-location/latitude', '//system/gps-location/longitude']:
                edge['template2'][value] = edge['template2'][value].lstrip("'")
        print('   Template mapping complete')

        # Save all edge data to JSON file for reference.

        print(f'   Saving complete edge data to:\n     {configdir}/{edgesCsvFile.removesuffix(".csv")}.json')
        with open(f'{configdir}/{edgesCsvFile.removesuffix(".csv")}.json', 'w') as json_file:
            json_file.write(json.dumps(edges, indent=2))

        #   Attach Template

        payload = {
            "deviceTemplateList": [
                {
                    "templateId": edge['templateId2'],
                    "device": [
                        edge['template2']
                    ],
                    "isEdited": False,
                    "isMasterEdited": False
                }
            ]
        }
        print(f'   Attaching template to uuid {edge["uuid2"]}')
        attach_job = vm_session2.post_request('template/device/config/attachment', payload=payload)
        print(f'     Job ID: {attach_job["id"]}')
        attach_status, attach_message = action_status(vm_session2, attach_job['id'])
        print(f'     Result: {attach_status}: {attach_message}')
        edge['attach_status'] = attach_status
        edge['attach_message'] = attach_message

        #   Download bootstrap

        if attach_status == 'Success':
            print("   Generating bootstrap configuration file... ")
            bootstrap_configuration = \
                vm_session2.get_request(f'system/device/bootstrap/device/{edge["uuid2"]}'
                                        f'?configtype=cloudinit&inclDefRootCert=false')['bootstrapConfig']
            print(f'     Saving the bootstrap configuration as {edge["host-name"]}.cfg...')
            with open(f'{configdir}/{edge["host-name"].strip()}.cfg', 'w', newline='') as bootstrap_configuration_file:
                bootstrap_configuration_file.write(bootstrap_configuration)
            edge['boostrap-file'] = f'{edge["host-name"]}.cfg'

        # Get edge timezone

        # edge['timezone'] = get_timezone(edge['template2']['//system/gps-location/latitude'],
        #                                 edge['template2']['//system/gps-location/longitude'])

        # Update JSON file for reference.

        with open(f'{configdir}/{edgesCsvFile.removesuffix(".csv")}.json', 'w') as json_file:
            json_file.write(json.dumps(edges, indent=2))

    vm_session1.logout()
    vm_session2.logout()

    # Write Timezone File

    # filename = f'{edgesCsvFile.removesuffix(".csv")}-TZ.csv'
    # with open(f'{configdir}/{filename}', 'w') as file:
    #     file.write('Edge,TimezoneName,UTC-Offset\n')
    #     for edge in edges:
    #         seconds = edge['timezone']['rawOffset']
    #         file.write(f'{edge["host-name"]},{edge["timezone"]["timeZoneName"]},{int(seconds/3600)}:'
    #                    f'{int((abs(seconds)%3600)/60):02}')
    # print(f'\nTimezone file written to {filename}\n\n')
