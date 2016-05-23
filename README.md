# MicroProxy

MicroProxy is a http/https traffic interceptor. 

This project is highly inspired by [mitmproxy](https://github.com/mitmproxy/mitmproxy),
but we take some different approach compare to mitmproxy.

In MicroProxy, we seperate the proxy and viewing into different process and using a message queue to communicate with each other.
By using this kind of approach, we can easily implement different kind of viewing component without changing the proxy code base.
Moreover, we can also open multiple viewing process to listen to the same MicroProxy server.

> Note: We are still in a very earyly stage and as a result, the interface will be changed.

[![Build Status](https://travis-ci.org/mike820324/microProxy.svg?branch=master)](https://travis-ci.org/mike820324/microProxy)
[![Coverage Status](https://coveralls.io/repos/github/mike820324/microProxy/badge.svg?branch=master)](https://coveralls.io/github/mike820324/microProxy?branch=master) 

## System Requirement:
We have tested MicroProxy under **Linux** and **MacOS**.
The python version we are using is version 2.7.10.

> Note: *transparent proxy mode* can only work in Linux machine.

## Environment Setup:

In this section, we will show you the steps to setup the project properly.

### Project Installation

Since we do not have setup.py yet, you can not use **setuptool** to install this project.
Currently, you have to clone the project and use pip to install the requirements.

```bash
git clone https://github.com/mike820324/microProxy.git
cd microProxy
pip install -r requirements.txt
```

### Socks Proxy Setup:

Setting up the socks proxy is very easy.
Just type the following command, and config your browser to use socks proxy with the same port.

```shell
python main.py proxy --host=127.0.0.1 --port=8080
```

### Transparent Proxy Setup:

There may be two possible scenario for transparent proxy setup.

#### In the same machine:
Make sure that your microproxy is run in the different uid or gid.
Let's assume the microproxy is running in **proxy** uid.

Type the following command to setup the transparent proxy for localhost only.

```shell
python main.py proxy --mode=transparent --port=8080
sudo iptables -t nat -A OUTPUT -p tcp -m owner ! --uid-owner proxy --dport 80 -j REDIRECT --to-port 8080
```

#### In different machine:

```shell
python main.py proxy --mode=transparent --port=8080
sudo sysctl -w net.ipv4.ip_forward=1
sudo iptables -t nat -A OUTPUT -p tcp --dport 80 -j REDIRECT --to-port 8080
```

Now set the default gateway of the client machine to the machine that the microProxy is running on.


## Command Line Options:

There are two sub-service for our binary which are

- Proxy: Enable the proxy server.
- Viewer: Open the viewer to view the http traffic.

Each sub-service has there are options.

### Proxy:

The following are the command line options for Proxy service.

* --host: specify the proxy host.
* --port: specify the proxy listening port.
* --mode: specify the proxy mode. Currently we have supported two diffenty mode, **socks proxy** and **transparent proxy**.
* --http-port: specify the additional http port.
* --https-port: specify the additional https port.
* --cert-file: specify the certificate file.
* --key-file: specify the private key file.
* --viewer-channel: specify the viewer channel. For example, tcp://*:5580

For example,
```shell
python main.py proxy --host=127.0.0.1 --port=8080 --mode=socks --http-port=5580 5581 5582 --https-port=5583 5584 5585
python main.py proxy --host=127.0.0.1 --port=8080 --mode=transparent
```
### Viewer:

The following are the command line options for Viewer service.

* --mode: specify the viewer mode. Currently we only support log viewer.
* --viewer-channel: specify the viewer channel. For example, tcp://127.0.0.1:5580

For example,
```shell
python main.py viewer --mode=log 
```

## Configuration File:
Currently, we only support the ini config format. 

The following is an example config file.
```ini
[proxy]
host=127.0.0.1
port=5580
mode=socks
http.port=5581,5582,5583
https.port=5584
certfile=/tmp/cert.crt
keyfile=/tmp/cert.key
viewer.channel=tcp://*:5585

[viewer]
mode=log
viewer.channel=tcp://127.0.0.1:5585
```

