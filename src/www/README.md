# The app
`mapot.py` is a *flask* app that allows to serve in real time the stats and data collected by `probemon.py`.

The app excepts the database to be in the current directory. This can be easily changed by changing the path of it in the `DATABASE` variable in `mapot.py`.

Or use a symlink or hardlink towards the real db.

The app connects to the db read-only.

## Running the app
Even though it is possible to run it without any real webserver, this is not recommended, as per the documentation of **flask**.

If you want to do it anyway, simply run:

    python3 mapot.py

Howewer, using a real webserver is the way to go.

This could be done simply with *gunicorn* for example. That you could install with:

    pip3 install gunicorn

Then run it with:

    gunicorn -w 4 -b 127.0.0.1:5556 mapot:app

You can look at other **options** on how to run the *app* in [the flask documentation](http://flask.pocoo.org/docs/1.0/deploying/).

## The UI
The main UI is a time chart with the probe requests displayed for the last 24 hours.

![Flask app main UI](../../mapot-main-ui.png)

On mobile, a table is displayed instead.

You can choose another day in the datepicker, on the right.

Refresh is done automatically if you go back to the tab/window and the current selected day is today. Otherwise, you can force a refresh by using the 'Refresh' button.

By clicking on a mac in the legend on the left of the chart, one gets a popup with details about that particuliar mac:
- probed SSIDs(s) list
- RSSI values stats
- a RSSI chart value over time
- a complete probe requests log

![Popup over details](../../mapot-popup.png)
