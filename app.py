from analysis import get_plotting_dataframe, get_dataframe
from models import *
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import time
import pytz
from flask import Flask, render_template

localtz = pytz.timezone('America/New_York')

class Cache(object):
    def __init__(self, cache_duration_seconds=60):
        """
        :param lookback:
        :param cache_duration_seconds: duration of cached in seconds
        """
        self.cache_duration = cache_duration_seconds
        self.last_retrieval = pytz.utc.localize(datetime.now()).astimezone(localtz)  - timedelta(days=1000)
        self.df = None

    def data(self, *args, **kwargs):
        cache_duration = self.cache_duration
        if (pytz.utc.localize(datetime.now()).astimezone(localtz)  - self.last_retrieval) > timedelta(seconds=cache_duration):
            self.last_retrieval = pytz.utc.localize(datetime.now()).astimezone(localtz)
            self.df = self._get_data(*args, **kwargs)
        return self.df

    def _get_data(self):
        pass


class RawDataFrame(Cache):
    def __init__(self, *args, **kwargs):
        super(RawDataFrame, self).__init__(*args, **kwargs)

    def _get_data(self, lookback=3):
        return get_dataframe(lookback)


class PlotDataFrame(Cache):
    def __init__(self, *args, **kwargs):
        super(PlotDataFrame, self).__init__(*args, **kwargs)

    def _get_data(self, lookback=3):
        return get_plotting_dataframe(hours=lookback)


class RecentTemperature(Cache):
    def __init__(self, *args, **kwargs):
        super(RecentTemperature, self).__init__(*args, **kwargs)

    def _get_data(self):
        df = get_plotting_dataframe(hours=3, resolution='10S')
        df = df.dropna().resample('60S').last()
        return df


data = RawDataFrame()
chart_data = PlotDataFrame()
last_data = RecentTemperature(cache_duration_seconds=10)

app = Flask(__name__)


def current_temp_chart(chartID, chart_height, chart_type):
    data1 = last_data.data().ix[-1, :].fillna(0)
    data2 = last_data.data().ix[0, :].fillna(0)
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


def temp_history_chart(chartID, chart_height):
    data = chart_data.data(lookback=24).dropna()
    localtz = pytz.timezone('America/New_York')
    utctz = pytz.timezone('UTC')
    chart = {
        "renderTo": chartID,
        "type": 'line',
        "height": chart_height,
        "width": 650,
        "zoomType": 'x'
    }

    localize = lambda t: utctz.localize(t).astimezone(localtz).timetuple()

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
    charts = []

    charts.append(
        current_temp_chart('Current', chart_height, 'bar')
    )

    charts.append(
        temp_history_chart('History', chart_height)
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