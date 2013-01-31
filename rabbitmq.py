#! /usr/bin/env python

# RabbitMQ plugin for collectd

import collectd
import urllib2
import json
from socket import gethostname

host = 'localhost'
port = 15672
username = 'guest'
password = 'guest'
extended_memory = False

def rabbitmq_config(c):
    global host, port, username, password, extended_memory

    for child in c.children:
        if child.key == 'Host':
            host = child.values[0]
        elif child.key == 'Port':
            port = int(child.values[0])
        elif child.key == 'Username':
            username = child.values[0]
        elif child.key == 'Password':
            password = child.values[0]
        elif child.key == 'ExtendedMemory':
            extended_memory = bool(child.values[0])

def rabbitmq_read():
    authinfo = urllib2.HTTPBasicAuthHandler()
    authinfo.add_password(realm='RabbitMQ Management',
                          uri='http://%s:%d/api/' % (host, port),
                          user=username,
                          passwd=password)

    opener = urllib2.build_opener(authinfo)

    urllib2.install_opener(opener)

    l = gethostname().split('.')[0]

    f = urllib2.urlopen('http://%s:%d/api/nodes/rabbit@%s?memory=true' % (host, port, l))
    j = json.load(f)

    for m in j['memory']:
        if m == 'total':
            continue
        v = collectd.Values(plugin='rabbitmq')
        v.type = 'bytes'
        v.type_instance = m
        v.values = [j['memory'][m]]
        v.dispatch()

collectd.register_config(rabbitmq_config)
collectd.register_read(rabbitmq_read)
