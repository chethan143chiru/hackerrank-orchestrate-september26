import csv
from datetime import datetime, timedelta
from collections import defaultdict

IMAGE_AMOUNTS = {
    'event_253': 4365000.0,
    'event_1442': 100000.0,
    'event_1545': 41272.0,
    'event_1700': 2854.0,
    'event_1786': 704.05,
    'event_3051': 1995.0,
    'event_3231': 8528.0,
    'event_4535': 15339.0,
    'event_5170': 723.0,
    'event_6033': 79679.26,
    'event_6859': 3650.0,
    'event_7307': 33.50,
    'event_7941': 2298.0,
    'event_9421': 4543.0,
    'event_9806': 9968.0,
    'event_10521': 393.22,
}

profiles = {r['user_id']: r for r in csv.DictReader(open('dataset/financial_profiles.csv'))}
events_raw = list(csv.DictReader(open('dataset/financial_events.csv')))
for e in events_raw:
    if not e['amount'] and e['event_id'] in IMAGE_AMOUNTS:
        e['amount'] = str(IMAGE_AMOUNTS[e['event_id']])

rates = {}
for r in csv.DictReader(open('dataset/exchange_rates.csv')):
    rates[(r['rate_date'], r['from_currency'], r['to_currency'])] = float(r['rate'])

messages = list(csv.DictReader(open('dataset/messages.csv')))
samples = list(csv.DictReader(open('dataset/sample_requests.csv')))

def get_home_amount(amount_str, currency, home_currency, date_str):
    if not amount_str:
        return 0.0
    amt = float(amount_str)
    if currency == home_currency:
        return amt
    if (date_str, currency, home_currency) in rates:
        return amt * rates[(date_str, currency, home_currency)]
    # search nearest rate
    for (d, fc, tc), r in rates.items():
        if fc == currency and tc == home_currency:
            return amt * r
    return amt

print("Loaded all data.")
