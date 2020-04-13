*all your probe requests belong to us*

# probemon
probemon is a simple command line tool for logging data from 802.11 probe request frames with tools to plot mac presence over time and get statistics.

This rewritten version of probemon uses an sqlite3 DB like in *probeSniffer*, as the log can quickly grow over time. It does not hop on channels as you lose more traffic by hopping than by simply staying on a major channel (like 1, 6, 11).

This simple python script uses under the hood *scapy*.
A script called *plot.py* using *matplotlib* allows you to draw a chart to easily visualize the mac addresses presence.
Another tool presents statistics about the mac addresses present in the database; it is just a helper script to query the database.

There is also a **flask app** to serve charts/plots and stats of the sqlite3 db. Use a real webserver like *gunicorn* or whatever you like. Look at [your deployement options](http://flask.pocoo.org/docs/1.0/deploying/#self-hosted-options) to find how to serve the app with a webserver.

The dependencies are:
* for probemon.py: scapy, manuf-ng, lru-dict
NOTE: Will need to replace regular manuf.py with modified one found in repository due to anti botting measures

* for stats.py: None
* for plot.py: matplotlib, cycler
* for mapot.py: flask, flask-caching

## probemon.py
You must enable monitor mode on your interface before running `probemon.py`. You can use, for example, `airmon-ng start wlan0` where wlan0 is your interface name. Now, use *wlan0mon* with `probemon.py`.

```
usage: probemon.py [-h] [-c CHANNEL] [-d DB] [-i INTERFACE] [-I IGNORE] [-s]
                   [-v]

a command line tool for logging 802.11 probe request

optional arguments:
  -h, --help            show this help message and exit
  -c CHANNEL, --channel CHANNEL
                        the channel to listen on
  -d DB, --db DB        database file name to use
  -i INTERFACE, --interface INTERFACE
                        the capture interface to use
  -I IGNORE, --ignore IGNORE
                        mac address to ignore
  -s, --stdout          also log probe request to stdout
  -v, --version         show version and exit
```

### Note about non utf-8 SSID
For SSID that we can't decode in utf-8, we can't store them as is in the db. So we encode them in base64 and store prepended with `b64_`.


## mapot.py
A flask *app* to serve in real time the probe requests stats and charts.

### How to run it ?
You can serve the *app* with a webserver like *gunicorn*.
For example:

    gunicorn -w 4 -b 127.0.0.1:4000 mapot:app


More details in the *README.md* in `src/www`

## plot script
This script simplifies the analysis of the recorded data by drawing a chart that plots the presence of
mac addresses via the recorded probe request.

```
usage: plot.py [-h] [-b DB] [-c] [-i [IMAGE]] [-l] [--label] [-k KNOWNMAC]
               [-M MIN] [-m MAC] [-p] [--pcap PCAP] [-r RSSI] [-s START]
               [--span-time SPAN_TIME] [-t [TITLE]] [-v]

Plot MAC presence from probe requests in the database

optional arguments:
  -h, --help            show this help message and exit
  -b DB, --db DB        file name of the db
  -c, --continuous      continously update the plot/image (every minute)
  -i [IMAGE], --image [IMAGE]
                        output an image
  -l, --legend          add a legend
  --label               add a mac label for each plot
  -k KNOWNMAC, --knownmac KNOWNMAC
                        known mac to highlight in red
  -M MIN, --min MIN     minimum number of probe requests to consider
  -m MAC, --mac MAC     only display that mac
  -p, --privacy         merge LAA MAC address
  --pcap PCAP           pcap file to process instead of the db
  --kismet KISMET       kismet db file to process instead of the db
  --only-pr             when processing pcap file/kismet db, keep only probe requests
  -r RSSI, --rssi RSSI  minimal value for RSSI
  -s START, --start START
                        start timestamp
  --span-time SPAN_TIME
                        span of time (coud be #d or ##h or ###m)
  -t [TITLE], --title [TITLE]
                        add a title to the top of image (if none specified,
                        use a timestamp)
  -v, --verbose         be verbose
```

* `-d/--days` specify the number of days that will lapse the chart from 00:00 to 00:00.
* `-k/--knowmac` (can be repeated) to specify known mac address that will be colored in red (overwrite mac in config.py).
* `-p/--privacy` switch merges all Locally Administered Addresses (MAC) into a single plot. Whether this option is used or not, they are colored in grey.
* `-m/--min` allows specifying the minimum of probe requests that are needed to be displayed on the chart.
* `-r/--rssi` allows filtering probe request based their RSSI value
* `-s/--start` allows to specify a date (%Y-%m-%d) or a timestamp (without seconds) (%Y-%m-%dT%H:%M) where to begin to draw the chart

You can produce a similar timeline chart from either a *pcap* file or a *kismet* db file:
* use `--pcap` to specify a pcap file to process. Every packet is taken into account; but scapy is rather slow to process all the packets. So if you are only interested in probe requests, add `--only-pr` to keep only probe requests, the process will be faster.
* use `--kismet` to process a *new* kismet db file. By default, all the activity of each wifi mac addresses/devices is used, except AP. If you want only probe requests, use `--only-pr`. This time, using that last option will be slow. If you want only probe requests, to speed things up, you can use `kismet_log_to_pcap` (from python-kismetdb) to convert to a pcap file and then use `--pcap` with `--only-pr` instead.

![Image of chart plotted with plot.py](screenshots/example.png)
When displayed by the script, one can hover the mouse on the plot to get the mac address, and the timestamp.
When you export to an image, you lose that feature but you can add a legend instead.

### Continuous mode
You can specify the `-c/--continuous` switch to enable an automatic continuous generation of plot. (Currently only working with image)
In one shell, run `./plot.py -i test.png`. Then open test.png in an image viewer, that auto-refresh the image automatically. The image will be updated/regenerated every minute.

## stats script
It allows you to request the database about a specific mac address and get statistics about it,
or filter based on a RSSI value. You can also specify the start time and end time of your request.
```
usage: stats.py [-h] [-a AFTER] [-b BEFORE] [-d] [--day-by-day] [--db DB]
                [--list-mac-ssids] [-l] [-m MAC] [-p] [-r RSSI] [-s SSID] [-z]

Display various stats about mac addresses/probe requests in the database

optional arguments:
  -h, --help            show this help message and exit
  -a AFTER, --after AFTER
                        filter before this timestamp
  -b BEFORE, --before BEFORE
                        filter after this timestamp
  -d, --day             filter only for the past day
  --day-by-day          day by day stats for given mac
  --db DB               file name of database
  --list-mac-ssids      list ssid with mac that probed for it
  -l, --log             log all entries instead of showing stats
  -m MAC, --mac MAC     filter for that mac address
  -p, --privacy         merge all LAA mac into one
  -r RSSI, --rssi RSSI  filter for that minimal RSSI value
  -s SSID, --ssid SSID  look up for mac that have probed for that ssid
  -z, --zero            filter rssi value of 0
```

## Locally Administered Addresses

> A locally administered address is assigned to a device by a network administrator, overriding the burned-in address.

> Universally administered and locally administered addresses are distinguished by setting the second-least-significant bit of the first octet of the address. This bit is also referred to as the U/L bit, short for Universal/Local, which identifies how the address is administered.
(source Wikipedia)

These type of MAC addresses are used by recent various OS/wifi stack to send probe requests anonymously, and using at the same time randomization.

So it defeats tracking and render probemon useless in that case. But not all devices are using this randomization technique, yet.

## Device behavior
It should be noted that not all devices are equal. They vary a lot in behavior regarding of the probe requests (PR). This should be taken into account when analyzing the data collected.

Depending on the type of device (PC/laptop/..., printer, mobile phone/tablet, IoT device), the OS used (Linux, Windows, Android, MacOS/iOS, unknown embedded OS, ...) the wifi chipset and/or the wifi/network stack, one device behave differently from one another when sending probe request.

Even phone using the same OS like android, can behave differently: some send PR every 30 seconds, while others only send PR when the screen is unlocked.

# Legality

I am not a lawyer and I can't give you any advice regarding the law.
But it might not be legal to collect and store probe requests in your country.

Even simply listening to probe requests might not be legal. For example, given the interpretation of *Section 18 U.S. Code § 2511*, it might not be legal to intercept the MAC addresses of devices in a network (?) or in the vicinity (?) in the U.S.A.

In Europe, if you are operating as a business, storing MAC addresses, which are considered private data, might be subject to the *GDPR*.

This is only straching the surface of the legality or illegality of this software.

Use with caution.
