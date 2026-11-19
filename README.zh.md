# TorPool

高性能低延迟的单跳 Tor 代理池

## 这是什么

Tor 是一个由非盈利组织和社区运营的, 关注隐私的[去中心化网络](https://zh.wikipedia.org/wiki/%E6%B4%8B%E8%91%B1%E8%B7%AF%E7%94%B1).

社区贡献者会贡献许多 relay 服务器, 目前有 [2000+ relay](https://metrics.torproject.org/rs.html#search/flag:exit%20) 可以作为 Exit 提供到互联网的连接.

我们可以使用这些 Exit 节点作为代理池, 用于绕过部分网站的地区限制或 IP 频控.

## 优缺点 / 与现有项目的比较

类似的项目, 例如 [Tor-proxy-pool](https://github.com/fxaxg/Tor-proxy-pool) 或 [torpool](https://github.com/u1234x1234/torpool), 均会启动多个 Tor 实例进行负载均衡, 并构建标准的 Tor 三跳链路.

本项目对此进行了优化, 通过 python 脚本控制单个 Tor relay 实例建立并管理多个特殊的单跳连接, 有以下优点:

1. 低延迟, 使用单跳而非传统的 3 跳链路, 降低到目标的延迟
2. 高并发与低资源占用, 1 核心 1GB RAM 的 VPS 可以承载 100+ QPS, 每个连接均为随机出口 IP

   缺点则是由于 Tor 网络的限制, 使用者必须搭建一个真实的 Tor relay 节点才能构建可被 peer 接受的单跳链路. 这一般需要一个有公网 IPv4 地址的服务器.

## 如何使用

1. 你需要一个正常运行的 relay 节点, 如果你还没有的话, 请参考 [Relay Operations](https://community.torproject.org/relay/).

   你自己的节点不需要是 Exit 节点, 普通 Relay 就足够了. 新建的节点需要一段时间 (一两个小时) 以进入 Tor 网络共识 (可在[网页](https://metrics.torproject.org/rs.html)搜索). 

   一般来说, 大部分云服务商不会限制你搭建非 Exit 的 relay 节点, 也不会遭到投诉. 搭建 relay 节点可能会消耗你的 VPS 的额外流量, 建议使用大流量的 VPS 或进行合理的 `RelayBandwidthRate` 限制.

2. 构建修补过后的 Tor 客户端接受一跳的连接

   ```bash
   wget https://dist.torproject.org/tor-0.4.9.17.tar.gz
   tar xvf tor-0.4.9.17.tar.gz && cd tor-0.4.9.17

   git apply tor-allow-1-hop.patch
   ./configure --enable-systemd
   make

   # 替换系统原有的 tor 二进制, 具体路径取决于系统
   mv src/app/tor /usr/bin/tor
   ```

   更改 `torrc` 配置添加以下额外配置, 用于让 Python 脚本接管 circuit 创建和 stream (原有 tor relay 配置不用动):

   ```
   SocksPort     127.0.0.1:9050
   ControlPort   127.0.0.1:9051
   CookieAuthentication 0
   __LeaveStreamsUnattached 1
   ```

   重启 Tor 服务:

   ```bash
   systemctl restart tor@default.service
   ```

3. 运行本项目的 Python 脚本, 其启动时会维护指定数目个 circuit 到随机选中的 Exit, 并将 socks 连接随机分配给 circuit. 此时直接使用 tor 配置的 socks 入口即可.

   ```bash
   # 在后台保持运行
   cd src && python3 main.py

   while true; do curl -x socks5h://127.0.0.1:9050 https://wtfismyip.com/; done
   # 162.19.7.11
   # 23.191.200.31
   # 171.25.193.131
   # 185.220.101.55
   # 143.20.185.77
   # 204.8.96.159
   # ......

   # 指定一个 username (和任意密码) 可以保持出口粘性, 尽可能分配为同一个出口 IP
   curl -x socks5h://job1:x@127.0.0.1:9050 https://wtfismyip.com/
   # 171.25.193.82
   curl -x socks5h://job1:x@127.0.0.1:9050 https://wtfismyip.com/
   # 171.25.193.82
   curl -x socks5h://job2:x@127.0.0.1:9050 https://wtfismyip.com/
   # 192.42.116.62
   ```
