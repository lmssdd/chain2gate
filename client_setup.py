#!/usr/bin/env python3

import json

print('Chain2gate client setup')
settings = {}
settings['DeviceId'] = input('Enter Device Id (c2g-xxxxxxxxx): ')
settings['ServerIP'] = input('Enter Server IP (XXX.XXX.XXX.XXX): ')
settings['ApiKey'] = input('Enter API Key (xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx): ')
settings['RootDir'] = input('Enter Root Dir (/home/pi/chain2gate): ')

with open(f"settings.json", 'w') as jsonfile:
    json.dump(settings, jsonfile)

