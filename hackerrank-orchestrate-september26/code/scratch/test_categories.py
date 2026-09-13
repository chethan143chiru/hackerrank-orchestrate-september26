import csv, re
from datetime import datetime, timedelta
from collections import defaultdict, Counter

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

events_by_user = defaultdict(list)
for e in events_raw:
    events_by_user[e['user_id']].append(e)

samples = list(csv.DictReader(open('dataset/sample_requests.csv')))

# Let's inspect user_01
uid = 'user_01'
evs = events_by_user[uid]
by_cat = defaultdict(list)
for e in evs:
    if e['status'] == 'settled' and e['direction'] == 'debit':
        by_cat[e['category']].append(e)

print(f"Categories for {uid}:")
for cat, items in by_cat.items():
    dates = sorted([datetime.strptime(x['event_date'], '%Y-%m-%d') for x in items])
    diffs = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
    common_diff = Counter(diffs).most_common(1)[0][0] if diffs else 0
    avg_amt = sum(float(x['amount']) for x in items) / len(items)
    print(f"  {cat}: {len(items)} items, interval={common_diff} days, avg_amt={avg_amt:.2f}, last_date={dates[-1].strftime('%Y-%m-%d')}")
