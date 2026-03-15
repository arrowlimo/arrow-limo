import os, sys, getpass, itertools, time

"""Automated Exchange 2019 on-prem probe.

Attempts combinations of:
  - Username formats: email, local part, DOMAIN\\user, DOMAIN\\email
  - Auth types: NTLM, BASIC (optionally others if specified)
  - Servers: provided list or defaults
  - Optional direct EWS URL

Stops on first success and prints the working parameters for reuse with
`export_complete_owa_data.py`.

Usage examples (PowerShell):
  $env:EXH_PASS="pass"
  python -X utf8 scripts\auto_exchange_probe.py --email info@arrowlimo.ca --domain ARROWLIMO --password-env EXH_PASS --servers exchange2019.company.local,exchange.company.local --ews-url https://exchange2019.company.local/EWS/Exchange.asmx

Dry-run (no connect):
  python -X utf8 scripts\auto_exchange_probe.py --email info@arrowlimo.ca --domain ARROWLIMO --dry-run
"""

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Auto probe Exchange 2019 credentials/server combinations')
    parser.add_argument('--email', required=True)
    parser.add_argument('--domain', help='DOMAIN part for DOMAIN\\user attempts')
    parser.add_argument('--password', help='Direct password/app password')
    parser.add_argument('--password-env', help='Env var holding password')
    parser.add_argument('--servers', help='Comma-separated list of server hostnames')
    parser.add_argument('--ews-url', help='Direct EWS URL (https://host/EWS/Exchange.asmx)')
    parser.add_argument('--auth', help='Comma-separated auth types to try (default: NTLM,BASIC)')
    parser.add_argument('--limit', type=int, default=0, help='Max attempts (0 = unlimited)')
    parser.add_argument('--delay', type=float, default=0.2, help='Delay seconds between attempts')
    parser.add_argument('--dry-run', action='store_true', help='Show combinations without connecting')
    args = parser.parse_args()

    password = args.password or (args.password_env and os.getenv(args.password_env))
    if not password and not args.dry_run:
        password = getpass.getpass(f'Password/app password for {args.email}: ')

    # Username candidates
    local_part = args.email.split('@')[0]
    candidates = {args.email, local_part}
    if args.domain:
        candidates.add(f"{args.domain}\\{local_part}")
        candidates.add(f"{args.domain}\\{args.email}")
    usernames = list(candidates)

    # Auth types
    auth_types = ['NTLM','BASIC']
    if args.auth:
        auth_types = [a.strip().upper() for a in args.auth.split(',') if a.strip()]

    # Servers
    servers = []
    if args.servers:
        servers = [s.strip() for s in args.servers.split(',') if s.strip()]
    else:
        servers = [
            '1.exchange.1and1.us',
            'exchange2019.ionos.com',
            'exchange.ionos.com'
        ]

    combos = []
    if args.ews_url:
        for u, a in itertools.product(usernames, auth_types):
            combos.append(('DIRECT', args.ews_url, u, a))
    for s, u, a in itertools.product(servers, usernames, auth_types):
        combos.append(('HOST', s, u, a))

    if args.dry_run:
        print('Dry-run combinations:')
        for mode, target, user, auth in combos:
            print(f'{mode} target={target} user={user} auth={auth}')
        print(f'Total combos: {len(combos)}')
        return

    try:
        from exchangelib import Credentials, Account, Configuration, DELEGATE, BaseProtocol
    except ImportError:
        print('ERROR: exchangelib not installed. pip install exchangelib')
        return

    attempt_count = 0
    for mode, target, user, auth in combos:
        attempt_count += 1
        if args.limit and attempt_count > args.limit:
            print('Attempt limit reached, stopping.')
            break
        print(f'Attempt {attempt_count}: mode={mode} target={target} user={user} auth={auth}')
        try:
            BaseProtocol.DEFAULT_AUTH_TYPE = auth
        except Exception:
            pass
        try:
            creds = Credentials(username=user, password=password)
            if mode == 'DIRECT':
                config = Configuration(service_endpoint=target, credentials=creds)
            else:
                config = Configuration(server=target, credentials=creds)
            acct = Account(primary_smtp_address=args.email, config=config, autodiscover=False, access_type=DELEGATE)
            _ = acct.root
            print('  SUCCESS')
            print('\nWorking parameters:')
            print(f'  --username "{user}" --auth {auth} ' + (f'--ews-url {target}' if mode=='DIRECT' else f'--servers {target}'))
            print('\nUse these with: export_complete_owa_data.py')
            return
        except Exception as e:
            print(f'  FAIL: {str(e)[:200]}')
        time.sleep(args.delay)

    print('\nNo combinations succeeded. Consider:')
    print('  - Verifying password/app password')
    print('  - Checking if OAuth-only is enforced')
    print('  - Trying different DOMAIN values or adjusting auth types')

if __name__ == '__main__':
    main()