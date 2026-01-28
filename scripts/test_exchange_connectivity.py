import os, sys, getpass

"""Minimal Exchange connectivity tester.

Usage (PowerShell):
  $env:EXCHANGE_APP_PASSWORD="secret"
  python -X utf8 scripts\test_exchange_connectivity.py --email info@arrowlimo.ca --password-env EXCHANGE_APP_PASSWORD --servers 1.exchange.1and1.us,exchange2019.ionos.com,exchange.ionos.com,outlook.office365.com

This avoids full calendar/email enumeration and just validates credentials and server reachability.
"""

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Test Exchange server connectivity/auth (supports on-prem)')
    parser.add_argument('--email', required=True, help='Primary SMTP address (used for autodiscover/root)')
    parser.add_argument('--username', help='Explicit username or DOMAIN\\user for auth (defaults to --email)')
    parser.add_argument('--password', help='Direct password/app password')
    parser.add_argument('--password-env', help='Env var containing password/app password')
    parser.add_argument('--servers', help='Comma-separated server list (optional)')
    parser.add_argument('--autodiscover', action='store_true', help='Try autodiscover if direct servers fail')
    parser.add_argument('--auth', choices=['BASIC','NTLM','OAUTH2','GSSAPI','NOAUTH'], help='Force auth type (BASIC/NTLM common)')
    parser.add_argument('--ews-url', help='Direct EWS endpoint URL (e.g. https://exch.company.local/EWS/Exchange.asmx)')
    args = parser.parse_args()

    password = args.password
    if not password and args.password_env:
        password = os.getenv(args.password_env)
    if not password:
        password = getpass.getpass(f'Password/app password for {args.email}: ')

    username = args.username or args.email

    servers = []
    if args.servers:
        servers = [s.strip() for s in args.servers.split(',') if s.strip()]
    else:
        servers = [
            os.getenv('EXCHANGE_SERVER_OVERRIDE') or '',
            '1.exchange.1and1.us',
            'exchange2019.ionos.com',
            'exchange.ionos.com',
            'outlook.office365.com'
        ]
        servers = [s for s in servers if s]

    try:
        from exchangelib import Credentials, Account, Configuration, DELEGATE, BaseProtocol

        if args.auth:
            # Set allowed auth types to just the requested one for clarity
            BaseProtocol.DEFAULT_AUTH_TYPE = args.auth
    except ImportError:
        print('ERROR: exchangelib not installed. Install with: pip install exchangelib')
        sys.exit(1)

    creds = Credentials(username=username, password=password)
    success = False
    if args.ews-url:
        # Direct EWS URL bypass
        print(f'Attempting direct EWS URL: {args.ews_url}')
        try:
            config = Configuration(service_endpoint=args.ews_url, credentials=creds)
            acct = Account(primary_smtp_address=args.email, config=config, autodiscover=False, access_type=DELEGATE)
            _ = acct.root
            print(f'  SUCCESS: Connected via direct EWS URL.')
            success = True
        except Exception as e:
            print(f'  FAIL (direct URL): {str(e)[:160]}')

    if not success:
        for srv in servers:
            print(f'Attempting server host: {srv}')
            try:
                config = Configuration(server=srv, credentials=creds)
                acct = Account(primary_smtp_address=args.email, config=config, autodiscover=False, access_type=DELEGATE)
                _ = acct.root  # trigger connection
                print(f'  SUCCESS: Connected to {srv}')
                success = True
                break
            except Exception as e:
                print(f'  FAIL: {str(e)[:160]}')

    if not success and args.autodiscover:
        print('Trying autodiscover fallback...')
        try:
            acct = Account(primary_smtp_address=args.email, credentials=creds, autodiscover=True, access_type=DELEGATE)
            _ = acct.root
            print('  SUCCESS: Autodiscover connected.')
            success = True
        except Exception as e:
            print(f'  Autodiscover FAIL: {str(e)[:160]}')

    if not success:
        print('No successful connections. Check password/MFA/app password settings.')
        print('If MFA is enabled, create an app password and retry.')
        sys.exit(1)
    else:
        print('Connectivity test finished successfully.')

if __name__ == '__main__':
    main()