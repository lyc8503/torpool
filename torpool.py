import stem.control
import logging
import random


class TorPool:
    def __init__(self, tor_addr='127.0.0.1', controller_port=9051, socks_port=9050, exit_count=5):
        self.tor_addr = tor_addr
        self.socks_port = socks_port
        self.exit_count = exit_count

        self.controller = stem.control.Controller.from_port(address=tor_addr, port=controller_port)
        self.controller.authenticate()
        self.circuits = []
        logging.info(f"connected to Tor controller at {tor_addr}:{controller_port}")
        self.controller.add_event_listener(self.event_listener, stem.control.EventType.STREAM, stem.control.EventType.CIRC)
        # TODO: self circuit maintain

    def get_eligible_exit_nodes(self):
        exits = []
        for node in self.controller.get_network_statuses():
            # must have Exit/Running/Fast flags
            if any(map(lambda x: x not in node.flags, ['Exit', 'Running', 'Fast'])):
                continue
            # TODO: more filters, e.g. country, allowed ports, etc.
            exits.append({
                'fingerprint': node.fingerprint,
                'address': node.address,
                'port': node.or_port,
                'nickname': node.nickname,
            })
        logging.debug(f"found {len(exits)} eligible exit nodes")
        if len(exits) < self.exit_count:
            logging.warning(f"not enough eligible exit nodes found: {len(exits)} < {self.exit_count}")
        return exits

    def new_circuit(self, exit_node):
        # create a new 1-hop circuit to the given exit node
        # properly configured tor instance will authenticate us as relay,
        # so the peer exit will allow us using this circuit for outgoing connections
        circ_id = self.controller.new_circuit([exit_node['fingerprint']], purpose='controller', await_build=True, timeout=10)
        logging.debug(f"new circuit {circ_id} to exit node {exit_node['nickname']} ({exit_node['fingerprint']})")
        return circ_id

    def maintain_circuits(self):
        # create and maintain self.exit_count 1-hop relay circuits to random selected exits
        # will never return
        nodes = self.get_eligible_exit_nodes()
        for _ in range(0, self.exit_count):
            exit_node = random.choice(nodes)
            circ_id = self.new_circuit(exit_node)
            self.circuits.append({
                'circ_id': circ_id,
                'exit_node': exit_node
            })

    def event_listener(self, event):
        # 
        logging.debug(f"tor event: {event}")

