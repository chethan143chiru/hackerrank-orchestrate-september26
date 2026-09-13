#!/usr/bin/env python3
"""Deeper diagnostic: check messages for failing users and trace forecast."""
import csv, os
from collections import defaultdict

ds = 'dataset'

# Load messages
msgs_by_user = defaultdict(list)
with open(os.path.join(ds, 'messages.csv')) as f:
    for r in csv.DictReader(f):
        msgs_by_user[r['user_id']].append(r)

# Load events
events_by_user = defaultdict(list)
with open(os.path.join(ds, 'financial_events.csv')) as f:
    for r in csv.DictReader(f):
        events_by_user[r['user_id']].append(r)

# Show all messages for failing users
failing_users = ['user_05','user_06','user_08','user_11','user_12','user_13','user_17','user_19','user_21','user_22','user_23']
for uid in failing_users:
    msgs = msgs_by_user[uid]
    print(f"\n=== Messages for {uid} ({len(msgs)} total) ===")
    for m in msgs:
        print(f"  [{m.get('related_event_id','')}] {m['message_text'][:200]}")

    # Show salary-like events with "final" or "last" in description
    for e in events_by_user[uid]:
        desc_lower = e['description'].lower()
        if any(kw in desc_lower for kw in ['final', 'last', 'severance', 'ended', 'contract', 'termination']):
            if e['category'] == 'salary' or 'salary' in desc_lower or 'payroll' in desc_lower or 'pay' in desc_lower:
                print(f"  EVENT: {e['event_id']} | {e['event_date']} | {e['status']} | {e['direction']} | {e['currency']} {e['amount']} | {e['description']}")

    # Show latest salary event
    sal = [e for e in events_by_user[uid] if e['category'] == 'salary' or 'salary' in e['description'].lower() or 'payroll' in e['description'].lower()]
    if sal:
        sal.sort(key=lambda x: x['event_date'])
        print(f"  Latest salary: {sal[-1]['event_id']} | {sal[-1]['event_date']} | {sal[-1]['amount']} | {sal[-1]['description']}")
