from datetime import datetime
import time
from cycler import cycler
#import matplotlib
#matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import argparse
import sqlite3
import sys

NUMOFSECSINADAY = 60*60*24

# read config variable from config.txt file
with open('config.txt') as f:
    exec('\n'.join(f.readlines()))

def is_local_bit_set(mac):
    fields = mac.split(':')
    if '{0:08b}'.format(int(fields[0], 16))[-2] == '1':
    	return True
    return False

parser = argparse.ArgumentParser(description='Plot MAC presence from probe request sniff')
parser.add_argument('-b', '--db', default='probemon.db', help='file name of the db')
parser.add_argument('-d', '--days', type=int, default=1, help='number of days to keep')
parser.add_argument('-i', '--image', action='store_true', default=False, help='output an image')
parser.add_argument('-l', '--legend', action='store_true', default=False, help='add a legend')
parser.add_argument('-k', '--knownmac', action='append', help='known mac to highlight in red')
parser.add_argument('-m', '--min', type=int, default=3, help='minimum number of probe requests to consider')
parser.add_argument('-M', '--mac', action='append', help='only display that mac')
parser.add_argument('-p', '--privacy', action='store_true', default=False, help='merge LAA MAC address')
parser.add_argument('-r', '--rssi', type=int, default=-99, help='minimal value for RSSI')
parser.add_argument('-s', '--start', help='start timestamp')
args = parser.parse_args()

if args.knownmac is not None:
    KNOWNMAC = args.knownmac

# slite3
conn = sqlite3.connect(args.db)
c = conn.cursor()

if args.start:
    try:
        start_time = time.mktime(time.strptime(args.start, '%Y-%m-%dT%H:%M'))
    except  ValueError:
        try:
            date = time.strptime(args.start, '%Y-%m-%d')
            date = time.strptime('%sT12:00' % args.start, '%Y-%m-%dT%H:%M')
            start_time = time.mktime(date)
        except ValueError:
            print "Error: can't parse date timestamp"
            conn.close()
            sys.exit(-1)
    end_time = start_time + NUMOFSECSINADAY*args.days
else:
    c.execute('select max(date) from probemon')
    end_time = c.fetchone()[0]
    start_time = end_time - NUMOFSECSINADAY*args.days

# keep only the data between 2 timestamps ignoring IGNORED macs with rssi
# greater than the min value
time_list = []
mac_list = []
arg_list = ','.join(['?']*len(IGNORED))
sql = '''select date,mac.address,rssi from probemon
    inner join mac on mac.id=probemon.mac
    where date < ? and date > ?
    and mac.address not in (%s)
    and rssi > ?
    order by date''' % (arg_list,)
for row in c.execute(sql, (end_time, start_time) + IGNORED + (args.rssi,)):
    time_list.append(row[0])
    mac_list.append(row[1])
conn.close()

if args.mac :
    macs = args.mac
else:
    macs = list(set(mac_list))

data = []
# transform data to keep log datetime for each mac
for m in macs:
    times = [time_list[i] for i,x in enumerate(mac_list) if x == m]
    if len(times) > args.min:
        data.append((m,times))

# sort the data on frequency of appearence
data = sorted(data, key=lambda x:len(x[1]))
macs = [x for x,_ in data]
times = [x for _,x in data]

# merge all LAA mac into one plot for a virtual MAC called 'LAA'
if args.privacy:
    indx = [i for i,x in enumerate(map(is_local_bit_set, macs)) if x]
    t = []
    for i in indx:
        t.extend(times[i])
    macs = [m for i,m in enumerate(macs) if i not in indx]
    times = [x for i,x in enumerate(times) if i not in indx]
    macs.append('LAA')
    times.append(t)

# initialize plot
fig, ax = plt.subplots()
# change margin around axis to the border
fig.subplots_adjust(left=0.05, right=0.95, top=0.95, bottom=0.07)
# set our custom color cycler (without red and gray)
ax.set_prop_cycle(cycler('color',
    ['tab:blue', 'tab:orange', 'tab:green', 'tab:purple',
    'tab:brown', 'tab:pink', 'tab:olive', 'tab:cyan']))

# calculate size of marker given the number of macs to display and convert from inch to point
markersize = (fig.get_figheight()/len(macs))*72
# plot
for i,p in enumerate(times):
    if macs[i] in KNOWNMAC:
        ax.plot(p, [i]*len(p), linestyle='', marker='|', markersize=markersize, color='tab:red', label=macs[i])
    elif macs[i] == 'LAA' or is_local_bit_set(macs[i]):
        ax.plot(p, [i]*len(p), linestyle='', marker='|', markersize=markersize, color='tab:gray', label=macs[i])
    else:
        ax.plot(p, [i]*len(p), linestyle='', marker='|', markersize=markersize, label=macs[i])

# define helper function for labels and ticks
def showdate(tick, pos):
    return time.strftime('%Y-%m-%d', time.localtime(tick))
def showtime(tick, pos):
    return time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(tick))
def showhour(tick, pos):
    return time.strftime('%Hh', time.localtime(tick))
def showmac(tick, pos):
    try:
        return macs[int(round(tick))]
    except IndexError:
        pass

# customize the appearence of our figure/plot
ax.xaxis.set_major_formatter(ticker.FuncFormatter(showdate))
ax.xaxis.set_minor_formatter(ticker.FuncFormatter(showhour))
# show minor tick every hour
ax.xaxis.set_minor_locator(ticker.MultipleLocator((args.days*24*60*60)/24))
# show only integer evenly spaced on y axis
ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True, steps=[1,2,4,5,10]))
# move down major tick labels not to overwrite minor tick labels
ax.xaxis.set_tick_params(which='major', pad=15)
# customize the label shown on mouse over
ax.format_xdata = ticker.FuncFormatter(showtime)
ax.format_ydata = ticker.FuncFormatter(showmac)
# show a grid of vertical bar matching minor ticks
ax.grid(True, axis='x', which='minor')
# add a legend
if args.legend:
    ax.legend()
# avoid space around our data
plt.xlim(start_time-5*60, end_time+5*60)
plt.ylim(-1, len(macs))

# and tada !
if args.image:
    height = 1366 # in pixels
    width = 768 # in pxiels
    fig.set_size_inches(float(height)/100, float(width)/100)
    fig.savefig('plot.png', dpi=100)
    #fig.savefig('test.svg', format='svg')
else:
    plt.show()
