#!/usr/bin/python3

import sqlite3
import argparse
import time
import sys
import os.path

# avoid IOError when quitting less
from signal import signal, SIGPIPE, SIG_DFL
signal(SIGPIPE, SIG_DFL)

NUMOFSECSINADAY = 60*60*24
MAX_VENDOR_LENGTH = 25
MAX_SSID_LENGTH = 15

# read config variable from config.py file
import config

def is_local_bit_set(mac):
    byte = mac.split(':')
    try:
        bi = int(byte[0], 16)
        return  bi & 0b00000010 == 0b00000010
    except ValueError as e:
        return False

def median(lst):
    n = len(lst)
    if n < 1:
        return None
    if n % 2 == 1:
        return sorted(lst)[n//2]
    else:
        return sum(sorted(lst)[n//2-1:n//2+1])//2

def parse_ts(ts):
    try:
        date = time.strptime(ts, '%Y-%m-%dT%H:%M')
    except  ValueError:
        try:
            date = time.strptime(ts, '%Y-%m-%d')
            date = time.strptime('%sT12:00' % ts, '%Y-%m-%dT%H:%M')
        except ValueError:
            print("Error: can't parse date timestamp", file=sys.stderr)
            sys.exit(-1)
    t = time.mktime(date)
    return t

def build_sql_query(after, before, macs, rssi, zero, day):
    sql_head = '''select date,mac.address,vendor.name,ssid.name,rssi from probemon
    inner join mac on mac.id=probemon.mac
    inner join vendor on vendor.id=mac.vendor
    inner join ssid on ssid.id=probemon.ssid'''
    sql_tail = 'order by date'

    sql_where_clause = ''
    sql_args = []

    def add_arg(clause, op, new_arg):
        if clause == '':
            clause = '%s' % new_arg
        else:
            clause = '%s %s %s' % (clause, op, new_arg)
        return clause

    if macs:
        for mac in macs:
            if len(mac) != 17:
                mac = '%s%%' % mac
            sql_where_clause = add_arg(sql_where_clause, 'or', 'mac.address like ?')
            sql_args.append(mac)
        if len(macs) > 1:
            sql_where_clause = '(%s)' % sql_where_clause
    if rssi:
        sql_where_clause = add_arg(sql_where_clause, 'and', 'rssi>?')
        sql_args.append(rssi)

    if day:
        before = time.time() # now
        after = before - NUMOFSECSINADAY # since one day in the past

    if after is not None:
        sql_where_clause = add_arg(sql_where_clause, 'and', 'date>?')
        sql_args.append(after)
    if before is not None:
        sql_where_clause = add_arg(sql_where_clause, 'and', 'date<?')
        sql_args.append(before)

    if zero:
        sql_where_clause = add_arg(sql_where_clause, 'and', 'rssi != 0')

    if len(config.IGNORED) > 0:
        arg_list = ','.join(['?']*len(config.IGNORED))
        sql_where_clause = add_arg(sql_where_clause, 'and', 'mac.address not in (%s)' % (arg_list,))
        sql_args.extend(config.IGNORED)

    sql = '%s where %s %s' % (sql_head, sql_where_clause, sql_tail)
    return sql, sql_args

def main():
    parser = argparse.ArgumentParser(description='Display various stats about mac addresses/probe requests in the database')
    parser.add_argument('-a', '--after', help='filter before this timestamp')
    parser.add_argument('-b', '--before', help='filter after this timestamp')
    parser.add_argument('-d', '--day', action='store_true', help='filter only for the past day')
    parser.add_argument('--day-by-day', action='store_true', help='day by day stats for given mac')
    parser.add_argument('--db', default='probemon.db', help='file name of database')
    parser.add_argument('--list-mac-ssids', action='store_true', help='list ssid with mac that probed for it')
    parser.add_argument('-l', '--log', action='store_true', help='log all entries instead of showing stats')
    parser.add_argument('-m', '--mac', action='append', help='filter for that mac address')
    parser.add_argument('-p', '--privacy', action='store_true', help='merge all LAA mac into one')
    parser.add_argument('-r', '--rssi', type=int, help='filter for that minimal RSSI value')
    parser.add_argument('-s', '--ssid', help='look up for mac that have probed for that ssid')
    parser.add_argument('-z', '--zero', action='store_true', help='filter rssi value of 0')
    args = parser.parse_args()

    if args.list_mac_ssids:
        args.mac = None
        args.day_by_day = False

    if args.day and (args.before or args.after):
        print('Error: --day conflicts with --after or --before', file=sys.stderr)
        sys.exit(-1)

    if args.day_by_day and not args.mac:
        print('Error: --day-by-day needs a --mac switch', file=sys.stderr)
        sys.exit(-1)

    before = None
    after = None
    if args.after:
        after = parse_ts(args.after)
    if args.before:
        before = parse_ts(args.before)

    if not os.path.exists(args.db):
        print(f'Error: file not found {args.db}', file=sys.stderr)
        sys.exit(-1)

    if args.ssid and args.mac:
        print(':: Ignoring --mac switch')
        args.mac = None

    conn = sqlite3.connect(args.db)
    c = conn.cursor()
    sql = 'pragma query_only = on;'
    c.execute(sql)
    sql = 'pragma temp_store = 2;' # to store temp table and indices in memory
    c.execute(sql)
    sql = 'pragma journal_mode = off;' # disable journal for rollback (we don't use this)
    c.execute(sql)
    conn.commit()

    if args.ssid:
        c.execute('select id from ssid where name=?', (args.ssid,))
        ssid = c.fetchone()
        if ssid is None:
            print('Error: ssid not found', file=sys.stderr)
            conn.close()
            sys.exit(-1)
        c.execute('select distinct mac from probemon where ssid=?', (ssid[0],))

        macs = []
        # search for mac that have probed that ssid
        for row in c.fetchall():
            c.execute('select address from mac where id=?', (row[0],))
            mac = c.fetchone()[0]
            if args.privacy and is_local_bit_set(mac):
                continue
            macs.append(mac)

        print(f'{args.ssid} : {", ".join(macs)}')
        conn.close()
        return

    sql, sql_args = build_sql_query(after, before, args.mac, args.rssi, args.zero, args.day)
    try:
        c.execute(sql, sql_args)
    except sqlite3.OperationalError as e:
        time.sleep(2)
        c.execute(sql, sql_args)

    if args.log:
        # simply output each log entry to stdout
        for t, m, mc, ssid, rssi in c.fetchall():
            t = time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(t))
            if is_local_bit_set(m):
                m = '%s (LAA)' % m
            # strip mac vendor string to MAX_VENDOR_LENGTH chars, left padded with space
            if len(mc) > MAX_VENDOR_LENGTH:
                mc = mc[:MAX_VENDOR_LENGTH-3]+ '...'
            else:
                mc = mc.ljust(MAX_VENDOR_LENGTH)
            # do the same for ssid
            if len(ssid) > MAX_SSID_LENGTH:
                ssid = ssid[:MAX_SSID_LENGTH-3]+ '...'
            else:
                ssid = ssid.ljust(MAX_SSID_LENGTH)
            print('\t'.join([t, m, mc, ssid, str(rssi)]))

        conn.close()
        return

    if args.day_by_day:
        # gather stats day by day for args.mac
        stats = {}
        for row in c.fetchall():
            if row[1] not in list(stats.keys()):
                stats[row[1]] = {'vendor': row[2]}
            day = time.strftime('%Y-%m-%d', time.localtime(row[0]))
            if day in stats[row[1]]:
                smd = stats[row[1]][day]
                smd['rssi'].append(row[4])
                if row[0] > smd['last']:
                    smd['last'] = row[0]
                if row[0] < smd['first']:
                    smd['first'] = row[0]
            else:
                stats[row[1]][day] = {'rssi': [row[4]], 'first': row[0], 'last': row[0]}
        conn.close()

        for mac in list(stats.keys()):
            vendor = stats[mac]['vendor']
            del stats[mac]['vendor']
            days = sorted(stats[mac].keys())
            print(f'MAC: {mac}, VENDOR: {vendor}')
            for d in days:
                rssi = stats[mac][d]['rssi']
                first = time.strftime('%H:%M:%S', time.localtime(stats[mac][d]['first']))
                last = time.strftime('%H:%M:%S', time.localtime(stats[mac][d]['last']))
                print(f'  {d}: [{first}-{last}]', end=' ')
                print(f'  RSSI: #: {len(rssi):4d}, min: {min(rssi):3d}, max: {max(rssi):3d}, avg: {sum(rssi)//len(rssi):3d}, median: {median(rssi):3d}')
        return

    if args.list_mac_ssids:
        ssids = {}
        for row in c.fetchall():
            ssid = row[3]
            if ssid == '' or is_local_bit_set(row[1]):
                continue
            if ssid not in ssids:
                ssids[ssid] = set([row[1]])
            else:
                ssids[ssid].add(row[1])
        si = sorted(list(ssids.items()), key=lambda x:len(x[1]))
        si.reverse()
        for k,v in si:
            if len(v) > 1:
                print(f'{k}: {", ".join(v)}')

        conn.close()
        return
    # gather stats about each mac
    macs = {}
    for row in c.fetchall():
        mac = row[1]
        if args.privacy and is_local_bit_set(mac):
            # create virtual mac for LAA mac address
            mac = 'LAA'
        if mac not in macs:
            macs[mac] = {'vendor': row[2], 'ssid': [], 'rssi': [], 'last': row[0], 'first':row[0]}
        d = macs[mac]
        if row[3] != '' and row[3] not in d['ssid']:
            d['ssid'].append(row[3])
        if row[0] > d['last']:
            d['last'] = row[0]
        if row[0] < d['first']:
            d['first'] = row[0]
        if row[4] != 0:
            d['rssi'].append(row[4])

    conn.close()

    # sort on frequency of appearence of a mac
    tmp = [(k,len(v['rssi'])) for k,v in list(macs.items())]
    tmp = reversed(sorted(tmp, key=lambda k:k[1]))

    # print our stats
    for k,_ in tmp:
        v = macs[k]
        laa = ' (LAA)' if is_local_bit_set(k) else ''
        print(f'MAC: {k}{laa}, VENDOR: {v["vendor"]}')
        print(f'  SSIDs: {",".join(sorted(v["ssid"]))}')
        rssi = v['rssi']
        if rssi != []:
            print(f'  RSSI: #: {len(rssi):4d}, min: {min(rssi):3d}, max: {max(rssi):3d}, avg: {sum(rssi)//len(rssi):3d}, median: {median(rssi):3d}')
        else:
            print('  RSSI: Nothing found.')

        first = time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(v['first']))
        last = time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(v['last']))
        print(f'  First seen at {first} and last seen at {last}')

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
