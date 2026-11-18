import logging
import time
import coloredlogs
coloredlogs.install(level=logging.DEBUG)

from torpool import TorPool

pool = TorPool(controller_port=19051, socks_port=19050, exit_count=5)

pool.maintain_circuits()


while True:
    time.sleep(1)
