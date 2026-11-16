"""CLI: generate / analyze / policy / check / demo / serve"""
import argparse, json, sys
from .generator import generate_payments
from .analytics import rail_comparison, recovery_rate_by_lag_and_reason, retry_cost_accounting
from .policy import simulate_policies, validate_retry_plan, derive_policy
from .state_machine import transition, IllegalTransitionError

def _print_json(obj):
    print(json.dumps(obj, indent=2, sort_keys=True))

def cmd_generate(args):
    payments = generate_payments(seed=args.seed, n=args.count, period=args.period)
    out = json.dumps(payments, indent=2, sort_keys=True)
    if args.output:
        with open(args.output, "w") as f:
            f.write(out + "\n")
        print(f"wrote {len(payments)} payments to {args.output}")
    else:
        print(out)
    return 0

def cmd_analyze(args):
    payments = generate_payments(seed=args.seed, n=args.count, period=args.period)
    rec = recovery_rate_by_lag_and_reason(payments)
    rec_str = {f"{k[0]}|{k[1]}": v for k, v in rec.items()}
    _print_json({"rail_comparison": rail_comparison(payments), "recovery_by_lag_reason": rec_str, "costs": retry_cost_accounting(payments)})
    return 0

def cmd_policy(args):
    p1 = generate_payments(seed=42, n=args.count, period=1)
    p2 = generate_payments(seed=42, n=args.count, period=2)
    _print_json(simulate_policies(p1, p2, min_n=args.min_n))
    return 0

def cmd_check(args):
    if args.input:
        try:
            with open(args.input) as f:
                data = json.load(f)
        except Exception as e:
            print(f"check failed: cannot load input: {e}", file=sys.stderr)
            return 2
        # data may be a plan list or payments list
        if isinstance(data, list) and data and "planned_retries" in data[0]:
            violations = validate_retry_plan(data)
            if violations:
                _print_json({"ok": False, "violations": violations})
                return 1
            _print_json({"ok": True, "violations": []})
            return 0
        if isinstance(data, list) and data and "attempts" in data[0]:
            # validate final states are terminal-valid names
            valid = {"settled", "failed_permanent", "written_off"}
            for p in data:
                if p.get("final_state") not in valid:
                    print(f"check failed: bad final_state {p.get('final_state')}", file=sys.stderr)
                    return 2
            _print_json({"ok": True, "count": len(data)})
            return 0
        print("check failed: unrecognised input shape", file=sys.stderr)
        return 2
    # seeded data check
    payments = generate_payments(seed=42, n=500, period=1)
    try:
        # exercise state machine on a valid path
        s = transition("initiated", "authorized")
        s = transition(s, "settled")
    except IllegalTransitionError as e:
        print(f"check failed: {e}", file=sys.stderr)
        return 2
    # sample valid plan should have no violations
    valid_plan = [{"payment_id": "x1", "rail": "ACH", "failure_reason": "insufficient_funds", "failure_code": "R01", "planned_retries": 2}]
    if validate_retry_plan(valid_plan):
        print("check failed: valid plan flagged", file=sys.stderr)
        return 2
    _print_json({"ok": True, "seeded_count": len(payments), "rail_comparison": rail_comparison(payments)})
    return 0

def cmd_demo(args):
    p1 = generate_payments(seed=42, n=2000, period=1)
    p2 = generate_payments(seed=42, n=2000, period=2)
    print("=== Payments Lifecycle Analytics — Demo (synthetic, seed 42) ===")
    print("Rail comparison (period 1, n=2000):")
    _print_json(rail_comparison(p1))
    print("Costs (ILLUSTRATIVE):")
    _print_json(retry_cost_accounting(p1))
    print("Derived policy vs naive (derive on period 1, score on period 2):")
    _print_json(simulate_policies(p1, p2, min_n=20))
    return 0

def cmd_serve(args):
    from http.server import BaseHTTPRequestHandler, HTTPServer
    payments = generate_payments(seed=42, n=1000, period=1)
    report = {"rail_comparison": rail_comparison(payments), "costs": retry_cost_accounting(payments)}
    body = json.dumps(report, indent=2, sort_keys=True).encode()
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/report":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404); self.end_headers()
        def log_message(self, *a):
            pass
    server = HTTPServer(("127.0.0.1", args.port), H)
    print(f"serving on http://127.0.0.1:{args.port}/report")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0

def main(argv=None):
    parser = argparse.ArgumentParser(prog="payments-lifecycle")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("generate", "analyze"):
        sp = sub.add_parser(name)
        sp.add_argument("--seed", type=int, default=42)
        sp.add_argument("--count", type=int, default=1000)
        sp.add_argument("--period", type=int, default=1)
        if name == "generate":
            sp.add_argument("--output", default=None)
    sp = sub.add_parser("policy"); sp.add_argument("--count", type=int, default=2000); sp.add_argument("--min-n", type=int, default=20)
    sp = sub.add_parser("check"); sp.add_argument("--input", default=None)
    sp = sub.add_parser("demo")
    sp = sub.add_parser("serve"); sp.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    dispatch = {"generate": cmd_generate, "analyze": cmd_analyze, "policy": cmd_policy, "check": cmd_check, "demo": cmd_demo, "serve": cmd_serve}
    return dispatch[args.cmd](args)

if __name__ == "__main__":
    raise SystemExit(main())
