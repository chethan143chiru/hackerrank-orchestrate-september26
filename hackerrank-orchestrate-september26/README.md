# Buy or Wait – AI Financial Decision Agent

## 1. Project Overview

This project implements **Buy or Wait?**, an AI-powered financial decision agent for the HackerRank Orchestrate challenge (September 2026). For every purchase or payment request in `requests.csv`, the agent decides whether the user should:

- **Pay in full** immediately
- **Pay partially** now and the rest later
- **Use installments** from available payment options
- **Wait** until a future date when full payment becomes safe
- **Not proceed** if the request cannot be completed safely

The agent reconstructs the user's financial position from structured profiles, financial events, exchange rates, messages, images, and seller payment options — then produces a 90-day cash-flow forecast to ensure the user's minimum balance is never breached.

---

## 2. Approach

The agent follows a **deterministic, rule-based** approach with no LLM calls. It reconstructs the user's financial state by:

1. **Loading the user profile** — home currency, current balance, minimum balance to keep, protected categories, flexible categories, and payment preferences.
2. **Parsing messages** — extracting salary updates, rent changes, contract endings, and one-off income adjustments via regex patterns on message text.
3. **Cataloging financial events** — separating pending debits, settled recurring streams, salary events, and one-off credits.
4. **Hardcoding image-extracted amounts** — 16 images were manually analyzed, and their financial amounts are embedded as a lookup table in `IMAGE_AMOUNTS`.
5. **Building a 90-day balance curve** — projecting daily inflows (salary) and outflows (recurring expenses, pending debits) to create a day-by-day running balance.
6. **Evaluating 5 candidate plans** against the forecast and the user's constraints, then ranking them.

---

## 3. Architecture

```
Data Loading (CSV + Images)
        ↓
Message Parsing (regex extraction)
        ↓
User Context Assembly (profile + events + salary + rent)
        ↓
90-Day Cash Flow Forecast (daily balance curve)
        ↓
Candidate Plan Generation (5 plan types)
        ↓
Plan Ranking & Selection (deadline, cost, changes, start date, payments)
        ↓
Explanation Generation
        ↓
output.csv
```

**Pipeline stages:**

| Stage | Input | Output |
|-------|-------|--------|
| Data Loading | 7 CSV files + 16 images | In-memory structures |
| Context Assembly | Profile + messages + events | Salary info, rent multiplier, event lists |
| Forecast | Events + salary + pending debits | 91-element balance curve |
| Plan Generation | Balance curve + request + options | Up to 5 candidate plans |
| Plan Ranking | All candidates | Best plan (or not_affordable) |
| Output | All results | `dataset/output.csv` |

---

## 4. Dataset Usage

| File | Usage |
|------|-------|
| `financial_profiles.csv` | User's home currency, current balance, minimum balance, protected/willing categories, payment preferences, max installment months |
| `financial_events.csv` | Historical, pending, scheduled, settled, failed, and cancelled financial records. Used to detect recurring expense patterns and project future outflows |
| `exchange_rates.csv` | Fixed dated rates for converting foreign-currency cash events to the user's home currency |
| `requests.csv` | 250 evaluation requests (request_id, user_id, date, type, amount, deadline, partial_payment flag) |
| `sample_requests.csv` | 25 public examples with completed output fields — used for validation only, not evaluation |
| `request_payment_options.csv` | 2–4 installment options per request (payment method, number of payments, amount, frequency, dates, total payable) |
| `messages.csv` | Employer, bank, merchant, and financial service messages that update salary amounts, pay dates, rent, and income status |
| `images.csv` | Metadata for 16 image files in `dataset/media/images/` — amounts were pre-extracted and hardcoded |
| `output.csv` | Blank prediction template with 250 request_ids |

---

## 5. AI / LLM Usage

**This agent is fully rule-based and makes zero LLM calls.** All intelligence is implemented via:

- **Regex pattern matching** on message text to extract salary amounts, pay dates, rent changes, and contract status
- **Statistical recurrence detection** — counting settled event intervals and selecting the most common interval
- **Deterministic cash-flow simulation** — projecting inflows and outflows day-by-day for 90 days
- **Candidate plan enumeration and ranking** — evaluating 5 plan types against constraints

**Image analysis** was done manually (16 images) and the extracted amounts are hardcoded in the `IMAGE_AMOUNTS` dictionary. No OCR or vision model is used at runtime.

**Estimated cost:** $0.00 (no API calls)

See `evaluation/usage_report.md` for the token usage report.

---

## 6. Financial Decision Logic

### amount_safe_to_pay

The maximum amount that can be paid today without ever dipping below `minimum_balance_to_keep` over the entire 90-day forecast:

```python
min_surplus_today = min(balance_curve[t] - min_bal for t in range(91))
amount_safe_to_pay = max(0, min(requested_amount, min_surplus_today))
```

### payment_plan selection

Five candidate plans are generated, then ranked by priority:

| Priority | Criterion | Best value |
|----------|-----------|------------|
| 1 | Completes by deadline | True before False |
| 2 | Requires no spending changes | False before True |
| 3 | Total payment cost | Lowest |
| 4 | Start date | Earliest |
| 5 | Number of payments | Fewest |

**Candidate plans evaluated:**

1. **Immediate full payment** — if `amount_safe_to_pay ≥ requested_amount` and `full_payment` is an allowed method
2. **Installments** — each option from `request_payment_options.csv`, filtered by `max_installment_months` and checked against the balance curve with cumulative installment deductions
3. **Partial payment** — if `allows_partial_payment` is true, splits into two payments: safe amount today + remainder on the earliest safe full-payment date
4. **Full payment with spending changes** — stops or reduces flexible, non-protected expenses to free up enough balance (tries single stop, single reduce, then stop+reduce combinations)
5. **Wait** — if earliest safe full-payment date ≤ deadline

### earliest_date_for_full_payment

The first day in the 90-day forecast where paying the full `requested_amount` keeps the balance at or above `minimum_balance_to_keep` for the remaining forecast period.

---

## 7. 90-Day Forecast

The forecast builds a **day-by-day balance curve** from `request_date` through `request_date + 90 days`:

### Inflows (daily_inflow)
- **Salary**: projected on the 15th of each month (or a specific first date from messages), using the base salary from the most recent settled salary event or message-updated amount. Supports one-off adjustments (reduced next salary, arrears, etc.)

### Outflows (daily_outflow)
- **Pending debits**: placed on their settlement date
- **Recurring expenses**: detected from settled debit events with ≥2 historical occurrences. Monthly categories (rent, utilities, insurance, debt, education) are projected on the same day of month. Interval-based categories (groceries, transport, dining) use the most common historical interval. Subscription categories (streaming, cloud storage, gym) are projected monthly per specific subscription.
- **Rent multiplier**: applied when a message indicates a rent increase (e.g., +12%)

### Balance curve construction
```python
running_bal = current_available_balance
for t in 0..90:
    running_bal += daily_inflow[t] - daily_outflow[t]
    balance_curve[t] = running_bal
```

The balance must **never fall below `minimum_balance_to_keep`** for any recommended plan.

---

## 8. Evaluation

Validation is run against `sample_requests.csv` (25 public examples):

```bash
python3 code/evaluation/main.py
```

**Metrics tracked:**
- **Status Match** — `affordability_status` matches expected
- **Method Match** — `recommended_payment_method` matches expected
- **Plan Match** — `payment_plan` string matches expected exactly
- **Safe Amount** — `amount_safe_to_pay` matches expected

The evaluation also processes all 250 evaluation requests and writes `dataset/output.csv`.

---

## 9. Installation

No external dependencies required — the project uses only Python 3 standard library modules.

```bash
# Clone the repository
git clone <repository-url>
cd <repository-name>

# Verify Python 3 is available
python3 --version

# No pip install needed — only stdlib used (csv, re, datetime, collections, os, sys)
```

---

## 10. Running

### Generate output.csv (full pipeline)
```bash
python3 code/evaluation/main.py
```

### Run agent with built-in sample validation only
```bash
python3 code/main.py
```

### Run scratch tests
```bash
python3 code/scratch/test_all_samples.py
```

---

## 11. Output

The agent produces `dataset/output.csv` with these columns:

| Column | Description |
|--------|-------------|
| `request_id` | Unique request identifier |
| `amount_safe_to_pay` | Maximum amount safe to pay today without breaching the minimum balance over 90 days |
| `affordability_status` | One of: `affordable_now`, `affordable_with_plan`, `affordable_later`, `not_affordable` |
| `recommended_payment_method` | One of: `full_payment`, `partial_payment`, `installments`, `wait`, `not_recommended` |
| `payment_plan` | Chronological `YYYY-MM-DD:amount` entries separated by `\|`, or `none` |
| `earliest_date_for_full_payment` | First date when full payment is safe, or empty if not possible |
| `spending_changes_needed` | `none` or `stop:<event_id>` / `reduce_to:<event_id>:<amount>` actions |
| `decision_explanation` | Concise, grounded explanation of the recommendation |

---

## 12. Token Usage / Cost

This agent makes **zero LLM API calls** — it is entirely rule-based with regex parsing and deterministic forecasting.

**Estimated total cost: $0.00**

See `evaluation/usage_report.md` for the full usage report format.

| Metric | Value |
|--------|-------|
| Model calls | 0 |
| Input tokens | 0 |
| Output tokens | 0 |
| Total tokens | 0 |
| Estimated cost | $0.00 |

---

## 13. Project Structure

```
.
├── AGENTS.md                          # Agent instructions and rules
├── CLAUDE.md                          # Claude-specific agent config
├── README.md                          # This file
├── problem_statement.md               # Full challenge specification
├── .gitignore
├── code/
│   ├── main.py                        # Core FinancialAgent class
│   ├── evaluation/
│   │   ├── main.py                    # Evaluation workflow (validate + generate output)
│   │   └── usage_report.md            # Token usage report
│   └── scratch/
│       ├── test_all_samples.py        # Full-sample test harness
│       ├── test_calibrated.py         # Calibrated test variant
│       ├── test_categories.py         # Category-specific tests
│       ├── test_refined.py            # Refined test variant
│       └── test_sim.py                # Simulation test
├── dataset/
│   ├── financial_profiles.csv         # User profiles (140 users)
│   ├── financial_events.csv           # Financial events (10k+ rows)
│   ├── exchange_rates.csv             # Fixed dated exchange rates
│   ├── requests.csv                   # 250 evaluation requests
│   ├── sample_requests.csv            # 25 public examples with answers
│   ├── request_payment_options.csv    # Installment options per request
│   ├── messages.csv                   # Employer/bank/merchant messages
│   ├── images.csv                     # Image metadata
│   ├── output.csv                     # Generated output (blank template)
│   └── media/
│       └── images/                    # 16 PNG images (image_01–image_16)
└── Desktop/
    └── chethan143chiru/               # Participant profile assets
        ├── README.md
        └── assets/
```

### Key files explained

| File | Purpose |
|------|---------|
| `code/main.py` | The `FinancialAgent` class: loads data, forecasts cash flow, evaluates requests, ranks plans, generates explanations |
| `code/evaluation/main.py` | Entry point that runs validation + output generation and prints summary |
| `code/scratch/test_all_samples.py` | Standalone test harness with a `Simulator` class (slightly refined variant of the agent) |
| `dataset/media/images/*.png` | 16 receipt/invoice screenshots whose amounts are hardcoded in `IMAGE_AMOUNTS` |

---

## 14. Limitations

1. **Hardcoded image amounts** — The 16 image-extracted values are embedded in source code. Any change to images requires manual re-extraction and code update.

2. **Regex-only message parsing** — Salary and rent extraction relies on fixed regex patterns. Messages in unexpected formats or languages may not be parsed correctly.

3. **Single pay_day assumption** — Salary is projected on the 15th of each month unless a specific first date is given. Users with different pay schedules may get inaccurate forecasts.

4. **No inter-request dependencies** — Each request is evaluated independently. Multiple requests for the same user do not account for each other's impact on the balance.

5. **Conservative recurring detection** — Recurrence requires ≥2 historical settled events. New or infrequent expenses (e.g., annual insurance) may be missed.

6. **No interest or fees on installments** — Installment total cost comes from `request_payment_options.csv` but the agent does not model interest accrual or late fees.

7. **Spending changes limited to 3 actions** — The agent can suggest at most 3 stop/reduce actions per request.

8. **Fixed 90-day forecast window** — Requests with deadlines beyond 90 days are evaluated against the same 90-day curve, which may undercount long-term affordability.

9. **No cross-currency arbitrage** — Exchange rates are used as-is from the provided table; no rate optimization or hedging is modeled.

10. **Deterministic, no probabilistic modeling** — The agent uses conservative estimates with no Monte Carlo simulation or confidence intervals.
