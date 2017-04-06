import json
import time
import os
import pprint
import mysql.connector
import nexmo
from app import app
from flask import render_template, request, render_template, jsonify


class MySQLCursorDict(mysql.connector.cursor.MySQLCursor):

    def fetchone(self):
        row = self._fetch_row()
        if row:
            return dict(zip(self.column_names, self._row_to_python(row)))
        return None


class Mdb:
    isLeaf = True
    con = False

    def __init__(self):
        print("DB INITIALIZED")
        self.__connect()

    def __connect(self):
        try:
            print("Connecting to database: %s" % "localhost")
            #self.con = MySQLdb.connect(host=self.config.get('mysql', 'host'), user=self.config.get('mysql', 'username'), passwd=self.config.get('mysql', 'password'), db=self.config.get('mysql', 'database'))
            self.con = mysql.connector.connect(host="127.0.0.1", user="root", passwd="", db="pypong")
            cur = self.con.cursor()
            cur.execute("SELECT VERSION()")
            ver = cur.fetchone()
            print("Database version : %s " % ver)

        except mysql.connector.Error, e:
            print("Error %d: %s" % (e.args[0], e.args[1]))

        print("Connected!")

        return self.con

    def ping(self):
        try:
            print("Pinging Database")
            if self.con.is_connected:
                self.con.ping()
            else:
                print("DB not connected!")
                self.__connect()
        except:
            print("Pinging Database has failed")
            self.__connect()


db = Mdb()
nexmo_client = nexmo.Client(
    key=os.environ.get('NEXMO_API_KEY'),
    secret=os.environ.get('NEXMO_API_SECRET'))


def sendNotification():
    print "send notification invoked"
    cur = db.con.cursor(cursor_class=MySQLCursorDict)
    try:
        cur.execute(
            "SELECT * FROM sms_request WHERE status=1 ORDER BY id LIMIT 1")
    except:
        print("DB operation failed")
        return "DB error"
    row = cur.fetchone()
    cur.close()
#   print("Returned::::::::::::::::::::: 2  %s" , pprint.pformat(row))
    db.con.commit()
    if row:
        print "sending text to " + str(row['msisdn'])
        print nexmo_client.send_message({'from': 'PyPong', 'to': str(row['msisdn']), 'text': 'Hello Neximo! The table is free and you are next in the queue. PyPong'})
        cur = db.con.cursor(cursor_class=MySQLCursorDict)
        cur.execute("DELETE FROM sms_request WHERE id = %d " % row['id'])
        row = cur.fetchone()
        cur.close()
        db.con.commit()
        time.sleep(2)
    return 0


@app.route('/')
@app.route('/index')
def index():
    d = parser()
    return render_template('index.html', data=d)


@app.route('/get_values')
def get_values():
    d = parser()
    return jsonify(d)


def parser():
    f_path = '/root/'
    f = os.path.join(f_path, 'ioppt.csv')

    INTERVAL_BETWEEN_BOUNCES = 1500
    NOISE_INTERVAL = 50
    INTERVAL_BETWEEN_STREAKS = 2000
    MINIMAL_LENGTH_OF_STREAK = 2

    hit_times = []
    try:
        for line in open(f).readlines():
            hit_times += [int(line.split(",")[1])]
    except:
        report = {}
        report["longest_streak"] = 0
        report["last_streak_speed"] = 0
        report["last_streak_length"] = 0
        report["fastest_streak"] = 0
        report["game_is_on"] = False

        print json.dumps(report)
        return report

    intervals = []
    p_hit_time = 0
    for hit_time in hit_times:
        intervals += [hit_time - p_hit_time]
        p_hit_time = hit_time

    last_streak_event = 0

    streaks = []
    streak = []
    for i in range(len(hit_times)):
        if intervals[i] < INTERVAL_BETWEEN_BOUNCES and intervals[i] > NOISE_INTERVAL:
            streak += [intervals[i]]
        else:
            if len(streak) > MINIMAL_LENGTH_OF_STREAK:
                last_streak_event = hit_times[i]
                streaks += [streak]
                # print streak
                streak = []
            else:
                streak = []
    millis = int(round(time.time() * 1000))
    if len(streak) > MINIMAL_LENGTH_OF_STREAK:
        streaks += [streak]
        last_streak_event = millis

    last_event_interval = millis - last_streak_event
    if last_event_interval < INTERVAL_BETWEEN_STREAKS:
        report_game_is_on = True
    else:
        report_game_is_on = False
        sendNotification()
    report_longest_streak = 0
    report_fastest_streak = 0
    for streak in streaks:
        avg_delay = reduce(lambda x, y: x + y, streak) / len(streak)
        hits_per_minute = 60000/avg_delay
        if hits_per_minute > report_fastest_streak:
            report_fastest_streak = hits_per_minute
        if len(streak) > report_longest_streak:
            report_longest_streak = len(streak)

    report_last_streak_length = len(streaks[-1])
    report_last_streak_speed = 60000 / \
        (reduce(lambda x, y: x + y, streaks[-1]) / len(streaks[-1]))

    report = {}
    report["longest_streak"] = report_longest_streak
    report["last_streak_speed"] = report_last_streak_speed
    report["last_streak_length"] = report_last_streak_length
    report["fastest_streak"] = report_fastest_streak
    report["game_is_on"] = report_game_is_on

    print json.dumps(report)
    return report


@app.route('/api/sms', methods=['POST', 'GET'])
def api():
    cur = db.con.cursor(cursor_class=MySQLCursorDict)
    print "isdn: ", request.form['msisdn']
    try:
        cur.execute("SELECT * FROM sms_request WHERE status=1 AND msisdn = '%s'" %
                    str(request.form['msisdn']))
    except:
        print("DB operation failed")
        return "DB error"
    row = cur.fetchone()
    cur.close()
    print("Returned::::::::::::::::::::: 1 %s" % pprint.pformat(row))
    db.con.commit()
    if not row:
        cur = db.con.cursor(cursor_class=MySQLCursorDict)
        cur.execute("INSERT INTO sms_request VALUES (null, '%s', '%s', now(), 1)" % (
            str(request.form['msisdn']),  str(request.form['keyword'])))
        cur.close()
        db.con.commit()
        print nexmo_client.send_message({'from': 'PyPong', 'to': str(request.form['msisdn']), 'text': 'Thank you for the SMS. We will let you know when the table is free. PyPong'})
    pprint.pprint(request.form)
    return "OK"
