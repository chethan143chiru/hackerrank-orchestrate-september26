import csv, re, os
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

def parse_date(d_str):
    return datetime.strptime(d_str.strip(), '%Y-%m-%d').date()

def format_date(d):
    return d.strftime('%Y-%m-%d')

def format_num(amt):
    if abs(amt - round(amt)) < 1e-4:
        return f"{int(round(amt))}"
    return f"{amt:.2f}".rstrip('0').rstrip('.') if '.' in f"{amt:.2f}" else f"{amt:.2f}"

def format_currency_amount(amt, currency):
    # Format with commas for explanations e.g. IDR 15,952,906.67 or INR 122,500
    if abs(amt - round(amt)) < 1e-4:
        return f"{currency} {int(round(amt)):,}"
    return f"{currency} {amt:,.2f}"

class Simulator:
    def __init__(self, dataset_dir='dataset'):
        self.dataset_dir = dataset_dir
        self.profiles = {r['user_id']: r for r in csv.DictReader(open(f'{dataset_dir}/financial_profiles.csv'))}
        
        self.rates = {}
        for r in csv.DictReader(open(f'{dataset_dir}/exchange_rates.csv')):
            self.rates[(r['rate_date'], r['from_currency'], r['to_currency'])] = float(r['rate'])
            
        events_raw = list(csv.DictReader(open(f'{dataset_dir}/financial_events.csv')))
        for e in events_raw:
            eid = e['event_id']
            if not e['amount'] and eid in IMAGE_AMOUNTS:
                e['amount'] = str(IMAGE_AMOUNTS[eid])
        
        self.events_by_user = defaultdict(list)
        for e in events_raw:
            self.events_by_user[e['user_id']].append(e)
            
        self.messages_by_user = defaultdict(list)
        for r in csv.DictReader(open(f'{dataset_dir}/messages.csv')):
            self.messages_by_user[r['user_id']].append(r)
            
        self.options_by_req = defaultdict(list)
        for r in csv.DictReader(open(f'{dataset_dir}/request_payment_options.csv')):
            self.options_by_req[r['request_id']].append(r)

    def convert_currency(self, amt, from_curr, to_curr, date_str):
        if from_curr == to_curr or not amt:
            return amt
        key = (date_str, from_curr, to_curr)
        if key in self.rates:
            return amt * self.rates[key]
        for (d, fc, tc), r in self.rates.items():
            if fc == from_curr and tc == to_curr:
                return amt * r
        return amt

    def parse_user_context(self, user_id, req_date):
        prof = self.profiles[user_id]
        home_curr = prof['home_currency']
        cur_bal = float(prof['current_available_balance'])
        min_bal = float(prof['minimum_balance_to_keep'])
        user_events = self.events_by_user[user_id]
        user_msgs = self.messages_by_user[user_id]

        salary_info = {
            'confirmed': True,
            'amount': None,
            'pay_day': 15,
            'first_date': None,
            'one_off_next': None
        }
        rent_multiplier = 1.0

        for m in user_msgs:
            text = m['message_text']
            if 'seasonal contract has ended' in text or 'No off-season income' in text:
                salary_info['confirmed'] = False

            # IDR raise
            m_idr = re.search(r'naik menjadi IDR\s*([\d\.,]+)', text)
            if m_idr:
                salary_info['amount'] = float(m_idr.group(1).replace(',', '').rstrip('.'))
            
            # EUR temp pay
            m_eur = re.search(r'temporary monthly pay is EUR\s*([\d\.,]+)', text)
            if m_eur:
                salary_info['amount'] = float(m_eur.group(1).replace(',', '').rstrip('.'))

            # EUR reduced next salary
            m_red = re.search(r'next salary is reduced to EUR\s*([\d\.,]+)', text)
            if m_red:
                salary_info['one_off_next'] = float(m_red.group(1).replace(',', '').rstrip('.'))

            # USD raise
            m_usd = re.search(r'monthly salary has increased to USD\s*([\d\.,]+)', text)
            if m_usd:
                salary_info['amount'] = float(m_usd.group(1).replace(',', '').rstrip('.'))

            # Resumed regular salary
            m_res = re.search(r'Regular salary of EUR\s*([\d\.,]+)\s*resumes', text)
            if m_res:
                salary_info['amount'] = float(m_res.group(1).replace(',', '').rstrip('.'))

            # First salary ZAR
            m_first_zar = re.search(r'first salary will be ZAR\s*([\d\.,]+)', text)
            if m_first_zar:
                salary_info['amount'] = float(m_first_zar.group(1).replace(',', '').rstrip('.'))

            # First salary EUR
            m_first_eur = re.search(r'first salary will be EUR\s*([\d\.,]+)', text)
            if m_first_eur:
                salary_info['amount'] = float(m_first_eur.group(1).replace(',', '').rstrip('.'))

            # IDR confirmed base salary
            m_idr_conf = re.search(r'Gaji pokok yang dikonfirmasi adalah IDR\s*([\d\.,]+)', text)
            if m_idr_conf:
                salary_info['amount'] = float(m_idr_conf.group(1).replace(',', '').rstrip('.'))

            # Pay date update
            m_date = re.search(r'expected on\s*(\d{4}-\d{2}-\d{2})', text)
            if m_date:
                salary_info['first_date'] = parse_date(m_date.group(1))

            # Rent change
            m_rent = re.search(r'increases monthly rent by\s*(\d+)%', text)
            if m_rent:
                rent_multiplier = 1.0 + float(m_rent.group(1)) / 100.0

        return prof, cur_bal, min_bal, user_events, salary_info, rent_multiplier

    def forecast_cash_flow(self, user_id, req_date, days=90, spending_changes=None):
        prof, cur_bal, min_bal, user_events, salary_info, rent_multiplier = self.parse_user_context(user_id, req_date)
        home_curr = prof['home_currency']

        stopped_events = set()
        reduced_events = {}
        if spending_changes:
            for sc in spending_changes.split('|'):
                sc = sc.strip()
                if sc.startswith('stop:'):
                    stopped_events.add(sc.split(':')[1])
                elif sc.startswith('reduce_to:'):
                    parts = sc.split(':')
                    reduced_events[parts[1]] = float(parts[2])

        # Separate past events, pending debits, salary, and recurring streams
        pending_debits = []
        cat_streams = defaultdict(list)
        sub_streams = defaultdict(list)
        salary_events = []

        for e in user_events:
            amt = float(e['amount']) if e['amount'] else 0.0
            amt_home = self.convert_currency(amt, e['currency'], home_curr, e['settlement_date'] or e['event_date'])
            e_dict = dict(e)
            e_dict['amount_home'] = amt_home

            if e['category'] == 'salary' or 'salary' in e['description'].lower():
                salary_events.append(e_dict)

            # Pending debits
            if e['status'] == 'pending' and e['direction'] == 'debit':
                settle_d = parse_date(e['settlement_date']) if e['settlement_date'] else parse_date(e['event_date'])
                if settle_d >= req_date:
                    pending_debits.append((settle_d, e_dict))

            # Settled debits
            if e['status'] == 'settled' and e['direction'] == 'debit':
                cat = e['category']
                if cat in ('streaming', 'cloud_storage', 'music_subscription', 'delivery_membership', 'gym'):
                    sub_streams[(cat, e['description'])].append(e_dict)
                else:
                    cat_streams[cat].append(e_dict)

        daily_inflow = defaultdict(float)
        daily_outflow = defaultdict(float)

        # 1. Apply pending debits
        for s_date, e in pending_debits:
            offset = (s_date - req_date).days
            if 0 <= offset <= days:
                daily_outflow[offset] += e['amount_home']

        # 2. Project salary
        if salary_info['confirmed']:
            base_salary = salary_info['amount']
            if not base_salary and salary_events:
                settled_sals = [s for s in salary_events if s['status'] in ('settled', 'scheduled') and s['amount_home'] > 0]
                if settled_sals:
                    settled_sals.sort(key=lambda x: x['event_date'])
                    base_salary = settled_sals[-1]['amount_home']

            if base_salary:
                pay_day = salary_info['pay_day']
                cur_m = req_date.month
                cur_y = req_date.year
                for m_idx in range(4):
                    m = (cur_m - 1 + m_idx) % 12 + 1
                    y = cur_y + (cur_m - 1 + m_idx) // 12
                    try:
                        p_date = datetime(y, m, pay_day).date()
                    except ValueError:
                        p_date = datetime(y, m, 28).date()

                    if salary_info['first_date'] and m_idx == 0:
                        p_date = salary_info['first_date']

                    if p_date >= req_date:
                        offset = (p_date - req_date).days
                        if 0 <= offset <= days:
                            amt = base_salary
                            if m_idx == 0 and salary_info['one_off_next']:
                                amt = salary_info['one_off_next']
                            daily_inflow[offset] += amt

        # 3. Project subscriptions (specific to each subscription)
        for (cat, desc), evs in sub_streams.items():
            evs.sort(key=lambda x: x['event_date'])
            last_ev = evs[-1]
            last_eid = last_ev['event_id']

            if last_eid in stopped_events:
                continue

            last_date = parse_date(last_ev['event_date'])
            day_of_month = last_date.day
            amt = float(last_ev['amount_home'])
            if last_eid in reduced_events:
                amt = reduced_events[last_eid]

            cur_m = req_date.month
            cur_y = req_date.year
            for m_idx in range(4):
                m = (cur_m - 1 + m_idx) % 12 + 1
                y = cur_y + (cur_m - 1 + m_idx) // 12
                try:
                    occ_date = datetime(y, m, day_of_month).date()
                except ValueError:
                    occ_date = datetime(y, m, 28).date()

                if occ_date >= req_date:
                    offset = (occ_date - req_date).days
                    if 0 <= offset <= days:
                        daily_outflow[offset] += amt

        # 4. Project category streams (rent, utilities, debt, education, groceries, transport, dining, etc.)
        for cat, evs in cat_streams.items():
            if not evs:
                continue
            evs.sort(key=lambda x: x['event_date'])
            last_ev = evs[-1]
            last_eid = last_ev['event_id']

            if last_eid in stopped_events:
                continue

            dates = [parse_date(x['event_date']) for x in evs]
            diffs = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
            common_diff = Counter(diffs).most_common(1)[0][0] if diffs else 30
            avg_amt = sum(x['amount_home'] for x in evs) / len(evs)
            amt = avg_amt
            if last_eid in reduced_events:
                amt = reduced_events[last_eid]

            if cat == 'housing' or 'rent' in cat:
                amt *= rent_multiplier

            # Monthly categories: rent, utilities, insurance, education, debt_repayment
            if cat in ('rent', 'housing', 'utilities', 'insurance', 'debt_repayment', 'education', 'healthcare'):
                day_of_month = dates[-1].day
                cur_m = req_date.month
                cur_y = req_date.year
                for m_idx in range(4):
                    m = (cur_m - 1 + m_idx) % 12 + 1
                    y = cur_y + (cur_m - 1 + m_idx) // 12
                    try:
                        occ_date = datetime(y, m, day_of_month).date()
                    except ValueError:
                        occ_date = datetime(y, m, 28).date()

                    if occ_date >= req_date:
                        offset = (occ_date - req_date).days
                        if 0 <= offset <= days:
                            daily_outflow[offset] += amt
            else:
                # Interval-based (groceries: ~7, transport: ~7, dining: ~14)
                interval = common_diff if common_diff > 0 else 7
                nxt = dates[-1] + timedelta(days=interval)
                while nxt <= req_date + timedelta(days=days):
                    if nxt >= req_date:
                        offset = (nxt - req_date).days
                        if 0 <= offset <= days:
                            daily_outflow[offset] += amt
                    nxt += timedelta(days=interval)

        balance_curve = [0.0] * (days + 1)
        running_bal = cur_bal
        for t in range(days + 1):
            running_bal += daily_inflow[t] - daily_outflow[t]
            balance_curve[t] = running_bal

        return balance_curve, min_bal

    def evaluate_request(self, req):
        req_id = req['request_id']
        user_id = req['user_id']
        req_date = parse_date(req['request_date'])
        comp_date = parse_date(req['desired_completion_date'])
        req_amt = float(req['requested_amount'])
        allows_partial = req['allows_partial_payment'].strip().lower() in ('true', '1')

        prof = self.profiles[user_id]
        home_curr = prof['home_currency']
        pref_methods = [m.strip() for m in prof['payment_methods_user_will_consider'].split('|')]
        max_inst_months = int(prof['max_installment_months']) if prof['max_installment_months'].strip() else 0

        base_curve, min_bal = self.forecast_cash_flow(user_id, req_date, days=90, spending_changes=None)

        # 1. amount_safe_to_pay today
        min_surplus_today = min(base_curve[t] - min_bal for t in range(len(base_curve)))
        amount_safe_to_pay = max(0.0, min(req_amt, min_surplus_today))

        # 2. earliest_date_for_full_payment
        earliest_full_date = None
        for d_offset in range(len(base_curve)):
            safe = True
            for t in range(d_offset, len(base_curve)):
                if (base_curve[t] - req_amt) < min_bal - 1e-4:
                    safe = False
                    break
            if safe:
                earliest_full_date = req_date + timedelta(days=d_offset)
                break

        candidate_plans = []

        # Candidate 1: Immediate full payment
        if amount_safe_to_pay >= req_amt - 1e-4 and 'full_payment' in pref_methods:
            candidate_plans.append({
                'status': 'affordable_now',
                'method': 'full_payment',
                'plan': f"{format_date(req_date)}:{format_num(req_amt)}",
                'spending_changes': 'none',
                'completes_by_deadline': req_date <= comp_date,
                'requires_changes': False,
                'total_cost': req_amt,
                'start_date': req_date,
                'num_payments': 1,
                'option_id': 0
            })

        # Candidate 2: Installments
        options = self.options_by_req.get(req_id, [])
        for opt in options:
            if opt['payment_method'] == 'installments' and 'installments' in pref_methods:
                n_pay = int(opt['number_of_payments'])
                p_amt = float(opt['payment_amount'])
                f_date = parse_date(opt['first_payment_date'])
                freq = int(opt['payment_frequency_days']) if opt['payment_frequency_days'].strip() else 30
                tot_cost = float(opt['total_payable_amount'])
                opt_id_num = int(opt['payment_option_id'].split('_')[-1])

                duration_days = (n_pay - 1) * freq
                duration_months = round(duration_days / 30.0)
                if max_inst_months > 0 and duration_months > max_inst_months:
                    continue

                pay_dates = [f_date + timedelta(days=i * freq) for i in range(n_pay)]
                last_pay_date = pay_dates[-1]

                safe = True
                cum_inst = defaultdict(float)
                for p_d in pay_dates:
                    off = (p_d - req_date).days
                    if 0 <= off <= 90:
                        cum_inst[off] += p_amt

                cur_inst_paid = 0.0
                for t in range(len(base_curve)):
                    cur_inst_paid += cum_inst[t]
                    if (base_curve[t] - cur_inst_paid) < min_bal - 1e-4:
                        safe = False
                        break

                if safe:
                    plan_str = '|'.join(f"{format_date(d)}:{format_num(p_amt)}" for d in pay_dates)
                    candidate_plans.append({
                        'status': 'affordable_with_plan',
                        'method': 'installments',
                        'plan': plan_str,
                        'spending_changes': 'none',
                        'completes_by_deadline': last_pay_date <= comp_date,
                        'requires_changes': False,
                        'total_cost': tot_cost,
                        'start_date': f_date,
                        'num_payments': n_pay,
                        'option_id': opt_id_num
                    })

        # Candidate 3: Partial payment
        if allows_partial and 'partial_payment' in pref_methods:
            if 0 < amount_safe_to_pay < req_amt and earliest_full_date and earliest_full_date <= comp_date:
                rem_amt = req_amt - amount_safe_to_pay
                plan_str = f"{format_date(req_date)}:{format_num(amount_safe_to_pay)}|{format_date(earliest_full_date)}:{format_num(rem_amt)}"
                candidate_plans.append({
                    'status': 'affordable_with_plan',
                    'method': 'partial_payment',
                    'plan': plan_str,
                    'spending_changes': 'none',
                    'completes_by_deadline': earliest_full_date <= comp_date,
                    'requires_changes': False,
                    'total_cost': req_amt,
                    'start_date': req_date,
                    'num_payments': 2,
                    'option_id': 0
                })

        # Candidate 4: Full payment with spending changes
        if amount_safe_to_pay < req_amt - 1e-4 and 'full_payment' in pref_methods:
            willing_stop = [c.strip() for c in prof['expense_categories_user_is_willing_to_stop'].split('|') if c.strip()]
            willing_reduce = [c.strip() for c in prof['expense_categories_user_is_willing_to_reduce'].split('|') if c.strip()]
            protect = [c.strip() for c in prof['expense_categories_to_protect'].split('|') if c.strip()]

            user_events = self.events_by_user[user_id]
            eligible_stops = []
            eligible_reduces = []

            for e in user_events:
                cat = e['category']
                if cat in protect:
                    continue
                flex = e['flexibility']
                eid = e['event_id']
                amt = float(e['amount']) if e['amount'] else 0.0
                amt_home = self.convert_currency(amt, e['currency'], home_curr, e['settlement_date'] or e['event_date'])

                if cat in willing_stop and flex in ('stoppable', 'reducible_or_stoppable'):
                    eligible_stops.append((eid, amt_home, e['description']))
                if cat in willing_reduce and flex in ('reducible', 'reducible_or_stoppable'):
                    min_amt = float(e['minimum_allowed_amount']) if e['minimum_allowed_amount'] else amt_home * 0.5
                    min_amt_home = self.convert_currency(min_amt, e['currency'], home_curr, e['settlement_date'] or e['event_date'])
                    eligible_reduces.append((eid, min_amt_home, amt_home - min_amt_home, e['description']))

            found_changes = None
            for eid, savings, desc in eligible_stops:
                sc = f"stop:{eid}"
                c, _ = self.forecast_cash_flow(user_id, req_date, days=90, spending_changes=sc)
                if min(c[t] - min_bal for t in range(len(c))) >= req_amt - 1e-4:
                    found_changes = sc
                    break

            if not found_changes:
                for eid, min_amt, savings, desc in eligible_reduces:
                    sc = f"reduce_to:{eid}:{format_num(min_amt)}"
                    c, _ = self.forecast_cash_flow(user_id, req_date, days=90, spending_changes=sc)
                    if min(c[t] - min_bal for t in range(len(c))) >= req_amt - 1e-4:
                        found_changes = sc
                        break

            if not found_changes:
                for eid1, savings1, desc1 in eligible_stops:
                    for eid2, min_amt2, savings2, desc2 in eligible_reduces:
                        if eid1 != eid2:
                            sc = f"stop:{eid1}|reduce_to:{eid2}:{format_num(min_amt2)}"
                            c, _ = self.forecast_cash_flow(user_id, req_date, days=90, spending_changes=sc)
                            if min(c[t] - min_bal for t in range(len(c))) >= req_amt - 1e-4:
                                found_changes = sc
                                break
                    if found_changes:
                        break

            if found_changes:
                candidate_plans.append({
                    'status': 'affordable_with_plan',
                    'method': 'full_payment',
                    'plan': f"{format_date(req_date)}:{format_num(req_amt)}",
                    'spending_changes': found_changes,
                    'completes_by_deadline': req_date <= comp_date,
                    'requires_changes': True,
                    'total_cost': req_amt,
                    'start_date': req_date,
                    'num_payments': 1,
                    'option_id': 0
                })

        # Candidate 5: Wait
        if earliest_full_date and earliest_full_date <= comp_date and 'full_payment' in pref_methods:
            candidate_plans.append({
                'status': 'affordable_later',
                'method': 'wait',
                'plan': f"{format_date(earliest_full_date)}:{format_num(req_amt)}",
                'spending_changes': 'none',
                'completes_by_deadline': earliest_full_date <= comp_date,
                'requires_changes': False,
                'total_cost': req_amt,
                'start_date': earliest_full_date,
                'num_payments': 1,
                'option_id': 0
            })

        valid_plans = [p for p in candidate_plans if p['completes_by_deadline']]
        if valid_plans:
            valid_plans.sort(key=lambda p: (
                p['requires_changes'],
                p['total_cost'],
                p['start_date'],
                p['num_payments'],
                p['option_id']
            ))
            chosen = valid_plans[0]
        else:
            chosen = {
                'status': 'not_affordable',
                'method': 'not_recommended',
                'plan': 'none',
                'spending_changes': 'none'
            }

        earliest_full_str = format_date(earliest_full_date) if earliest_full_date else ""
        if chosen['status'] == 'not_affordable':
            earliest_full_str = ""

        explanation = self.generate_explanation(chosen, user_id, req, amount_safe_to_pay, earliest_full_date, min_bal, home_curr)

        return {
            'request_id': req_id,
            'amount_safe_to_pay': format_num(amount_safe_to_pay),
            'affordability_status': chosen['status'],
            'recommended_payment_method': chosen['method'],
            'payment_plan': chosen['plan'],
            'earliest_date_for_full_payment': earliest_full_str,
            'spending_changes_needed': chosen['spending_changes'],
            'decision_explanation': explanation
        }

    def generate_explanation(self, plan, user_id, req, safe_today, earliest_date, min_bal, currency):
        status = plan['status']
        method = plan['method']
        req_amt = float(req['requested_amount'])
        comp_date = req['desired_completion_date']

        if status == 'affordable_now':
            return f"Pay {format_currency_amount(req_amt, currency)} today. This leaves at least {format_currency_amount(min_bal, currency)} available over the next 90 days."
        elif status == 'affordable_with_plan':
            if method == 'installments':
                payments = plan['plan'].split('|')
                n = len(payments)
                first_amt = float(payments[0].split(':')[1])
                first_d_str = datetime.strptime(payments[0].split(':')[0], '%Y-%m-%d').strftime('%-d %B %Y')
                return f"Use {n} installments of {format_currency_amount(first_amt, currency)}, starting {first_d_str}. This leaves at least {format_currency_amount(min_bal, currency)} available."
            elif method == 'partial_payment':
                rem = req_amt - safe_today
                ed_str = earliest_date.strftime('%-d %B %Y') if earliest_date else comp_date
                return f"Pay {format_currency_amount(safe_today, currency)} today and the remaining {format_currency_amount(rem, currency)} on {ed_str}. This completes the full request and keeps the {format_currency_amount(min_bal, currency)} minimum protected."
            elif method == 'full_payment':
                changes = plan['spending_changes'].split('|')
                change_descs = []
                for c in changes:
                    if c.startswith('stop:'):
                        eid = c.split(':')[1]
                        desc = self.get_event_desc(user_id, eid)
                        change_descs.append(f"Stop the {desc.lower()}")
                    elif c.startswith('reduce_to:'):
                        parts = c.split(':')
                        eid = parts[1]
                        new_amt = float(parts[2])
                        desc = self.get_event_desc(user_id, eid)
                        change_descs.append(f"reduce the {desc.lower()} to {format_currency_amount(new_amt, currency)}")
                action_text = " and ".join(change_descs)
                return f"{action_text}, then pay {format_currency_amount(req_amt, currency)} today. This leaves at least {format_currency_amount(min_bal, currency)} available."
        elif status == 'affordable_later':
            ed_str = earliest_date.strftime('%-d %B %Y') if earliest_date else comp_date
            return f"Pay {format_currency_amount(req_amt, currency)} in full on {ed_str}. Paying earlier would take the balance below the {format_currency_amount(min_bal, currency)} minimum."
        else: # not_affordable
            if safe_today > 0:
                return f"Do not proceed with the {format_currency_amount(req_amt, currency)} request. Although {format_currency_amount(safe_today, currency)} is available today, the full amount cannot be completed safely within 90 days."
            else:
                cd_str = datetime.strptime(comp_date, '%Y-%m-%d').strftime('%-d %B %Y')
                return f"Do not make this payment by {cd_str}. None of the available options keeps the {format_currency_amount(min_bal, currency)} minimum protected."

    def get_event_desc(self, user_id, event_id):
        for e in self.events_by_user[user_id]:
            if e['event_id'] == event_id:
                return e['description']
        return "flexible expense"

sim = Simulator('dataset')
samples = list(csv.DictReader(open('dataset/sample_requests.csv')))
correct_status = 0
correct_method = 0
correct_plan = 0
total = len(samples)

for s in samples:
    res = sim.evaluate_request(s)
    match_status = res['affordability_status'] == s['affordability_status']
    match_method = res['recommended_payment_method'] == s['recommended_payment_method']
    match_plan = res['payment_plan'] == s['payment_plan']
    if match_status: correct_status += 1
    if match_method: correct_method += 1
    if match_plan: correct_plan += 1

    status_icon = "✓" if match_status else "✗"
    method_icon = "✓" if match_method else "✗"
    print(f"[{s['request_id']}] Status {status_icon}: {res['affordability_status']:<20} (Exp: {s['affordability_status']}) | Method {method_icon}: {res['recommended_payment_method']:<16} (Exp: {s['recommended_payment_method']}) | Safe: {res['amount_safe_to_pay']} (Exp: {s['amount_safe_to_pay']})")
    if not (match_status and match_method):
        print(f"  Plan: {res['payment_plan']}")
        print(f"  Exp : {s['payment_plan']}")

print(f"\nSample Accuracy Summary:")
print(f"Status Match: {correct_status}/{total} ({correct_status/total*100:.1f}%)")
print(f"Method Match: {correct_method}/{total} ({correct_method/total*100:.1f}%)")
print(f"Plan Match  : {correct_plan}/{total} ({correct_plan/total*100:.1f}%)")
