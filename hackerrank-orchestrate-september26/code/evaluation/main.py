"""
Evaluation Workflow — Buy or Wait? AI Financial Decision Agent

This script runs the full evaluation pipeline:
  1. Load dataset (profiles, events, rates, messages, payment options, images)
  2. Validate against sample_requests.csv (public examples with known answers)
  3. Run the agent against all evaluation requests in requests.csv
  4. Write output.csv
  5. Print accuracy summary and token usage report

Usage:
    python3 code/evaluation/main.py
"""

import sys
import os

# Add the code/ directory to sys.path so we can import main directly
# (the directory name 'code' conflicts with Python's built-in 'code' module)
_code_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, _code_dir)

import main as _main_module
FinancialAgent = _main_module.FinancialAgent
format_num = _main_module.format_num
format_date = _main_module.format_date

del sys.path[0]  # clean up

import csv
from datetime import datetime


def validate_samples(agent):
    """Run the agent against sample_requests.csv and print accuracy metrics."""
    sample_path = os.path.join('dataset', 'sample_requests.csv')
    if not os.path.exists(sample_path):
        print("[SKIP] sample_requests.csv not found; skipping validation.")
        return

    samples = list(csv.DictReader(open(sample_path, encoding='utf-8')))
    correct_status = 0
    correct_method = 0
    correct_plan = 0
    total = len(samples)

    print("=" * 70)
    print("STEP 1: VALIDATION AGAINST SAMPLE REQUESTS")
    print("=" * 70)

    for s in samples:
        res = agent.evaluate_request(s)
        match_status = res['affordability_status'] == s['affordability_status']
        match_method = res['recommended_payment_method'] == s['recommended_payment_method']
        match_plan = res['payment_plan'] == s['payment_plan']
        if match_status:
            correct_status += 1
        if match_method:
            correct_method += 1
        if match_plan:
            correct_plan += 1

        status_icon = "✓" if match_status else "✗"
        method_icon = "✓" if match_method else "✗"
        print(
            f"  [{s['request_id']}] "
            f"Status {status_icon}: {res['affordability_status']:<22} "
            f"(Exp: {s['affordability_status']:<22}) | "
            f"Method {method_icon}: {res['recommended_payment_method']:<16} "
            f"(Exp: {s['recommended_payment_method']}) | "
            f"Safe: {res['amount_safe_to_pay']} (Exp: {s['amount_safe_to_pay']})"
        )
        if not (match_status and match_method):
            print(f"    Plan : {res['payment_plan']}")
            print(f"    Exp  : {s['payment_plan']}")

    print(f"\n  Sample Accuracy Summary:")
    print(f"  Status Match : {correct_status}/{total} ({correct_status / total * 100:.1f}%)")
    print(f"  Method Match : {correct_method}/{total} ({correct_method / total * 100:.1f}%)")
    print(f"  Plan Match   : {correct_plan}/{total} ({correct_plan / total * 100:.1f}%)")
    print()
    return correct_status, correct_method, correct_plan, total


def generate_output(agent):
    """Run the agent against requests.csv and write output.csv."""
    requests_path = os.path.join('dataset', 'requests.csv')
    output_path = os.path.join('dataset', 'output.csv')

    requests = list(csv.DictReader(open(requests_path, encoding='utf-8')))

    print("=" * 70)
    print("STEP 2: GENERATING OUTPUT FOR EVALUATION REQUESTS")
    print("=" * 70)
    print(f"  Total requests: {len(requests)}")
    print()

    rows = []
    for req in requests:
        result = agent.evaluate_request(req)
        rows.append(result)
        print(f"  [{result['request_id']}] {result['affordability_status']:<22} "
              f"{result['recommended_payment_method']:<16} safe={result['amount_safe_to_pay']}")

    # Write output.csv with exact required columns
    fieldnames = [
        'request_id', 'amount_safe_to_pay', 'affordability_status',
        'recommended_payment_method', 'payment_plan',
        'earliest_date_for_full_payment', 'spending_changes_needed',
        'decision_explanation'
    ]

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n  Output written to: {output_path}")
    print(f"  Rows written: {len(rows)}")
    print()
    return rows


def print_summary():
    """Print usage and cost summary reference."""
    print("=" * 70)
    print("STEP 3: TOKEN USAGE / COST")
    print("=" * 70)
    usage_path = os.path.join('code', 'evaluation', 'usage_report.md')
    if os.path.exists(usage_path):
        with open(usage_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if content:
                print(f"  {content}")
            else:
                print("  usage_report.md is empty. No LLM calls were made (pure rule-based agent).")
    else:
        print("  usage_report.md not found. This agent is fully rule-based with no LLM calls.")
    print()


def main():
    print("=" * 70)
    print("BUY OR WAIT? — AI Financial Decision Agent")
    print("Evaluation Workflow")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()

    # Initialize the agent (loads all dataset files)
    print("Loading dataset...")
    agent = FinancialAgent(dataset_dir='dataset')
    print("  ✓ Profiles loaded")
    print("  ✓ Events loaded")
    print("  ✓ Exchange rates loaded")
    print("  ✓ Messages loaded")
    print("  ✓ Payment options loaded")
    print("  ✓ Image amounts loaded")
    print()

    # Step 1: Validate against known samples
    validation = validate_samples(agent)

    # Step 2: Generate output.csv
    rows = generate_output(agent)

    # Step 3: Print token usage
    print_summary()

    # Final summary
    print("=" * 70)
    print("WORKFLOW COMPLETE")
    print("=" * 70)
    print(f"  Dataset:        {len(rows)} evaluation requests processed")
    print(f"  Output:         dataset/output.csv")
    if validation:
        s, m, p, t = validation
        print(f"  Sample Status:  {s}/{t} ({s / t * 100:.1f}%)")
        print(f"  Sample Method:  {m}/{t} ({m / t * 100:.1f}%)")
        print(f"  Sample Plan:    {p}/{t} ({p / t * 100:.1f}%)")
    print(f"  Finished:       {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()


if __name__ == '__main__':
    main()
