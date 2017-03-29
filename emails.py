import smtplib
from email.mime.text import MIMEText
from models import *
from datetime import datetime, timedelta
import pytz
from local_settings import LOCALTZ, EMAIL
import pandas as pd

localtz = pytz.timezone(LOCALTZ)


def check_temps(user):
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    q = session.query(Temperature.record_time, Temperature.location, (Temperature.value - Sensor.bias).label('value'), Sensor.warning_level) \
        .filter(Temperature.record_time >= pytz.utc.localize(datetime.now()).astimezone(localtz) - timedelta(minutes=5)) \
        .join(Sensor) \
        .filter(Sensor.user == user) \
        .filter(Sensor.warning_level is not None)

    df = pd.read_sql(q.statement, q.session.bind)
    session.close()

    df1 = df.reset_index().pivot_table(index='record_time', columns='location', values='value').median(axis=0)
    df2 = df.reset_index().pivot_table(index='record_time', columns='location', values='warning_level').min(axis=0)

    return df1, df2


def send_email(to, warnings):
    from_addr = EMAIL['USERNAME']
    password = EMAIL['PASSWORD']

    text = ''
    for k, v in warnings.iteritems():
        text += '{0}: {1}\n'.format(k, round(v, 2))

    msg = MIMEText(text)
    msg['Subject'] = "thermoPi Warning"
    msg['From'] = from_addr
    msg['To'] = to

    server = smtplib.SMTP('smtp.gmail.com:587')
    server.starttls()
    server.login(from_addr, password)
    server.sendmail(from_addr, to, msg.as_string())
    server.quit()


def main():
    session = get_session()
    results = session.query(User).all()
    for user in results:
        if user.email is not None:
            temps, warn_lvl = check_temps(user.id)
            warnings = temps[temps < warn_lvl]
            if len(warnings) > 0:
                print('Sending email to {0}'.format(user.email))
                send_email(user.email, {k: v for k, v in warnings.iteritems()})


if __name__ == '__main__':
    main()
