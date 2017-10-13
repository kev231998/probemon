#!/usr/bin/python
# -*- encoding: utf-8 -*-

import time
from datetime import datetime
import argparse
import urllib2
import sys
import os
from scapy.all import *
import sqlite3
import netaddr

# deal with socket error when connecting to macvendors.com
from socket import error as SocketError
import errno

NAME = 'probemon'
DESCRIPTION = "a command line tool for logging 802.11 probe request frames"
VERSION = '0.2'

 # list of mac address to ignore or use -I switch
# read config variable from config.txt file
with open('config.txt') as f:
    exec('\n'.join(f.readlines()))

def insert_into_db(fields, db):
    date, mac, vendor, ssid, rssi = fields
    conn = sqlite3.connect(db)
    c = conn.cursor()

    c.execute('select id from vendor where name=?', (vendor,))
    row = c.fetchone()
    if row is None:
        c.execute('insert into vendor (name) values(?)', (vendor,))
        c.execute('select id from vendor where name=?', (vendor,))
        row = c.fetchone()
    vendor_id = row[0]

    c.execute('select id from mac where address=?', (mac,))
    row = c.fetchone()
    if row is None:
        c.execute('insert into mac (address,vendor) values(?, ?)', (mac, vendor_id))
        c.execute('select id from mac where address=?', (mac,))
        row = c.fetchone()
    mac_id = row[0]

    c.execute('select id from ssid where name=?', (ssid,))
    row = c.fetchone()
    if row is None:
        c.execute('insert into ssid (name) values(?)', (ssid,))
        c.execute('select id from ssid where name=?', (ssid,))
        row = c.fetchone()
    ssid_id = row[0]

    c.execute('insert into probemon values(?, ?, ?, ?)', (date, mac_id, ssid_id, rssi))

    conn.commit()
    conn.close()

def build_packet_cb(network, db, stdout):
    def packet_callback(packet):
        now = time.time()
        # look up vendor from OUI value in MAC address
        if network:
            try:
                r = urllib2.urlopen('https://api.macvendors.com/%s' % packet.addr2)
                fields.append(r.read())
                r.close()
            except SocketError as e:
                if e.errno != errno.ECONNRESET:
                    raise # Not error we are looking for
                vendor = 'UNKNOWN'
            except urllib2.HTTPError:
                vendor = 'UNKNOWN'
            except urllib2.URLError:
                vendor = 'UNKNOWN'
        else:
            try:
                parsed_mac = netaddr.EUI(packet.addr2)
                vendor = parsed_mac.oui.registration().org
            except netaddr.core.NotRegisteredError, e:
                vendor = 'UNKNOWN'
        # calculate RSSI value (might be [-4:-3] for you)
        rssi = -(256-ord(packet.notdecoded[-2:-1]))

        fields = [now, packet.addr2, vendor, packet.info, rssi]

        if packet.addr2 not in IGNORED:
            insert_into_db(fields, db)

            if stdout:
                # convert time to iso
                fields[0] = str(datetime.fromtimestamp(now))[:-3].replace(' ','T')
                print '\t'.join(str(i) for i in fields)

    return packet_callback

def main():
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument('-c', '--channel', default=1, type=int, help="the channel to listen on")
    parser.add_argument('-d', '--db', default='probemon.db', help="database file name to use")
    parser.add_argument('-i', '--interface', required=True, help="the capture interface to use")
    parser.add_argument('-I', '--ignore', action='append', help="mac address to ignore")
    parser.add_argument('-n', '--network', action='store_true', default=False, help="to use the network to look up for mac address vendor")
    parser.add_argument('-s', '--stdout', action='store_true', default=False, help="also log probe request to stdout")
    args = parser.parse_args()

    if args.ignore is not None:
        IGNORED = args.ignore

    conn = sqlite3.connect(args.db)
    c = conn.cursor()
    # create tables if they do not exists
    sql = 'create table if not exists vendor(id integer not null primary key, name text)'
    c.execute(sql)
    sql = '''create table if not exists mac(id integer not null primary key, address text,
        vendor integer,
        foreign key(vendor) references vendor(id)
        )'''
    c.execute(sql)
    sql = 'create table if not exists ssid(id integer not null primary key, name text)'
    c.execute(sql)
    sql = '''create table if not exists probemon(date float,
        mac integer,
        ssid integer,
        rssi integer,
        foreign key(mac) references mac(id),
        foreign key(ssid) references ssid(id)
        )'''
    c.execute(sql)
    conn.commit()
    conn.close()

    # sniff on specified channel
    os.system("iwconfig %s channel %d >/dev/null 2>&1" % (args.interface, args.channel))

    sniff(iface=args.interface, prn=build_packet_cb(args.network, args.db, args.stdout),
        store=0, lfilter=lambda x:x.haslayer(Dot11ProbeReq))

if __name__ == '__main__':
    main()

# vim: set et ts=4 sw=4:
