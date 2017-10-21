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

NUMOFSECSINADAY = 60*60*24
# standard colors without red and gray
COLORS = ['tab:blue', 'tab:orange', 'tab:green', 'tab:purple',
    'tab:brown', 'tab:pink', 'tab:olive', 'tab:cyan']

# draws a rectangle as custom legend handler
class MyLine2DHandler(object):
    def legend_artist(self, legend, orig_handle, fontsize, handlebox):
        x0, y0 = handlebox.xdescent, handlebox.ydescent
        width, height = handlebox.width, handlebox.height
        patch = mpatches.Rectangle([x0, y0], width, height, facecolor=orig_handle.get_color())
        handlebox.add_artist(patch)
        return patch

# read config variable from config.txt file
with open('config.txt') as f:
    exec('\n'.join(f.readlines()))

def is_local_bit_set(mac):
    fields = mac.split(':')
    return '{0:08b}'.format(int(fields[0], 16))[-2] == '1'

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
    end_time = start_time + NUMOFSECSINADAY*args.days
else:
    c.execute('select max(date) from probemon')
    end_time = c.fetchone()[0]
    start_time = end_time - NUMOFSECSINADAY*args.days

# keep only the data between 2 timestamps ignoring IGNORED macs with rssi
# greater than the min value
ts = {}
arg_list = ','.join(['?']*len(IGNORED))
sql = '''select date,mac.address,rssi from probemon
    inner join mac on mac.id=probemon.mac
    where date < ? and date > ?
    and mac.address not in (%s)
    and rssi > ?
    order by date''' % (arg_list,)
for row in c.execute(sql, (end_time, start_time) + IGNORED + (args.rssi,)):
    if row[1] in ts:
        ts[row[1]].append(row[0])
    else:
        ts[row[1]] = [row[0]]
conn.close()

macs = ts.keys()
if args.mac :
    # keep mac with args.mac as substring
    macs = [m for m in ts.keys() if any(am in m for am in args.mac)]

# filter our data set based on min probe request or mac appearence
for k,v in ts.items():
    if len(v) <= args.min or k not in macs:
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
ax.xaxis.set_minor_formatter(ticker.FuncFormatter(showhour))
# show minor tick every hour
ax.xaxis.set_minor_locator(ticker.MultipleLocator((args.days*24*60*60)/24))
# show only integer evenly spaced on y axis
#ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True, steps=[1,2,4,5,10]))
# don't draw y axis
ax.yaxis.set_visible(False)
# move down major tick labels not to overwrite minor tick labels
ax.xaxis.set_tick_params(which='major', pad=15)
# customize the label shown on mouse over
ax.format_xdata = ticker.FuncFormatter(showtime)
ax.format_ydata = ticker.FuncFormatter(showmac)
# show vertical bars matching minor ticks
ax.grid(True, axis='x', which='minor')
# add a legend
if args.legend:
    # add a custom label handler to draw rectangle instead of default line style
    ax.legend(lines, macs, fontsize=8, loc='lower left', ncol=len(macs)/30+1,
        handler_map={matplotlib.lines.Line2D: MyLine2DHandler()})
# avoid too much space around our data by defining set
space = 5*60 # 5 minutes
ax.set_xlim(start_time-space, end_time+space)
ax.set_ylim(-1, len(macs))

# and tada !
if args.image:
    fig.set_size_inches(float(HEIGHT)/DPI, float(WIDTH)/DPI)
    fig.savefig('plot.png', dpi=DPI)
    #fig.savefig('test.svg', format='svg')
else:
    plt.show()
