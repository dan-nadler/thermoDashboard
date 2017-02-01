from datetime import datetime, timedelta
import pandas as pd
import pytz
import time
from sqlalchemy.orm import sessionmaker
from models import Temperature, get_engine, Sensor

localtz = pytz.timezone('America/New_York')

def get_dataframe(hours=24, user=1):
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    q = session.query(Temperature)\
        .filter(Temperature.record_time >= pytz.utc.localize(datetime.now()).astimezone(localtz) - timedelta(hours=hours))\
        .join(Sensor).filter(Sensor.user==user)

    df = pd.read_sql(q.statement, q.session.bind)

    df = df.reset_index().pivot_table(index='record_time', columns='location', values='value')
    return df


def get_plotting_dataframe(hours=24, user=1, resolution='60S', interpolation='linear'):
    df = get_dataframe(hours=hours, user=user)

    while (df.ffill().diff().abs() > 5).sum().sum() > 0:
        df[df.ffill().diff().abs() > 5] = pd.np.nan
    df['Dining Room (North Wall)'] = df['Dining Room (North Wall)'].dropna()
    df['Living Room (South Wall)'] = df['Living Room (South Wall)'].dropna()

    df2 = df.resample(resolution).mean().interpolate(interpolation)
    return df2
