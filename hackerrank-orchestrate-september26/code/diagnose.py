#!/usr/bin/env python3
"""Diagnostic script to understand failing sample requests."""
import csv
import os
from datetime import datetime, timedelta
from collections import defaultdict, Counter

IMAGE_AMOUNTS = {
    'event_253': 4365000.0, 'event_1442': 100000.0, 'event_1545': 41272.0,
    'event_1700': 2854.0, 'event_1786': 704.05, 'event_3051': 1995.0,
    'event_3231': 8528.0, 'event_4535': 15339.0, 'event_5170': 723.0,
    'event_6033': 79679.26, 'event_6859': 3650.0, 'event_7307': 33.50,
    'event_7941': 2298.0, 'event_9421': 4543.0, 'event_9806': 9968.0,
    'event_10521': 393.22,
}

def parse_date(d_str):
    return datetime.strptime(d_str.strip(), '%Y-%m-%d').date()

def main():
    ds = 'dataset'
    # Load profiles
    profiles = {}
    with open(os.path.join(ds, 'financial_profiles.csv')) as f:
        for r in csv.DictReader(f):
            profiles[r['user_id']] = r

    # Load rates
    rates = {}
    with open(os.path.join(ds, 'exchange_rates.csv')) as f:
        for r in csv.DictReader(f):
            rates[(r['rate_date'], r['from_currency'], r['to_currency'])] = float(r['rate'])

    # Load events
    events_by_user = defaultdict(list)
    with open(os.path.join(ds, 'financial_events.csv')) as f:
        for r in csv.DictReader(f):
            eid = r['event_id']
            if not r['amount'] and eid in IMAGE_AMOUNTS:
                r['amount'] = str(IMAGE_AMOUNTS[eid])
            events_by_user[r['user_id']].append(r)

    # Load messages
    msgs_by_user = defaultdict(list)
    with open(os.path.join(ds, 'messages.csv')) as f:
        for r in csv.DictReader(f):
            msgs_by_user[r['user_id']].append(r)

    # Load payment options
    options_by_req = defaultdict(list)
    with open(os.path.join(ds, 'request_payment_options.csv')) as f:
        for r in csv.DictReader(f):
            options_by_req[r['request_id']].append(r)

    # Load sample requests
    with open(os.path.join(ds, 'sample_requests.csv')) as f:
        samples = list(csv.DictReader(f))

    # Failing ones
    failing_ids = ['request_05', 'request_06', 'request_08', 'request_11',
                   'request_12', 'request_13', 'request_17', 'request_19',
                   'request_21', 'request_22', 'request_23']

    for s in samples:
        rid = s['request_id']
        if rid not in failing_ids:
            continue
        uid = s['user_id']
        req_date = parse_date(s['request_date'])
        req_amt = float(s['requested_amount'])
        comp_date = parse_date(s['desired_completion_date'])
        allows_partial = s['allows_partial_payment'].strip().lower() in ('true', '1')
        prof = profiles[uid]
        home_curr = prof['home_currency']
        pref_methods = [m.strip() for m in prof['payment_methods_user_will_consider'].split('|')]
        max_inst = int(prof['max_installment_months']) if prof['max_installment_months'].strip() else 0

        print(f"\n{'='*80}")
        print(f"=== {rid} | User: {uid} | Date: {s['request_date']} | Amount: {req_amt} | Complete by: {s['desired_completion_date']}")
        print(f"    Currency: {home_curr} | Balance: {prof['current_available_balance']} | Min: {prof['minimum_balance_to_keep']}")
        print(f"    Pref methods: {pref_methods} | Max inst months: {max_inst} | Partial: {allows_partial}")
        print(f"    Expected: {s['affordability_status']} / {s['recommended_payment_method']} / safe={s['amount_safe_to_pay']}")

        # Show relevant events
        uevents = events_by_user[uid]
        print(f"\n    --- Events for {uid} ({len(uevents)} total) ---")

        # Show pending debits after request date
        pending = [e for e in uevents if e['status'] == 'pending' and e['direction'] == 'debit'
                   and parse_date(e['settlement_date'] or e['event_date']) >= req_date]
        if pending:
            print(f"    Pending debits after {s['request_date']}:")
            for e in pending[:10]:
                print(f"      {e['event_id']} | {e['settlement_date']} | {e['currency']} {e['amount']} | {e['category']} | {e['description']}")

        # Show salary events
        salaries = [e for e in uevents if e['category'] == 'salary' or 'salary' in e['description'].lower()]
        if salaries:
            print(f"    Salary events:")
            for e in salaries[:5]:
                print(f"      {e['event_id']} | {e['event_date']} | {e['status']} | {e['currency']} {e['amount']} | {e['description']}")

        # Show recurring settled debits
        settled_debits = [e for e in uevents if e['status'] == 'settled' and e['direction'] == 'debit']
        cat_groups = defaultdict(list)
        for e in settled_debits:
            cat_groups[e['category']].append(e)
        print(f"    Recurring settled debits by category:")
        for cat, evs in sorted(cat_groups.items()):
            amts = [float(e['amount']) if e['amount'] else 0 for e in evs]
            dates = [e['event_date'] for e in evs]
            print(f"      {cat}: {len(evs)} events, amounts={amts[:5]}, dates={dates[:5]}")

        # Show payment options
        opts = options_by_req.get(rid, [])
        if opts:
            print(f"    Payment options:")
            for o in opts:
                print(f"      {o['payment_option_id']} | {o['payment_method']} | {o['number_of_payments']}x {o['payment_amount']} | freq={o['payment_frequency_days']}d | first={o['first_payment_date']} | total={o['total_payable_amount']}")

        # Show messages
        msgs = msgs_by_user[uid]
        if msgs:
            print(f"    Messages ({len(msgs)} total):")
            for m in msgs[:5]:
                print(f"      [{m.get('related_event_id','')}] {m['message_text'][:120]}")

if __name__ == '__main__':
    main()
