#!/usr/bin/env python3

from logger import logger
import asyncio
import websockets
import json
from pathlib import Path
import datetime
import os

RootDir = '/home/pi/chain2gate'
DeviceId = 'c2g-XXXXXXXXX'
ServerIP = 'XXX.XXX.XXX.XXX'
ApiKey = 'API_KEY'

def configure():
    global DeviceId, RootDir, ServerIP, ApiKey

    with open(f"{RootDir}/settings.json", 'r') as jsonfile:
        settings = json.load(jsonfile)
        DeviceId = settings.get('DeviceId')
        ServerIP = settings.get('ServerIP')
        ApiKey = settings.get('ApiKey')

def trim_dict(d):
    emax = max(d['epoch'])
    emin = min([e for e in d['epoch'] if e > emax - 60*60*24])
    imin = d['epoch'].index(emin)
    d['epoch'] = d['epoch'][imin:]
    d['meter'] = d['meter'][imin:]
    d['type'] = d['type'][imin:]
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
            'energy': [],
            'power': []
        }
    
    return d

def save_json(d):
    with open(f"{RootDir}/{DeviceId}.json", 'w') as jsonfile:
        json.dump(d, jsonfile)

def upload(date=None):
    c = f'curl -X PUT "http://{ServerIP}/api/chain2gate/{DeviceId}?api_key={ApiKey}" -H  "accept: application/json" -H  "Content-Type: multipart/form-data" -F "file=@{RootDir}/{DeviceId}.json;type=text/plain" > /dev/null 2>&1'
    if date is not None:
        c = f'curl -X PUT "http://{ServerIP}/api/chain2gate/{DeviceId}?api_key={ApiKey}&date={date}" -H  "accept: application/json" -H  "Content-Type: multipart/form-data" -F "file=@{RootDir}/{DeviceId}.json;type=text/plain" > /dev/null 2>&1'
    logger.debug(f'Uploading: {c}')
    os.system(c)

async def chain2client():
    while True:
        # outer loop restarted every time the connection fails
        uri = f"ws://{DeviceId}.local:81"
        logger.debug(f'uri: {uri}')
        logger.debug('Reading data json file.')
        d = load_json()
        logger.debug('Read.')
        last_upload = datetime.datetime.now()

        try:
            async with websockets.connect(uri) as websocket:
                logger.info('Client started.')
                async for message in websocket:
                    logger.debug('Message received.')
                    msg = json.loads(message)
                    now = datetime.datetime.now()

                    if 'Chain2Data' in msg:
                        logger.info(msg)

                        msg_meter = msg['Chain2Data']['Meter']
                        msg_type = msg['Chain2Data']['Type']
                        msg_payload = msg['Chain2Data']['Payload']
                        
                        msg_epoch = None
                        msg_energy = None
                        msg_power = None

                        if msg_type == 'CF1':
                            msg_epoch = msg_payload['MeasurePosixTimestamp']
                            msg_energy = msg_payload['TotalActEnergy']

                        if msg_type == 'CF21':
                            msg_epoch = msg_payload['EventPosixTimestamp']
                            msg_power = msg_payload['InstantPower']

                        if msg_type in ['CF1', 'CF21']:
                            d['epoch'].append(msg_epoch)
                            d['meter'].append(msg_meter)
                            d['type'].append(msg_type)
                            d['energy'].append(msg_energy)
                            d['power'].append(msg_power)
                        
                        if msg_type == 'CF1':
                            trim_dict(d)
                            logger.debug(f"Dictionary trimmed to {len(d['epoch'])}")
                            save_json(d)
                            logger.info('Json file updated.')
                            upload()
                            logger.info('Current data uploaded')
                            if last_upload.date() < now.date():
                                upload(now.strftime("%Y%m%d"))
                                logger.info(f'Daily data uploaded {now.strftime("%Y%m%d")}')
                            last_upload = now

                        if msg_type == 'CF1':
                            c = f"curl -i -XPOST 'http://localhost:8086/write?db=chain2gate' --data-binary '{msg_meter} energy={msg_energy} {msg_epoch}000000000' > /dev/null 2>&1"
                            logger.debug('Sending energy data to Influxdb')
                            os.system(c)
                        
                        if msg_type == 'CF21':
                            c = f"curl -i -XPOST 'http://localhost:8086/write?db=chain2gate' --data-binary '{msg_meter} power={msg_power} {msg_epoch}000000000'  > /dev/null 2>&1"
                            logger.debug('Sending power data to Influxdb')
                            os.system(c)

        except:
            logger.error('Socket error - retrying connection in 10 sec (Ctrl-C to quit)')
            await asyncio.sleep(10)
            continue

if __name__ == '__main__':
    logger.debug("Program started.")
    configure()
    logger.debug("Configuration completed.")
    asyncio.get_event_loop().run_until_complete(chain2client())


