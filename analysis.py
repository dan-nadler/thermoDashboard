from datetime import datetime, timedelta
import pandas as pd
import pytz
import numpy as np
from sqlalchemy.orm import sessionmaker
from models import Temperature, get_engine, Sensor
from local_settings import LOCALTZ

localtz = pytz.timezone(LOCALTZ)

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

def get_plotting_dataframe(hours=24, user=1, resolution='60S'):
    df = get_dataframe(hours=hours, user=user).resample(resolution).median().ffill(limit=1)
    df[ np.abs( df.ffill() - df.ffill().rolling(5).median() ) > 5 ] = np.nan
    return df
