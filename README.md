# TorPool

High-performance, low-latency single-hop Tor proxy pool

[[简体中文文档]](https://github.com/lyc8503/torpool/blob/main/README.zh.md)

## What is this

Tor is a privacy-focused [decentralized network](https://en.wikipedia.org/wiki/Tor_(anonymity_network)) operated by nonprofit organizations and the community.

Community contributors provide many relay servers. Currently, there are [2000+ relays](https://metrics.torproject.org/rs.html#search/flag:exit%20) that can serve as Exits to provide Internet connectivity.

We can use these Exit nodes as a proxy pool to bypass geographic restrictions or IP rate limiting on certain websites.

## Advantages and Disadvantages / Comparison with Existing Projects

Similar projects, such as [Tor-proxy-pool](https://github.com/fxaxg/Tor-proxy-pool) or [torpool](https://github.com/u1234x1234/torpool), launch multiple Tor instances for load balancing and construct standard three-hop Tor circuits.

This project improves upon that by using a Python script to control a single Tor relay instance to establish and manage multiple special single-hop connections, offering the following advantages:

1. Low latency: Using a single hop instead of the traditional three-hop circuit reduces latency to the destination.
2. High concurrency and low resource usage: A VPS with 1 CPU core and 1GB RAM can handle 100+ QPS, with each connection having a random exit IP.

   The downside is that due to limitations in the Tor network, users must set up a real Tor relay node to build single-hop circuits accepted by peers. This generally requires a server with a public IPv4 address.

## How to Use

1. You need a properly running relay node. If you don't have one yet, please refer to [Relay Operations](https://community.torproject.org/relay/).

   Your own node does not need to be an Exit node; a regular relay is sufficient. A newly created node requires some time (one or two hours) to enter the Tor network consensus (can be searched on the [webpage](https://metrics.torproject.org/rs.html)).

   Generally, most cloud service providers do not restrict setting up non-Exit relay nodes and complaints are unlikely. Setting up a relay node may consume additional bandwidth from your VPS; it is recommended to use a high-bandwidth VPS or apply reasonable `RelayBandwidthRate` limits.

2. Build a modified Tor client that accepts one-hop connections

   ```bash
   wget https://dist.torproject.org/tor-0.4.9.17.tar.gz
   tar xvf tor-0.4.9.17.tar.gz && cd tor-0.4.9.17

   git apply tor-allow-1-hop.patch
   ./configure --enable-systemd
   make

   # Replace the system's original tor binary; the specific path depends on the system
   mv src/app/tor /usr/bin/tor
   ```

   Modify the `torrc` configuration to add the following extra settings, allowing the Python script to take over circuit creation and streams (existing tor relay configurations remain unchanged):

   ```
   SocksPort     127.0.0.1:9050
   ControlPort   127.0.0.1:9051
   CookieAuthentication 0
   __LeaveStreamsUnattached 1
   ```

   Restart the Tor service:

   ```bash
   systemctl restart tor@default.service
   ```

3. Run the Python script from this project. On startup, it maintains a specified number of circuits to randomly selected Exits and randomly assigns SOCKS connections to these circuits. At this point, you can directly use the configured SOCKS entry of Tor.

   ```bash
   # Run in the background
   cd src && python3 main.py

   while true; do curl -x socks5h://127.0.0.1:9050 https://wtfismyip.com/; done
   # 162.19.7.11
   # 23.191.200.31
   # 171.25.193.131
   # 185.220.101.55
   # 143.20.185.77
   # 204.8.96.159
   # ......

   # Specifying a username (and any password) enables exit stickiness, attempting to assign the same exit IP
   curl -x socks5h://job1:x@127.0.0.1:9050 https://wtfismyip.com/
   # 171.25.193.82
   curl -x socks5h://job1:x@127.0.0.1:9050 https://wtfismyip.com/
   # 171.25.193.82
   curl -x socks5h://job2:x@127.0.0.1:9050 https://wtfismyip.com/
   # 192.42.116.62
   ```
