#!/usr/bin/python2

from datetime import datetime
import time
from cycler import cycler
import matplotlib
#matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.patches as mpatches
import argparse
import sqlite3
import sys
import os.path
import re

NUMOFSECSINADAY = 60*60*24
# standard colors without red and gray
COLORS = ['tab:blue', 'tab:orange', 'tab:green', 'tab:purple',
    'tab:brown', 'tab:pink', 'tab:olive', 'tab:cyan']

# read config variable from config.py file
from config import *
MERGED = (m[:8] for m in MERGED)

# draws a rectangle as custom legend handler
class MyLine2DHandler(object):
    def legend_artist(self, legend, orig_handle, fontsize, handlebox):
        x0, y0 = handlebox.xdescent, handlebox.ydescent
        width, height = handlebox.width, handlebox.height
        patch = mpatches.Rectangle([x0, y0], width, height, facecolor=orig_handle.get_color())
        handlebox.add_artist(patch)
        return patch

def is_local_bit_set(mac):
    byte = mac.split(':')
    return int(byte[0], 16) & 0b00000010 == 0b00000010

parser = argparse.ArgumentParser(description='Plot MAC presence from probe requests in the database')
parser.add_argument('-b', '--db', default='probemon.db', help='file name of the db')
parser.add_argument('-i', '--image', default=None, const='plot.png', nargs='?', help='output an image')
parser.add_argument('-l', '--legend', action='store_true', default=False, help='add a legend')
parser.add_argument('--label', action='store_true', default=False, help='add a mac label for each plot')
parser.add_argument('-k', '--knownmac', action='append', help='known mac to highlight in red')
parser.add_argument('-M', '--min', type=int, default=3, help='minimum number of probe requests to consider')
parser.add_argument('-m', '--mac', action='append', help='only display that mac')
parser.add_argument('-p', '--privacy', action='store_true', default=False, help='merge LAA MAC address')
parser.add_argument('-r', '--rssi', type=int, default=-99, help='minimal value for RSSI')
parser.add_argument('-s', '--start', help='start timestamp')
parser.add_argument('--span-time', default='1d', help='span of time (coud be #d or ##h or ###m)')
parser.add_argument('-t', '--timestamp', action='store_true', help='add a timestamp to the top right of image')
args = parser.parse_args()

# parse span_time
span = args.span_time[-1:]
try:
    sp = int(args.span_time[:-1])
except ValueError:
    print 'Error: --span-time argument should be of the form [digit]...[d|h|m]'
    sys.exit(-1)
if span == 'd':
    args.span_time = sp*NUMOFSECSINADAY
elif span == 'h':
    args.span_time = sp*60*60
elif span == 'm':
    args.span_time = sp*60
else:
    print 'Error: --span-time postfix could only be d or h or m'
    sys.exit(-1)

if args.knownmac is not None:
    KNOWNMAC = args.knownmac

if not os.path.exists(args.db):
    print 'Error: file not found %s' % args.db
    sys.exit(-1)

# sqlite3
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
    end_time = start_time + args.span_time
else:
    #c.execute('select max(date) from probemon')
    #end_time = c.fetchone()[0]
    end_time = time.time()
    start_time = end_time - args.span_time

# keep only the data between 2 timestamps ignoring IGNORED macs with rssi
# greater than the min value
ts = {}
arg_list = ','.join(['?']*len(IGNORED))
sql = '''select date,mac.address,rssi from probemon
    inner join mac on mac.id=probemon.mac
    where date <= ? and date >= ?
    and mac.address not in (%s)
    and rssi > ?
    order by date''' % (arg_list,)
try:
    c.execute(sql, (end_time, start_time) + IGNORED + (args.rssi,))
except sqlite3.OperationalError as e:
    time.sleep(2)
    c.execute(sql, (end_time, start_time) + IGNORED + (args.rssi,))
for row in c.fetchall():
    if row[1] in ts:
        ts[row[1]].append(row[0])
    else:
        ts[row[1]] = [row[0]]
conn.close()

def match(m, s):
    # match on start of mac address and use % as wild-card like in SQL syntax
    if '%' in m:
        m = m.replace('%', '.*')
    else:
        m = m+'.*'
    m = '^'+m
    return re.search(m, s) is not None

macs = ts.keys()
if args.mac :
    # keep mac with args.mac as substring
    macs = [m for m in ts.keys() if any(match(am.lower(), m) for am in args.mac)]

# filter our data set based on min probe request or mac appearence
for k,v in ts.items():
    if (len(v) <= args.min and k not in KNOWNMAC) or k not in macs:
        del ts[k]

# sort the data on frequency of appearence
data = sorted(ts.items(), key=lambda x:len(x[1]))
data.reverse()
macs = [x for x,_ in data]
times = [x for _,x in data]

# merge all LAA mac into one plot for a virtual MAC called 'LAA'
if args.privacy:
    indx = [i for i,m in enumerate(macs) if is_local_bit_set(m)]
    if len(indx) > 0:
        t = []
        # merge all times for LAA macs
        for i in indx:
            t.extend(times[i])
        macs = [m for i,m in enumerate(macs) if i not in indx]
        times = [x for i,x in enumerate(times) if i not in indx]
        macs.append('LAA')
        times.append(sorted(t))

# merge all same vendor mac into one plot for a virtual MAC called 'OUI'
for mv in MERGED:
    indx = [i for i,m in enumerate(macs) if m[:8] == mv]
    if len(indx) > 0:
        t = []
        # merge all times for vendor macs
        for i in indx:
            t.extend(times[i])
        macs = [m for i,m in enumerate(macs) if i not in indx]
        times = [x for i,x in enumerate(times) if i not in indx]
        macs.append(mv)
        times.append(sorted(t))

if len(times) == 0 or len(macs) == 0:
    print 'Error: nothing to plot'
    sys.exit(-1)

# initialize plot
fig, ax = plt.subplots()
# change margin around axis to the border
fig.subplots_adjust(left=0.05, right=0.95, top=0.95, bottom=0.07)
# set our custom color cycler (without red and gray)
ax.set_prop_cycle(cycler('color', COLORS))

# calculate size of marker given the number of macs to display and convert from inch to point
markersize = (fig.get_figheight()/len(macs))*72
# set default line style for the plot
matplotlib.rc('lines', linestyle=':', linewidth=0.3, marker='|', markersize=markersize)
# plot
lines = []
for i,p in enumerate(times):
    # reverse order to get most frequent at top
    n = len(times)-i-1
    # constant value
    q = [n]*len(p)
    label = macs[i]
    if macs[i] in KNOWNMAC:
        line, = ax.plot(p, q, color='tab:red', label=label)
    elif macs[i] == 'LAA' or is_local_bit_set(macs[i]):
        if macs[i] != 'LAA':
            label = '%s (LAA)' % macs[i]
        line, = ax.plot(p, q, color='tab:gray', label=label)
    else:
        line, = ax.plot(p, q, label=label)
        if args.label:
            ax.text(end_time, q[-1], label, fontsize=8, color='black', horizontalalignment='right', verticalalignment='top', family='monospace')
    lines.append(line)

# add a grey background on period greater than 15 minutes without data
alltimes = []
for t in times:
   alltimes.extend(t)
alltimes.sort()
diff = [i for i,j in enumerate(zip(alltimes[:-1], alltimes[1:])) if (j[1]-j[0])>60*15]
for i in diff:
    ax.axvspan(alltimes[i], alltimes[i+1], facecolor='#bbbbbb', alpha=0.5)

# define helper function for labels and ticks
def showdate(tick, pos):
    return time.strftime('%Y-%m-%d', time.localtime(tick))
def showtime(tick, pos):
    return time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(tick))
def showhourminute(tick, pos):
    return time.strftime('%H:%M', time.localtime(tick))
def showhour(tick, pos):
    return time.strftime('%Hh', time.localtime(tick))
def showmac(tick, pos):
    try:
        m = macs[len(times)-int(round(tick))-1]
        if m != 'LAA' and is_local_bit_set(m):
            m = '%s (LAA)' % m
        return m
    except IndexError:
        pass

## customize the appearence of our figure/plot
# customize label of major/minor ticks
ax.xaxis.set_major_formatter(ticker.FuncFormatter(showdate))
if span == 'd':
    # show minor tick every hour
    ax.xaxis.set_minor_formatter(ticker.FuncFormatter(showhour))
    ax.xaxis.set_minor_locator(ticker.MultipleLocator(60*60))
elif span == 'h':
    # show minor tick every x minutes
    ax.xaxis.set_minor_formatter(ticker.FuncFormatter(showhourminute))
    h = args.span_time/3600
    sm = 10*60
    if h > 2:
        sm = 15*60
    if h > 6:
        sm = 30*60
    if h > 12:
        sm = 60*60
    ax.xaxis.set_minor_locator(ticker.MultipleLocator(sm))
elif span == 'm':
    # show minor tick every 5 minutes
    ax.xaxis.set_minor_formatter(ticker.FuncFormatter(showhourminute))
    ax.xaxis.set_minor_locator(ticker.MultipleLocator(5*60))

# show only integer evenly spaced on y axis
#ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True, steps=[1,2,4,5,10]))
# don't draw y axis
ax.yaxis.set_visible(False)
# move down major tick labels not to overwrite minor tick labels and do not show major ticks
ax.xaxis.set_tick_params(which='major', pad=15, length=0)
# customize the label shown on mouse over
ax.format_xdata = ticker.FuncFormatter(showtime)
ax.format_ydata = ticker.FuncFormatter(showmac)
# show vertical bars matching minor ticks
ax.grid(True, axis='x', which='minor')
# add a legend
if args.legend:
    # add a custom label handler to draw rectangle instead of default line style
    ax.legend(lines, macs, loc='lower left', ncol=len(macs)/30+1,
        handler_map={matplotlib.lines.Line2D: MyLine2DHandler()}, prop={'family':'monospace', 'size':8})
# avoid too much space around our data by defining set
space = 5*60 # 5 minutes
ax.set_xlim(start_time-space, end_time+space)
ax.set_ylim(-1, len(macs))
# add a timestamp to the image
if args.timestamp:
    fig.text(0.49, 0.97, time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(time.time())), fontsize=8, alpha=0.2)

# and tada !
if args.image:
    fig.set_size_inches(float(HEIGHT)/DPI, float(WIDTH)/DPI)
    fig.savefig(args.image, dpi=DPI)
    #fig.savefig('test.svg', format='svg')
else:
    plt.show()
