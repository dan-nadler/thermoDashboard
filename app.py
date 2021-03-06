from analysis import get_plotting_dataframe, get_dataframe, get_action_status
from models import *
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import time
import pytz
from flask import Flask, render_template, request
from local_settings import LOCALTZ
from api import set_constant_temperature

localtz = pytz.timezone(LOCALTZ)


class Cache(object):
    def __init__(self, cache_duration_seconds=60):
        """
        :param cache_duration_seconds: duration of cached in seconds
        """
        self.cache_duration = cache_duration_seconds
        self.last_retrieval = pytz.utc.localize(datetime.now()).astimezone(localtz) - timedelta(days=1000)
        self.df = None

    def data(self, *args, **kwargs):
        force_refresh = kwargs.get('force_refresh', False)
        cache_duration = self.cache_duration

        if force_refresh:
            refresh = True
        elif (pytz.utc.localize(datetime.now()).astimezone(localtz) - self.last_retrieval) > timedelta(seconds=cache_duration):
            refresh = True
        else:
            refresh = False

        if refresh:
            self.last_retrieval = pytz.utc.localize(datetime.now()).astimezone(localtz)
            self.df = self._get_data(*args, **kwargs)
        return self.df

    def _get_data(self, **kwargs):
        pass


class RawDataFrame(Cache):
    def __init__(self, *args, **kwargs):
        super(RawDataFrame, self).__init__(*args, **kwargs)

    def _get_data(self, lookback=3, **kwargs):
        return get_dataframe(lookback)


class PlotDataFrame(Cache):
    def __init__(self, *args, **kwargs):
        super(PlotDataFrame, self).__init__(*args, **kwargs)

    def _get_data(self, lookback=3, **kwargs):
        return get_plotting_dataframe(user=kwargs.get('user', None), hours=lookback, zone=kwargs.get('zone', None))


class RecentTemperature(Cache):
    def __init__(self, *args, **kwargs):
        super(RecentTemperature, self).__init__(*args, **kwargs)

    def _get_data(self, **kwargs):
        df = get_plotting_dataframe(user=kwargs.get('user', None), hours=3, resolution='60S',
                                    zone=kwargs.get('zone', None))
        df = df.resample('60S').last()
        return df


data = RawDataFrame()
chart_data = PlotDataFrame()
last_data = RecentTemperature(cache_duration_seconds=5)

app = Flask(__name__, static_folder='/static')


def current_temp_chart(chartID, chart_height, chart_type, user, zone=None):
    temp = last_data.data(zone=zone, user=user)
    data1 = temp.ix[-1, :].fillna(0)
    data2 = temp.ix[0, :].fillna(0)
    chart = {
        "renderTo": chartID,
        "type": chart_type,
        "height": chart_height,
        "width": 650
    }
    series = [
        {
            "name": str(data1.name),
            "data": list(data1.values),
            "dataLabels":
                {
                    'enabled': 'true',
                    'allowOverlap': 'true',
                    'format': '{point.y:.1f}',
                    'style': {
                        'fontSize': '8px',
                    }
                }
        },
        {
            "name": str(data2.name),
            "data": list(data2.values),
            "dataLabels":
                {
                    'enabled': 'true',
                    'allowOverlap': 'true',
                    'format': '{point.y:.1f}',
                    'color': '#777777',
                    'style': {
                        'fontSize': '8px',
                    }
                }
        },
    ]
    title = {"text": 'Current Temperature'}
    xAxis = {
        "categories": list(data1.index),
        "labels": {
            "enabled": "false"
        }
    }
    yAxis = {
        "title": {
            "text": 'Degrees Fahrenheit'
        },
        "labels": {
            "enabled": "false"
        }

    }
    chart = {
        'chartID': chartID,
        'chart': chart,
        'series': series,
        'title': title,
        'xAxis': xAxis,
        'yAxis': yAxis,
    }

    return chart


def temp_history_chart(chartID, chart_height, lookback, user, zone=None):

    data = chart_data.data(lookback=lookback, force_refresh=True, zone=zone, user=user).ffill()

    localtz = pytz.timezone('America/New_York')
    utctz = pytz.timezone('UTC')

    chart = {
        "renderTo": chartID,
        "type": 'line',
        "height": chart_height,
        "width": 650,
        "zoomType": 'x'
    }

    localize = lambda t: t.timetuple() #pytz.utc.localize(t).astimezone(localtz).timetuple()

    series = [
        {
            "name": str(d[1].name),
            "yAxis": 1 if d[1].name == 'Outside (Street)' else 0,
            # "type": 'line' if d[1].name == 'Outside (Street)' else 'line',
            "zIndex": 0 if d[1].name == 'Outside (Street)' else 1,
            "data": [[time.mktime(a) * 1000, b] for a, b in zip([localize(t) for t in d[1].index], d[1].values)],
        } for d in data.iteritems()
        ]
    title = {"text": 'Historical Temperature'}
    xAxis = {
        "type": 'datetime',
    }
    yAxis = [
        {
            "title": {
                "text": 'Degrees Fahrenheit'
            }
        },
        {
            "title": {
                "text": 'Exterior Temperature'
            },
            "opposite": "true"
        }
    ]
    chart = {
        'chartID': chartID,
        'chart': chart,
        'series': series,
        'title': title,
        'xAxis': xAxis,
        'yAxis': yAxis,
    }
    return chart


def action_status(user):
    last_action = get_action_status(user)
    status_list = []
    for action in last_action:
        status = 'on' if action.value == 1 else 'off'
        time = action.record_time.strftime('%m/%d/%Y %H:%M:%S')
        status_list.append(('{0} {1}: is {2} as of {3}.'.format(action.unit, action.name.title(), status, time)))
    return status_list


def check_api_key(user, key):
    session = get_session()
    results = session.query(User).filter(User.id==user).all()[0]
    session.close()

    if results.api_key == key:
        return
    else:
        raise Exception('Invalid API Key')

@app.route('/')
@app.route('/index')
def index(chart_height=400):
    lookback = int(request.args.get('lookback', default=24))
    zone = request.args.get('zone', default=None)
    user = request.args.get('user')
    api_key = request.args.get('key')
    check_api_key(user, api_key)

    if zone is not None:
        zone = int(zone)

    charts = []

    charts.append(
        current_temp_chart('Current', chart_height, 'bar', user, zone=zone)
    )

    charts.append(
        temp_history_chart('History', chart_height, lookback, user, zone=zone)
    )

    status = action_status(user)

    return render_template('index.html', charts=charts, status=status)


@app.route('/set')
def set_temperature():
    user = request.args.get('user')
    key = request.args.get('key')
    check_api_key(user, key)

    zone = request.args.get('zone')
    target = request.args.get('temperature')
    hours = request.args.get('hours')
    expiration = datetime.now() + timedelta(hours=int(hours))

    set_constant_temperature(user, zone, target, expiration)
    return render_template('index.html', status='New temperature set.')


@app.route('/raw')
def raw():
    user = request.args.get('user')
    api_key = request.args.get('key')
    check_api_key(user, api_key)
    return data.data().to_html()


@app.route('/chart-data/')
def plot():
    user = request.args.get('user')
    api_key = request.args.get('key')
    check_api_key(user, api_key)
    return chart_data.data().to_html()


@app.route('/last-data')
def last():
    user = request.args.get('user')
    api_key = request.args.get('key')
    check_api_key(user, api_key)
    return last_data.data().to_frame().to_html()


@app.route('/test')
def test():
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    q = session.query(Temperature).filter(Temperature.record_time >= pytz.utc.localize(datetime.now()).astimezone(localtz)  - timedelta(hours=1))
    return ','.join([str(i.value) for i in q])

@app.route('/date')
def date():
    return str( pytz.utc.localize(datetime.now()).astimezone(localtz)  )

if __name__ == '__main__':
    app.run(debug=True)
