import sqlite3
import urllib2
import argparse
import time
import sys

# for correct handling of encoding when piping to less
import codecs
import locale
sys.stdout = codecs.getwriter(locale.getpreferredencoding())(sys.stdout)

NUMOFSECSINADAY = 60*60*24

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

parser = argparse.ArgumentParser(description='Find RSSI stats for a given mac')
parser.add_argument('-a', '--after', help='filter before this timestamp')
parser.add_argument('-b', '--before', help='filter after this timestamp')
parser.add_argument('-r', '--rssi', type=int, help='filter for that minimal RSSI value')
parser.add_argument('-m', '--mac', help='filter for that mac address')
args = parser.parse_args()

banner = None

if args.after:
    after = parse_ts(args.after)

if args.before:
    before = parse_ts(args.before)

conn = sqlite3.connect('probemon.db')
c = conn.cursor()
if args.mac:
    if len(args.mac) != 17:
        mac = '%s%%' % args.mac
    else:
        mac = args.mac

    sql = '''select date,mac.address,vendor.name,ssid.name,rssi from probemon
    inner join mac on mac.id=probemon.mac
    inner join vendor on vendor.id=mac.vendor
    inner join ssid on ssid.id=probemon.ssid
    where mac.address like ? and rssi != 0
    order by date'''
    c.execute(sql, (mac,))
    if args.rssi is None:
        args.rssi = -99
elif args.rssi:
    sql = '''select date,mac.address,vendor.name,ssid.name,rssi from probemon
    inner join mac on mac.id=probemon.mac
    inner join vendor on vendor.id=mac.vendor
    inner join ssid on ssid.id=probemon.ssid
    where rssi>? and rssi != 0
    order by date'''
    c.execute(sql, (args.rssi,))
else:
    if args.after is None and args.before is None:
        # print the stats of the day
        before = time.time() # now
        after = before - NUMOFSECSINADAY # since one day in the past
        banner = '== Stats of the day =='
    sql = '''select date,mac.address,vendor.name,ssid.name,rssi from probemon
    inner join mac on mac.id=probemon.mac
    inner join vendor on vendor.id=mac.vendor
    inner join ssid on ssid.id=probemon.ssid
    where rssi != 0
    order by date'''
    c.execute(sql)

macs = {}
for row in c.fetchall():
    if args.after and row[0] < after:
        continue
    if args.before and row[0] > before:
        continue
    mac = row[1]
    if is_local_bit_set(mac):
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
    if row[4] > args.rssi:
        d['rssi'].append(row[4])

conn.close()

# sort on frequency
tmp = [(k,len(v['rssi'])) for k,v in macs.items()]
tmp = reversed(sorted(tmp, key=lambda k:k[1]))

if banner is not None:
    print banner
for k,_ in tmp:
    v = macs[k]
    print 'MAC: %s, VENDOR: %s, SSIDs: %s' % (k, v['vendor'].decode('utf-8'), ','.join(v['ssid']))
    rssi = v['rssi']
    if rssi != []:
        print '\tRSSI: #: %d, min: %d, max: %d, avg: %d, median: %d' % (
            len(rssi), min(rssi), max(rssi), sum(rssi)/len(rssi), median(rssi))
    else:
        print '\tRSSI: Nothing found.'

    first = time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(v['first']))
    last = time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(v['last']))
    print '\tFirst seen on: %s and last seen on: %s' % (first, last)
