import asyncio
import logging
import json
import binascii
import voluptuous as vol
import sseclient
import requests
import time
from collections import defaultdict
from requests_toolbelt.utils import dump
from homeassistant.core import callback
import voluptuous as vol
from datetime import timedelta
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity, async_generate_entity_id
from homeassistant.helpers.event import async_track_state_change

from threading import Thread
from homeassistant.helpers import discovery
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.helpers.restore_state import RestoreEntity
_LOGGER = logging.getLogger(__name__)
from homeassistant.const import (STATE_ON, STATE_OFF)

from homeassistant.const import (
    CONF_NAME, CONF_PORT, CONF_PASSWORD)
import socketserver 
from datetime import datetime
import time
import logging
import threading
import sys
import re

from Crypto.Cipher import AES
from binascii import unhexlify,hexlify
from Crypto import Random
import random, string, base64
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util.dt import utcnow

DOMAIN = 'garnet'
CONF_HUBS = 'hubs'
CONF_ACCOUNT = 'account'

HUB_CONFIG = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_ACCOUNT): cv.string,
    vol.Optional(CONF_PASSWORD):cv.string,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_PORT): cv.string,
        vol.Required(CONF_HUBS, default={}):
            vol.All(cv.ensure_list, [HUB_CONFIG]),
    }),
}, extra=vol.ALLOW_EXTRA)


TIME_TILL_UNAVAILABLE = timedelta(seconds=119)

ID_R='\r'.encode()

hass_platform = None

def setup(hass, config):
    
    global hass_platform
    hass_platform = hass
    hass_platform.data[DOMAIN] = {}
    
    port = int(config[DOMAIN][CONF_PORT])
    _LOGGER.debug("Using port " + str(port))

    for hub_config in config[DOMAIN][CONF_HUBS]:

        if CONF_PASSWORD in hub_config:
            hass.data[DOMAIN][hub_config[CONF_ACCOUNT]] = EncryptedHub(hass, hub_config)
        else:
            hass.data[DOMAIN][hub_config[CONF_ACCOUNT]] = Hub(hass, hub_config)
          
    for component in ['binary_sensor']:
       discovery.load_platform(hass, component, DOMAIN, {}, config)

    server = socketserver.UDPServer(("", port), AlarmTCPHandler)
    t = threading.Thread(target=server.serve_forever)
    t.start()
    return True

class Hub:
    reactions = {            
            "BA" : [{"state":"ALARM","value":True}],
            "TA" : [{"state":"ALARM" ,"value":True}],
            "CL" : [{"state":"STATUS" ,"value":False},{"state":"STATUS_TEMP" ,"value":False}],
            "NL" : [{"state":"STATUS" ,"value":True},{"state":"STATUS_TEMP" ,"value":False}],
            "WA":  [{"state":"LEAK","value":True}],
            "WH":  [{"state":"LEAK" ,"value":False}],
            "GA":  [{"state":"GAS","value":True}],
            "GH":  [{"state":"GAS" ,"value":False}],
            "BR" : [{"state":"ALARM","value":False}],
            "OP" : [{"state":"STATUS","value":True},{"state":"STATUS_TEMP","value":True}],
            "RP" : []
        }

    def __init__(self, hass, hub_config):
        self._name = hub_config[CONF_NAME]
        self._accountId = hub_config[CONF_ACCOUNT]
        self._hass = hass
        self._states = {}
        self._states["COM"] = SIABinarySensor("garnet_panel_communications_status_" + self._name,"communication" , hass)
    
    def qualifier(self, argument):
        if argument == 1 :
            return "ACT"
        else :
            if argument == 3 :
                return "DEC"
            else :
                if argument == 6 :
                    return "RPT"
                else :
                    return "Invalid qualifier"

    def manage_message(self, token, data,timestamp):

        if(token == "NULL"):
            _LOGGER.info("Timestamp:" + timestamp + ", Keep alive, Account: " + self._accountId)
            self._states["COM"].new_state(True)
 
        else: 
            if token == "ADM-CID":

                message_blocks = data.split('|')
                message_blocks = message_blocks[1].split(']')
                contact_id = message_blocks[0].split(' ')

                # 1 = New Event or Opening,
                # 3 = New Restore or Closing,
                # 6 = Previously reported condition still present (Status report)
                event_qualifier = int(contact_id[0][0], 10)

                # 3 decimal(!) digits XYZ (e.g. 602)
                event_code = int(contact_id[0][1:], 10)

                # 2 decimal(!) digits GG, 00 if no info (e.g. 01)
                group_or_partition_number = contact_id[1]

                # 3 decimal(!) digits CCC, 000 if no info (e.g. 001)
                zone_number_or_user_number = contact_id[2]

                _LOGGER.debug("Event Qualifier is " + str(event_qualifier) + " (" + format(self.qualifier(event_qualifier)) + ")")
                _LOGGER.debug("Event Code is " + str(event_code))
                _LOGGER.debug("Partition number is " + group_or_partition_number)
                _LOGGER.debug("Zone/User number is " + zone_number_or_user_number)

                _LOGGER.info("Timestamp:" + timestamp + ", " + format(self.qualifier(event_qualifier)) + ", Code:" + str(event_code) + ", Particion/Grupo:" + group_or_partition_number + ", Zona/Usuario:" + zone_number_or_user_number + ", Account: " + self._accountId)
            else:
                _LOGGER.info("Timestamp:" + timestamp + ", Token:" + token)
                
        for device in self._states:
           self._states[device].assume_available()

    def manage_message_older(self, token):
        pos = msg.find('/')        
        assert pos>=0, "Can't find '/', message is possibly encrypted"
        tipo = msg[pos+1:pos+3]

        if tipo in self.reactions:
            reactions = self.reactions[tipo]
            for reaction in reactions:
                state = reaction["state"]
                value = reaction["value"]
             
                self._states[state].new_state(value)
        else:
            _LOGGER.error("unknown event: " + tipo )
        
        for device in self._states:
           self._states[device].assume_available()

    @staticmethod
    def findAndAssert(str,char) :
        x = str.find(char)               
        assert x >= 0, "Malformed message" 
        return x


    def process_line(self, line):
        
        strline = line.decode(errors='replace')                 # Se convierte a string para manejo eficiente

        # Se obtiene el token
        start = self.findAndAssert(strline,'"')               
        end = self.findAndAssert(strline[start + 1:],'"')               
        token = strline[start : end + 1].replace('"','')
        _LOGGER.debug("Token: " + token)

        strline = strline[end + 1 : ]           

        # Se obtiene el numero de secuencia
        start = 1                               
        end = self.findAndAssert(strline,'R')               
        seq = strline[start: end]
        _LOGGER.debug("Sequence #: " + seq)

        strline = strline[end: ]                

        # Se obtiene el numero de receiver
        start = self.findAndAssert(strline,'R')
        end = self.findAndAssert(strline,'L')
        receiver = strline[start + 1: end]
        _LOGGER.debug("Receiver ID: " + receiver)

        strline = strline[end: ]                

        # Se obtiene el numero de prefijo de cuenta
        start = self.findAndAssert(strline,'L')
        end = self.findAndAssert(strline,'#')
        account_prefix = strline[start + 1: end]
        _LOGGER.debug("Account prefix: " + account_prefix)

        strline = strline[end: ]                

        # Se obtiene el bloque de datos
        start = self.findAndAssert(strline,'[')
        end = self.findAndAssert(strline,'_')
        data = strline[start: end]
        _LOGGER.debug("Data block: " + data)

        strline = strline[end: ]                

        # Se obtiene el timestamp
        start = self.findAndAssert(strline,'_')
        ts = strline[start + 1: ]
        _LOGGER.debug("Timestamp: " + ts)


        self.manage_message(token, data, ts)
        return '"ACK"'  + (seq) + 'R' + receiver + 'L' + account_prefix + '#' + (self._accountId) + '[]' 
    
    
    
# ======================================================================================================
# Class EncryptedHub --> TODO
# ======================================================================================================
class EncryptedHub(Hub):
    def __init__(self, hass, hub_config):
        self._key = hub_config[CONF_PASSWORD].encode("utf8")
        iv = Random.new().read(AES.block_size)
        _cipher = AES.new(self._key, AES.MODE_CBC, iv)
        self.iv2 = None
        self._ending = hexlify(_cipher.encrypt( "00000000000000|]".encode("utf8") )).decode(encoding='UTF-8').upper()
        Hub.__init__(self, hass, hub_config)

    def manage_string(self, msg):
        iv = unhexlify("00000000000000000000000000000000") #where i need to find proper IV ? Only this works good.
        _cipher = AES.new(self._key, AES.MODE_CBC, iv)
        data = _cipher.decrypt(unhexlify(msg[1:]))
        _LOGGER.debug("EncryptedHub.manage_string data: " + data.decode(encoding='UTF-8',errors='replace'))

        data = data[data.index(b'|'):]
        resmsg = data.decode(encoding='UTF-8',errors='replace')
               
        Hub.manage_string(self, resmsg)

    def process_line(self, line):
        _LOGGER.debug("Processing message" + line.decode())
        #_LOGGER.debug("EncryptedHub.process_line" + line.decode())
        #pos = line.find(ID_STRING_ENCODED)
        #assert pos>=0, "Can't find ID_STRING_ENCODED, is SIA encryption enabled?"
        #seq = line[pos+len(ID_STRING_ENCODED) : pos+len(ID_STRING_ENCODED)+4]
        data = line[line.index(b'[') :]
        _LOGGER.debug("EncryptedHub.process_line found data: " + data.decode())
        self.manage_string(data.decode())
        return '"*ACK"'  + (seq.decode()) + 'L0#' + (self._accountId) + '[' + self._ending
  
        
# ======================================================================================================
# Class SIABinarySensor
# ======================================================================================================
class SIABinarySensor( RestoreEntity):
    def __init__(self,  name, device_class, hass):
        self._device_class = device_class
        self._should_poll = False
        self._name = name
        self.hass = hass
        self._is_available = True
        self._remove_unavailability_tracker = None

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        state = await self.async_get_last_state()        
        if state is not None and state.state is not None:
            self._state = state.state == STATE_ON
        else:
            self._state = None
        self._async_track_unavailable()

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return STATE_ON if self.is_on else STATE_OFF

    @property
    def unique_id(self) -> str:
        return self._name

    @property
    def available(self):
        return self._is_available

    @property
    def device_state_attributes(self):
        attrs = {}
        return attrs

    @property
    def device_class(self):
        return self._device_class

    @property
    def is_on(self):
        return self._state

    def new_state(self, state):   
        self._state = state
        self.async_schedule_update_ha_state()

    def assume_available(self):
        self._async_track_unavailable()

    @callback
    def _async_track_unavailable(self):
        if self._remove_unavailability_tracker:
            self._remove_unavailability_tracker()
        self._remove_unavailability_tracker = async_track_point_in_utc_time(
            self.hass, self._async_set_unavailable,
            utcnow() + TIME_TILL_UNAVAILABLE)
        if not self._is_available:
            self._is_available = True
            return True
        return False

    @callback
    def _async_set_unavailable(self, now):
        self._remove_unavailability_tracker = None
        self._is_available = False
        self.async_schedule_update_ha_state()



# ======================================================================================================
# Class AlarmTCPHandler
# ======================================================================================================
class AlarmTCPHandler(socketserver.BaseRequestHandler):
    
    # --------------------------------------------------------------------
    # handle - Recibe un mensaje UDP y hace el procesamiento inicial
    # --------------------------------------------------------------------
    def handle(self):
        line = b''
        try:
            line  = self.request[0].strip()     # Mensaje recibido
            socket = self.request[1]            # Socket
            
            hasNewline = line.find(b'\n')
            if hasNewline >= 0: 
                line = line[hasNewline + 1:] 
            
            _LOGGER.debug("Received raw string (ASCII): " + line.decode(errors='replace'))     
            _LOGGER.debug("                    (bytes): " + format(binascii.hexlify(line)))

            # Se obtiene el account ID
            accountId = line[line[3:].index(b'#') + 4: line[3:].index(b'[') + 3].decode(errors='replace')
            _LOGGER.debug("Message from AccountId: " + accountId )     

            # Se obtiene el mensaje
            pos = line.find(b'"')
            assert pos>=0, "Can't find message beginning"
            inputMessage = line[pos:]
            _LOGGER.debug("Stripped message: " + inputMessage.decode(errors='replace') )
            
            msgcrc = int.from_bytes(line[0:2], byteorder='big', signed=False) # Se obtiene el CRC del mensaje
            codecrc = str.encode(AlarmTCPHandler.CRCCalc(inputMessage))    # Se calcula el CRC a partir del mensaje
      
            try:
                if msgcrc != int(codecrc.decode(errors='replace'),16):
                    raise Exception('CRC mismatch! Expected ' +  str(msgcrc) + " but calculated " + codecrc.decode(errors='replace'))            
                if(accountId not in hass_platform.data[DOMAIN]):
                    raise Exception('Not supported account ' + accountId)
                
                # Si esta todo OK entonces procesa el mensaje
                response = hass_platform.data[DOMAIN][accountId].process_line(inputMessage)
                
            except Exception as e:
                _LOGGER.error(str(e))
                timestamp = datetime.fromtimestamp(time.time()).strftime('_%H:%M:%S,%m-%d-%Y')
                response = '"NAK"0000L0R0A0[]' + timestamp

            header = str(len(response)).zfill(4)
 
            byte_response = str.encode("\n") + int(AlarmTCPHandler.CRCCalc2(response),16).to_bytes(2, 'big') + str.encode(header) + str.encode(response) + str.encode("\r")

            _LOGGER.debug("Response string (ASCII): " + byte_response.decode(errors='replace').replace('\r','\\r').replace('\n','\\n'))     
            _LOGGER.debug("                (bytes): " + format(binascii.hexlify(byte_response)))

            self.request[1].sendto(byte_response, self.client_address)
        except Exception as e: 
            _LOGGER.error(str(e)+" on AlarmTCPHandler.handle()")
            return

    @staticmethod
    def CRCCalc(msg):
        CRC=0
        for letter in msg:
            temp=(letter)
            for j in range(0,8):  # @UnusedVariable
                temp ^= CRC & 1
                CRC >>= 1
                if (temp & 1) != 0:
                    CRC ^= 0xA001
                temp >>= 1
                
        return ('%x' % CRC).upper().zfill(4)
    
    @staticmethod
    def CRCCalc2(msg):
        CRC=0
        for letter in msg:
            temp=ord(letter)
            for j in range(0,8):  # @UnusedVariable
                temp ^= CRC & 1
                CRC >>= 1
                if (temp & 1) != 0:
                    CRC ^= 0xA001
                temp >>= 1
                
        return ('%x' % CRC).upper().zfill(4)
