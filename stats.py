import sqlite3
import urllib2
import argparse
import time
import sys

# for correct handling of encoding when piping to less
import codecs
import locale
sys.stdout = codecs.getwriter(locale.getpreferredencoding())(sys.stdout)
# avoid IOError when quitting less
from signal import signal, SIGPIPE, SIG_DFL
signal(SIGPIPE, SIG_DFL)

NUMOFSECSINADAY = 60*60*24

# read config variable from config.txt file
with open('config.txt') as f:
    exec('\n'.join(f.readlines()))

def is_local_bit_set(mac):
    fields = mac.split(':')
    if '{0:08b}'.format(int(fields[0], 16))[-2] == '1':
    	return True
    return False

def median(lst):
    n = len(lst)
    if n < 1:
        return None
    if n % 2 == 1:
        return sorted(lst)[n//2]
    else:
        return sum(sorted(lst)[n//2-1:n//2+1])/2.0

def parse_ts(ts):
    try:
        t = time.mktime(time.strptime(ts, '%Y-%m-%dT%H:%M'))
    except  ValueError:
        try:
            date = time.strptime(ts, '%Y-%m-%d')
            date = time.strptime('%sT12:00' % ts, '%Y-%m-%dT%H:%M')
            t = time.mktime(date)
        except ValueError:
            print "Error: can't parse date timestamp"
            sys.exit(-1)
    return t

def build_sql_query(after, before, mac, rssi, zero, day):
    sql_head = '''select date,mac.address,vendor.name,ssid.name,rssi from probemon
    inner join mac on mac.id=probemon.mac
    inner join vendor on vendor.id=mac.vendor
    inner join ssid on ssid.id=probemon.ssid'''
    sql_tail = 'order by date'

    if mac:
        if len(mac) != 17:
            mac = '%s%%' % mac
        sql_where_clause = 'where mac.address like ?'
        sql_args = [mac]
    elif rssi:
        sql_where_clause = 'where rssi>?'
        sql_args = [rssi]
    else:
        sql_where_clause = ''
        sql_args = []

    if day:
        before = time.time() # now
        after = before - NUMOFSECSINADAY # since one day in the past

    if after is not None:
        sql_where_clause = '%s and date >?' % (sql_where_clause,)
        sql_args.append(after)
    if before is not None:
        sql_where_clause = '%s and date <?' % (sql_where_clause,)
        sql_args.append(before)

    if zero:
        if sql_where_clause != '':
            sql_where_clause = '%s and rssi !=0' % (sql_where_clause,)
        else:
            sql_where_clause = 'where rssi != 0'

    if len(IGNORED) > 0:
        arg_list = ','.join(['?']*len(IGNORED))
        sql_where_clause = '%s and mac.address not in (%s)' % (sql_where_clause, arg_list)
        sql_args.extend(IGNORED)

    sql = '%s %s %s' % (sql_head, sql_where_clause, sql_tail)
    return sql, sql_args

def main():
    parser = argparse.ArgumentParser(description='Find RSSI stats for a given mac')
    parser.add_argument('-a', '--after', help='filter before this timestamp')
    parser.add_argument('-b', '--before', help='filter after this timestamp')
    parser.add_argument('-d', '--day', action='store_true', help='filter only for the past day')
    parser.add_argument('--db', default='probemon.db', help='file name of database')
    parser.add_argument('-l', '--log', action='store_true', help='log all entries instead of showing stats')
    parser.add_argument('-m', '--mac', help='filter for that mac address')
    parser.add_argument('-r', '--rssi', type=int, help='filter for that minimal RSSI value')
    parser.add_argument('-p', '--privacy', action='store_true', help='merge all LAA mac into one')
    parser.add_argument('-z', '--zero', action='store_true', help='filter rssi value of 0')
    args = parser.parse_args()

    before = None
    after = None
    if args.after:
        after = parse_ts(args.after)
    if args.before:
        before = parse_ts(args.before)

    conn = sqlite3.connect(args.db)
    c = conn.cursor()
    sql, sql_args = build_sql_query(after, before, args.mac, args.rssi, args.zero, args.day)
    c.execute(sql, sql_args)

    if args.log:
        # simply output each log entry to stdout
        for row in c.fetchall():
            t = time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(row[0]))
            m = row[1]
            if is_local_bit_set(m):
                m = '%s (LAA)' % m
            print '\t'.join([t, m, row[2], row[3], str(row[4])])

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
    tmp = [(k,len(v['rssi'])) for k,v in macs.items()]
    tmp = reversed(sorted(tmp, key=lambda k:k[1]))

    # print our stats
    for k,_ in tmp:
        v = macs[k]
        laa = ' (LAA)' if is_local_bit_set(k) else ''
        print 'MAC: %s%s, VENDOR: %s' % (k, laa, v['vendor'])
        print '\tSSIDs: %s' % ','.join(sorted(v['ssid']))
        rssi = v['rssi']
        if rssi != []:
            print '\tRSSI: #: %d, min: %d, max: %d, avg: %d, median: %d' % (
                len(rssi), min(rssi), max(rssi), sum(rssi)/len(rssi), median(rssi))
        else:
            print '\tRSSI: Nothing found.'

        first = time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(v['first']))
        last = time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(v['last']))
        print '\tFirst seen at %s and last seen at %s' % (first, last)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
