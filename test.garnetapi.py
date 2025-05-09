import time
from dummy.test_logging import logging 
from garnetapi.const import *
import garnetapi.garnetapi as garnetapi

_LOGGER = logging.getLogger(__name__)

def main():
    
    _LOGGER.info('-----------------------------------------------------------------------------------')
    _LOGGER.info('Garnet test started')

    user = GARNET_USER
    password = GARNET_PASS
    client = GARNET_SIACLIENT
    

    try:
        api = garnetapi.GarnetAPI(email = user, password = password, client = client)

        # Lets wait for a long time
        while(True):
            time.sleep(60)

    except Exception as err:
        _LOGGER.exception(err)        

if __name__ == '__main__':
    main()
