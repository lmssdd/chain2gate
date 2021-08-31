#!/usr/bin/env python3

import asyncio
import websockets
import json
from pathlib import Path
import datetime
import os

DeviceId = 'c2g-XXXXXXXXX'
RootDir = '.'
ServerIP = 'XXX.XXX.XXX.XXX'
ApiKey = 'API_KEY'

def configure():
    global DeviceId, RootDir, ServerIP, ApiKey

    file = Path('settings.json').absolute()
    if not file.exists():
        print(f"WARNING: {file} file not found, you cannot continue, please run setup")
        raise Exception("settings.json file not found, you cannot continue, please run setup")

    with open(file) as fin:
        settings = json.load(fin)
        DeviceId = settings.get('DeviceId')
        RootDir = settings.get('RootDir')
        ServerIP = settings.get('ServerIP')
        ApiKey = settings.get('ApiKey')

def trim_dict(d):
    emax = max(d['epoch'])
    emin = min([e for e in d['epoch'] if e > emax - 60*60*24])
    imin = d['epoch'].index(emin)
    d['epoch'] = d['epoch'][imin:]
    d['meter'] = d['meter'][imin:]
    d['type'] = d['type'][imin:]
    d['tariff'] = d['tariff'][imin:]
    d['energy'] = d['energy'][imin:]
    d['power'] = d['power'][imin:]

def load_json():
    try:
        with open(f"{RootDir}/{DeviceId}.json", 'r') as jsonfile:
            d = json.load(jsonfile)
    except:
        d = {
            'epoch': [],
            'meter': [],
            'type': [],
            'tariff': [],
            'energy': [],
            'power': []
        }
    
    return d

def save_json(d):
    with open(f"{RootDir}/{DeviceId}.json", 'w') as jsonfile:
        json.dump(d, jsonfile)

def upload(date=None):
    c = f'curl -X PUT "http://{ServerIP}/api/chain2gate/{DeviceId}?api_key={ApiKey}" -H  "accept: application/json" -H  "Content-Type: multipart/form-data" -F "file=@{RootDir}/{DeviceId}.json;type=text/plain"'
    if date is not None:
        c = f'curl -X PUT "http://{ServerIP}/api/chain2gate/{DeviceId}?api_key={ApiKey}&date={date}" -H  "accept: application/json" -H  "Content-Type: multipart/form-data" -F "file=@{RootDir}/{DeviceId}.json;type=text/plain"'
    os.system(c)

async def chain2client():
    while True:
        # outer loop restarted every time the connection fails
        uri = f"ws://{DeviceId}.local:81"
        d = load_json()
        last_upload = datetime.datetime.now()

        try:
            async with websockets.connect(uri) as websocket:
                async for message in websocket:
                    msg = json.loads(message)
                    print(msg)
                    if 'Chain2Data' in msg:
                        msg_meter = msg['Chain2Data']['Meter']
                        msg_type = msg['Chain2Data']['Type']
                        msg_payload = msg['Chain2Data']['Payload']
                        
                        msg_epoch = None
                        msg_tariff = None
                        msg_energy = None
                        msg_power = None

                        if msg_type == 'CF1':
                            msg_epoch = msg_payload['MeasurePosixTimestamp']
                            msg_tariff = msg_payload['TariffCode']
                            msg_energy = msg_payload['TotalActEnergy']

                        if msg_type == 'CF21':
                            msg_epoch = msg_payload['EventPosixTimestamp']
                            msg_power = msg_payload['InstantPower']

                        d['epoch'].append(msg_epoch)
                        d['meter'].append(msg_meter)
                        d['type'].append(msg_type)
                        d['tariff'].append(msg_tariff)
                        d['energy'].append(msg_energy)
                        d['power'].append(msg_power)
                        
                        now = datetime.datetime.now()
                        print(f'{now} {msg_type} ')
                        
                        trim_dict(d)
                        if msg_type == 'CF1':
                            save_json(d)
                            upload()
                            if last_upload.date() < now.date():
                                upload(now.strftime("%Y%m%d"))
                            last_upload = now

                        if msg_type == 'CF1':
                            c = f"curl -i -XPOST 'http://localhost:8086/write?db=chain2gate' --data-binary '{msg_meter} energy={msg_energy} {msg_epoch}000000000'"
                            os.system(c)
                        
                        if msg_type == 'CF21':
                            c = f"curl -i -XPOST 'http://localhost:8086/write?db=chain2gate' --data-binary '{msg_meter} power={msg_power} {msg_epoch}000000000'"
                            os.system(c)

        except:
            print('Socket error - retrying connection in 10 sec (Ctrl-C to quit)')
            await asyncio.sleep(10)
            continue

if __name__ == '__main__':
    configure()
    asyncio.get_event_loop().run_until_complete(chain2client())


