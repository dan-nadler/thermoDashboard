from datetime import datetime, timedelta
import pandas as pd
import pytz
import numpy as np
from sqlalchemy.orm import sessionmaker
from models import Temperature, get_engine, Sensor, get_session, ActionLog, Action, Unit
from local_settings import LOCALTZ

localtz = pytz.timezone(LOCALTZ)

def get_dataframe(hours=24, user=1, zone=None):
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    q = session.query(Temperature.record_time, Temperature.location, (Temperature.value - Sensor.bias).label('value'))\
        .filter(Temperature.record_time >= pytz.utc.localize(datetime.now()).astimezone(localtz) - timedelta(hours=hours))\
        .join(Sensor).filter(Sensor.user==user)
    if zone is not None:
        q = q.filter(Sensor.zone == zone)

    df = pd.read_sql(q.statement, q.session.bind)
    session.close()

    df = df.reset_index().pivot_table(index='record_time', columns='location', values='value')
    return df

def get_plotting_dataframe(user, hours=6, resolution='60S', zone=None):
    df = get_dataframe(hours=hours, user=user, zone=zone).resample(resolution).median().ffill(limit=1).bfill()
    df[ np.abs( df.ffill() - df.ffill().rolling(5).median() ) > 5 ] = np.nan
    return df

def get_action_status(user):
    engine = get_engine()
    result = engine.execute(
        '''select record_time, value, target, unit.name as unit, action.name as name
from action, action_log, unit
where unit.user = {0}
and action.unit = unit.id
and action_log.action = action.id
and action_log.record_time >= (NOW() - INTERVAL 12 HOUR )
order by record_time desc
limit 1'''.format(user)
    )
    r = result.fetchall()

    return r