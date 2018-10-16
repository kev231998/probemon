#!/usr/bin/python2
# -*- encoding: utf-8 -*-

import time
from datetime import datetime
import argparse
import sys
import os
import sqlite3
import netaddr
import base64
from lru import LRU
import atexit

# read config variable from config.py file
from config import *

NAME = 'probemon'
DESCRIPTION = "a command line tool for logging 802.11 probe request frames"
VERSION = '0.3'

mac_cache = LRU(128)
ssid_cache = LRU(128)
vendor_cache = LRU(128)

class Colors:
    red = '\033[31m'
    green = '\033[32m'
    yellow = '\033[33m'
    blue = '\033[34m'
    magenta = '\033[35m'
    cyan = '\033[36m'
    endc = '\033[0m'
    bold = '\033[1m'
    underline = '\033[4m'

def insert_into_db(fields, conn, c):
    date, mac, vendor, ssid, rssi = fields

    try:
        vendor_id = vendor_cache[vendor]
    except KeyError as k:
        c.execute('select id from vendor where name=?', (vendor,))
        row = c.fetchone()
        if row is None:
            c.execute('insert into vendor (name) values(?)', (vendor,))
            c.execute('select id from vendor where name=?', (vendor,))
            row = c.fetchone()
        vendor_id = row[0]
        vendor_cache[vendor] = vendor_id

    try:
        mac_id = mac_cache[mac]
    except KeyError as k:
        c.execute('select id from mac where address=?', (mac,))
        row = c.fetchone()
        if row is None:
            c.execute('insert into mac (address,vendor) values(?, ?)', (mac, vendor_id))
            c.execute('select id from mac where address=?', (mac,))
            row = c.fetchone()
        mac_id = row[0]
        mac_cache[mac] = mac_id

    try:
        ssid_id = ssid_cache[ssid]
    except KeyError as k:
        c.execute('select id from ssid where name=?', (ssid,))
        row = c.fetchone()
        if row is None:
            c.execute('insert into ssid (name) values(?)', (ssid,))
            c.execute('select id from ssid where name=?', (ssid,))
            row = c.fetchone()
        ssid_id = row[0]
        ssid_cache[ssid] = ssid_id

    c.execute('insert into probemon values(?, ?, ?, ?)', (date, mac_id, ssid_id, rssi))

    try:
        conn.commit()
    except sqlite3.OperationalError as e:
        # db is locked ? Retry again
        time.sleep(10)
        conn.commit()

def build_packet_cb(conn, c, stdout, ignored):
    def packet_callback(packet):
        now = time.time()
        # look up vendor from OUI value in MAC address
        try:
            parsed_mac = netaddr.EUI(packet.addr2)
            vendor = parsed_mac.oui.registration().org
        except netaddr.core.NotRegisteredError as e:
            vendor = u'UNKNOWN'
        except IndexError as e:
            vendor = u'UNKNOWN'

        # parse headers to get RSSI value
        try:
            rssi = -(256-ord(packet.notdecoded[-2:-1]))
            if rssi == -256:
                rssi = -(256-ord(packet.notdecoded[-4:-3]))
        except TypeError as e:
            try:
                rssi = -(256-ord(packet.notdecoded[-4:-3]))
            except TypeError as f:
                rssi = 0

        try:
            ssid = packet.info.decode('utf-8')
        except UnicodeDecodeError as u:
            # encode the SSID in base64 because it will fail
            # to be inserted into the db otherwise
            ssid = u'b64_%s' % base64.b64encode(packet.info)
        fields = [now, packet.addr2, vendor, ssid, rssi]

        if packet.addr2 not in ignored:
            insert_into_db(fields, conn, c)

            if stdout:
                if fields[1] in KNOWNMAC:
                    fields[1] = u'%s%s%s%s' % (Colors.bold, Colors.red, fields[1], Colors.endc)
                # convert time to iso
                fields[0] = str(datetime.fromtimestamp(now))[:-3].replace(' ','T')
                print '\t'.join(str(i) for i in fields)

    return packet_callback

def init_db(conn, c):
    # create tables if they do not exist
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

def close_db(conn):
    conn.close()

def main():
    # sniff on specified channel
    os.system('iw dev %s set channel %d' % (args.interface, args.channel))

    print ":: Started listening to probe requests on channel %d on interface %s" % (args.channel, args.interface)
    sniff(iface=args.interface, prn=build_packet_cb(conn, c, args.stdout, IGNORED),
        store=0, lfilter=lambda x:x.haslayer(Dot11ProbeReq))

if __name__ == '__main__':
    conn = None
    try:
        parser = argparse.ArgumentParser(description=DESCRIPTION)
        parser.add_argument('-c', '--channel', default=1, type=int, help="the channel to listen on")
        parser.add_argument('-d', '--db', default='probemon.db', help="database file name to use")
        parser.add_argument('-i', '--interface', required=True, help="the capture interface to use")
        parser.add_argument('-I', '--ignore', action='append', help="mac address to ignore")
        parser.add_argument('-s', '--stdout', action='store_true', default=False, help="also log probe request to stdout")
        args = parser.parse_args()

        global IGNORED
        if args.ignore is not None:
            IGNORED = args.ignore

        # only import scapy here to avoid delay if error in argument parsing
        print 'Loading scapy...'
        from scapy.all import *

        conn = sqlite3.connect(args.db)
        c = conn.cursor()
        atexit.register(close_db, conn)
        init_db(conn, c)

        main()
    except KeyboardInterrupt as e:
        pass
    finally:
        if conn is not None:
            conn.close()

# vim: set et ts=4 sw=4:
