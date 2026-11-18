import hashlib

import stem.control
import logging
import random
import threading
import time


class TorPool:
    def __init__(self, tor_addr='127.0.0.1', controller_port=9051, socks_port=9050, exit_count=10, close_existing_ctl_circuits=True):
        self.tor_addr = tor_addr
        self.socks_port = socks_port
        self.exit_count = exit_count

        self.controller = stem.control.Controller.from_port(address=tor_addr, port=controller_port)
        self.controller.authenticate()
        self.circuits = []
        self.sticky_sessions = {}  # map of username -> circuit_id for sticky sessions

        logging.info(f"connected to Tor controller at {tor_addr}:{controller_port}")
        self.controller.add_event_listener(self._event_listener, stem.control.EventType.STREAM, stem.control.EventType.CIRC)

        # close leftover controller circuits from previous runs, if any
        if close_existing_ctl_circuits:
            self._close_ctl_circuits()

        # thread to maintain the desired number of 1-hop circuits to exit nodes
        self.maintain_thread = threading.Thread(target=self._maintain_circuits, daemon=True)
        self.maintain_thread.start()

    def _close_ctl_circuits(self):
        for c in self.controller.get_circuits():
            if c.purpose == "CONTROLLER":
                try:
                    self.controller.close_circuit(c.id)
                    logging.info(f"closed leftover controller circuit {c.id}")
                except:
                    pass

    def _get_eligible_exit_nodes(self):
        exits = []
        for node in self.controller.get_network_statuses():
            # must have Exit/Running/Fast flags
            if any(map(lambda x: x not in node.flags, ['Exit', 'Running', 'Fast'])):
                continue
            # must not have BadExit flag
            if 'BadExit' in node.flags:
                continue
            # TODO: more filters, e.g. country, allowed ports, etc.
            exits.append({
                'fingerprint': node.fingerprint,
                'address': node.address,
                'port': node.or_port,
                'nickname': node.nickname,
            })
        logging.debug(f"found {len(exits)} eligible exit nodes")
        return exits

    def _new_circuit(self, exit_node):
        # create a new 1-hop circuit to the given exit node
        # properly configured tor instance will authenticate us as relay,
        # so the peer exit will allow us using this circuit for outgoing connections
        circ_id = self.controller.new_circuit([exit_node['fingerprint']], purpose='controller', await_build=True, timeout=10)
        logging.debug(f"new circuit {circ_id} to exit node {exit_node['nickname']} ({exit_node['address']})")
        return circ_id

    def _maintain_circuits(self):
        # block forever, maintain self.exit_count 1-hop relay circuits to random selected exits
        while True:
            try:
                # 1. clean broken circuits
                circ_query = self.controller.get_circuits()
                built_circ_ids = {c.id for c in circ_query if c.status == 'BUILT'}
                alive = []
                for c in self.circuits:
                    if c['circ_id'] not in built_circ_ids:
                        logging.warning(f"circuit {c['circ_id']} to exit node {c['exit_node']['nickname']} status != BUILT, removing")
                        continue
                    alive.append(c)
                self.circuits = alive

                # 2. create new circuits if needed
                if len(self.circuits) < self.exit_count:
                    nodes = self._get_eligible_exit_nodes()
                    unconnected_nodes = [n for n in nodes if n['fingerprint'] not in [c['exit_node']['fingerprint'] for c in self.circuits]]
                    random.shuffle(unconnected_nodes)

                    needed = self.exit_count - len(self.circuits)
                    logging.info(f"need {needed} new exit circuits, currently have {len(self.circuits)}")
                    if len(unconnected_nodes) < needed:
                        logging.warning(f"not enough new exit candidates: {len(unconnected_nodes)} < {self.exit_count - len(self.circuits)}")

                    for n in unconnected_nodes[:needed]:
                        try:
                            circ_id = self._new_circuit(n)
                            self.circuits.append({
                                'circ_id': circ_id,
                                'exit_node': n
                            })
                        except Exception as e:
                            logging.warning(f"failed to create circuit to exit node {n['nickname']} ({n['address']}): {e}")
            except Exception as e:
                logging.error(f"unexpected error in maintain_circuits: {e}")
            finally:
                time.sleep(5)

    def _event_listener(self, event):
        logging.debug(f"tor event: {event.type} {event}")
        if event.type == stem.control.EventType.STREAM:
            # when __LeaveStreamsUnattached is set, streams (socks clients) won't be attached to circuits automatically
            # so we can manually attach streams to custom 1-hop circuits
            if event.status == 'CONTROLLER_WAIT':
                username = event.keyword_args.get("SOCKS_USERNAME")
                if username:
                    circ = None
                    # find existing sticky session for this username, if any
                    if self.sticky_sessions.get(username):
                        circ = self.sticky_sessions[username]
                        if circ['circ_id'] not in [c['circ_id'] for c in self.circuits]:
                            logging.warning(f"sticky session for username {username} points to circuit {circ['circ_id']} which is no longer alive, removing")
                            del self.sticky_sessions[username]
                            circ = None
                    # create a new sticky session for this username if none exists, choosing the least frequently used circuit
                    if not circ:
                        circ = min(self.circuits, key=lambda c: sum(1 for s in self.sticky_sessions.values() if s['circ_id'] == c['circ_id']))
                        self.sticky_sessions[username] = circ
                        logging.info(f"created sticky session for username {username} to circuit {circ['circ_id']} {circ['exit_node']['address']}")
                else:
                    # attach new streams to random 1-hop circuits if no username
                    circ = random.choice(self.circuits)

                circ_id, address = circ['circ_id'], circ['exit_node']['address']
                self.controller.attach_stream(event.id, circ_id)
                logging.info(f"attached stream {event.id} to circuit {circ_id} {address}")

    def circuit_count(self):
        return len(self.circuits)
