from analysis import get_plotting_dataframe, get_dataframe
from models import *
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import time
import pytz
from flask import Flask, render_template, request
from local_settings import LOCALTZ

localtz = pytz.timezone(LOCALTZ)

class Cache(object):
    def __init__(self, cache_duration_seconds=60):
        """
        :param cache_duration_seconds: duration of cached in seconds
        """
        self.cache_duration = cache_duration_seconds
        self.last_retrieval = pytz.utc.localize(datetime.now()).astimezone(localtz)  - timedelta(days=1000)
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

    def _get_data(self, lookback=3,**kwargs):
        return get_dataframe(lookback)


class PlotDataFrame(Cache):
    def __init__(self, *args, **kwargs):
        super(PlotDataFrame, self).__init__(*args, **kwargs)

    def _get_data(self, lookback=3, **kwargs):
        return get_plotting_dataframe(hours=lookback)


class RecentTemperature(Cache):
    def __init__(self, *args, **kwargs):
        super(RecentTemperature, self).__init__(*args, **kwargs)

    def _get_data(self, **kwargs):
        df = get_plotting_dataframe(hours=3, resolution='60S')
        df = df.resample('60S').last()
        return df


data = RawDataFrame()
chart_data = PlotDataFrame()
last_data = RecentTemperature(cache_duration_seconds=0)

app = Flask(__name__, static_folder='/static')


def current_temp_chart(chartID, chart_height, chart_type):
    temp = last_data.data()
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


def temp_history_chart(chartID, chart_height, lookback):

    data = chart_data.data(lookback=lookback, force_refresh=True).ffill()

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


@app.route('/')
@app.route('/index')
def index(chart_height=400):
    lookback = int(request.args.get('lookback', default=24))

    charts = []

    charts.append(
        current_temp_chart('Current', chart_height, 'bar')
    )

    charts.append(
        temp_history_chart('History', chart_height, lookback)
    )

    return render_template('index.html', charts=charts)


@app.route('/raw')
def raw():
    return data.data().to_html()


@app.route('/chart-data/')
def plot():
    return chart_data.data().to_html()


@app.route('/last-data')
def last():
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
