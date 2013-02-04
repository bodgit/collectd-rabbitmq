#! /usr/bin/env python

# RabbitMQ plugin for collectd

import collectd
import urllib2
from urllib2 import HTTPError, URLError
import json

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

def dispatch_values(instance, values, type, plugin=None):
    v = collectd.Values(plugin='rabbitmq')
    if plugin:
        v.plugin_instance = plugin
    v.type = type
    v.type_instance = instance
    v.values = values
    v.dispatch()

def fetch_json(url):
    try:
        f = urllib2.urlopen(url)
        return json.load(f)
    except URLError, e:
        collectd.error('rabbitmq plugin: Error connecting to %s - %r' % (url, e))
    except HTTPError, e:
        collectd.error('rabbitmq plugin: HTTP error connecting to %s - HTTP code %d' % (url, e.code))

    return

def rabbitmq_read():
    authinfo = urllib2.HTTPBasicAuthHandler()
    authinfo.add_password(realm='RabbitMQ Management',
                          uri='http://%s:%d/api/' % (host, port),
                          user=username,
                          passwd=password)

    opener = urllib2.build_opener(authinfo)

    urllib2.install_opener(opener)

    u = 'http://%s:%d/api/overview' % (host, port)

    j = fetch_json(u)

    # Objects, exchanges, queues, etc.
    for o in j['object_totals']:
        dispatch_values(o, [j['object_totals'][o]], 'gauge')

    # Global message statistics, infer rates from these counters rather
    # than use what RabbitMQ calculates
    for m in j['message_stats']:
        if m.endswith('_details'):
            continue
        dispatch_values('msg_' + m, [j['message_stats'][m]], 'counter')

    # Queue totals, across all queues currently defined
    for q in j['queue_totals']:
        if q.endswith('_details'):
            continue
        dispatch_values('queued_' + q, [j['queue_totals'][q]], 'gauge')

    # Use the previous JSON document to get the node name
    u = 'http://%s:%d/api/nodes/%s' % (host, port, j['node'])

    # Must be a nicer way of doing this?
    if extended_memory:
        u += '?memory=true'

    j = fetch_json(u)

    metrics = {
        'bytes': [
            'disk_free',
            'disk_free_limit',
            'mem_limit',
            'mem_used'
        ],
        'gauge': [
            'fd_total',
            'fd_used',
            'proc_total',
            'proc_used',
            'sockets_total',
            'sockets_used'
        ],
        'uptime': [
            'uptime'
        ]
    }

    for type in metrics:
        for metric in metrics[type]:
            dispatch_values(metric, [j[metric]], type)

    if extended_memory:
        for m in j['memory']:
            # Skip the total, can infer it by summing the individual counts
            if m == 'total':
                continue
            # Prefix each memory pool to help distinguish them
            dispatch_values('mem_' + m, [j['memory'][m]], 'bytes')

    # Per-queue statistics
    u = 'http://%s:%d/api/queues' % (host, port)

    j = fetch_json(u)

    # Loop through each queue
    #
    # XXX vhost is currently ignored
    # XXX temporary queues are not currently ignored
    for queue in j:
        dispatch_values('memory', [queue['memory']], 'bytes', queue['name'])
        for m in queue['message_stats']:
            if m.endswith('_details'):
                continue
            dispatch_values('msg_' + m, [queue['message_stats'][m]], 'counter', queue['name'])
        for stat in queue:
            if not stat.startswith('messages'):
                continue
            if stat.endswith('_details'):
                continue
            dispatch_values('queued_' + stat, [queue[stat]], 'gauge', queue['name'])

collectd.register_config(rabbitmq_config)
collectd.register_read(rabbitmq_read)
