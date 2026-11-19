import logging
import time
import coloredlogs
coloredlogs.install(level=logging.DEBUG)

from torpool import TorPool

pool = TorPool(controller_port=9051, exit_count=200)


while True:
    time.sleep(10)
