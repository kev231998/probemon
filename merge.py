import sqlite3
import sys

if len(sys.argv) < 2:
    print 'Error: needs an argument'
    sys.exit(-1)

conn_in = sqlite3.connect(sys.argv[1])
c_in = conn_in.cursor()

conn_out = sqlite3.connect('probemon.db')
c_out = conn_out.cursor()

c_in.execute('select * from probemon')
for row in c_in.fetchall():
    time, mac, ssid, rssi = row

    c_in.execute('select address,vendor from mac where id = ?', (mac,))
    mac_add, vendor_id = c_in.fetchone()
    c_in.execute('select name from vendor where id = ?', (vendor_id,))
    vendor_name = c_in.fetchone()[0]
    c_out.execute('select id from vendor where name = ?', (vendor_name,))
    r = c_out.fetchone()
    if r is None:
        c_out.execute('insert into vendor (name) values (?)', (vendor_name,))
        c_out.execute('select id from vendor where name = ?', (vendor_name,))
        r = c_out.fetchone()
    vendor_id = r[0]

    c_out.execute('select id from mac where address = ?', (mac_add,))
    r = c_out.fetchone()
    if r is None:
        c_out.execute('insert into mac (address, vendor) values (?, ?)', (mac_add, vendor_id,))
        c_out.execute('select id from mac where address = ?', (mac_add,))
        r = c_out.fetchone()
    mac_id = r[0]

    c_in.execute('select name from ssid where id = ?' , (ssid,))
    ssid_name = c_in.fetchone()[0]
    c_out.execute('select id from ssid where name = ?', (ssid_name,))
    r = c_out.fetchone()
    if r is None:
        c_out.execute('insert into ssid (name) values (?)', (ssid_name,))
        c_out.execute('select id from ssid where name = ?', (ssid_name,))
        r = c_out.fetchone()
    ssid_id = r[0]

    c_out.execute('insert into probemon values (?, ?, ?, ?)', (time, mac_id, ssid_id, rssi))

conn_out.commit()

conn_out.close()
conn_in.close()
