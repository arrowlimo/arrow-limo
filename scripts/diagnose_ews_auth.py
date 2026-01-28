import sys, os, base64, ssl
from urllib import request, error

"""Quick EWS authentication diagnostic.

Checks response headers for the Exchange Web Services endpoint to identify
available auth methods (Basic, NTLM, Bearer/OAuth). Optionally attempts a
basic auth handshake and reports status codes.

Usage (PowerShell):
  python -X utf8 scripts\diagnose_ews_auth.py --url https://exchange2019.ionos.com/EWS/Exchange.asmx
  python -X utf8 scripts\diagnose_ews_auth.py --url https://exchange2019.ionos.com/EWS/Exchange.asmx --email info@arrowlimo.ca --password-env EXH_PASS

Note: Does NOT store credentials, only tests and prints status.
"""

def parse_args():
    import argparse
    p = argparse.ArgumentParser(description='Diagnose EWS auth capabilities (Basic/NTLM/OAuth)')
    p.add_argument('--url', required=True, help='EWS endpoint URL (https://host/EWS/Exchange.asmx)')
    p.add_argument('--email', help='Username/email for basic auth test')
    p.add_argument('--password', help='Password/app password')
    p.add_argument('--password-env', help='Environment variable containing password')
    return p.parse_args()

def fetch(url, headers=None):
    req = request.Request(url, headers=headers or {})
    try:
        with request.urlopen(req, context=ssl.create_default_context()) as resp:
            return resp.status, dict(resp.headers)
    except error.HTTPError as e:
        return e.code, dict(e.headers)
    except Exception as e:
        print(f'ERROR: {e}')
        return None, {}

def main():
    args = parse_args()
    pwd = args.password or (args.password_env and os.getenv(args.password_env))

    print(f'[*] Probing EWS endpoint: {args.url}')
    status, hdrs = fetch(args.url)
    if status is None:
        sys.exit(1)
    print(f'Initial unauthenticated status: {status}')
    www = hdrs.get('WWW-Authenticate', '')
    all_headers = '\n'.join(f'{k}: {v}' for k,v in hdrs.items())
    print('\nResponse headers (truncated):')
    for k,v in list(hdrs.items())[:12]:
        print(f'  {k}: {v[:160]}')
    print('\nWWW-Authenticate raw:', www)

    indicators = []
    w_lower = www.lower()
    if 'basic' in w_lower:
        indicators.append('Basic')
    if 'ntlm' in w_lower:
        indicators.append('NTLM')
    if 'bearer' in w_lower or 'oauth' in w_lower:
        indicators.append('OAuth/Bearer')
    if not indicators:
        indicators.append('No explicit auth challenges detected (may still allow forms-based or blocked)')
    print('\nDetected auth mechanisms:', ', '.join(indicators))

    if args.email and pwd:
        print('\n[*] Attempting Basic auth with provided credentials...')
        token = base64.b64encode(f'{args.email}:{pwd}'.encode('utf-8')).decode('ascii')
        status_auth, hdrs_auth = fetch(args.url, headers={'Authorization': f'Basic {token}'})
        print(f'Basic auth attempt status: {status_auth}')
        if status_auth == 200:
            print('SUCCESS: Basic auth accepted.')
        elif status_auth == 401:
            print('FAIL: 401 Unauthorized - credentials rejected or Basic disabled.')
        elif status_auth == 403:
            print('FAIL: 403 Forbidden - access blocked (policy or IP restriction).')
        else:
            print('Unexpected status; headers excerpt:')
            for k,v in list(hdrs_auth.items())[:10]:
                print(f'  {k}: {v[:120]}')
    else:
        print('\n[!] Skipping credential test (provide --email and --password / --password-env to test).')

    print('\nNext steps guidance:')
    if 'Basic' in indicators and args.email and pwd:
        print('- Basic present; verify password or generate app password if MFA / portal uses modern auth.')
    if 'OAuth/Bearer' in indicators:
        print('- OAuth indicated; may need OAuth workflow (client id/secret) rather than password.')
    if 'NTLM' in indicators:
        print('- NTLM present; exchangelib NTLM should work with domain\\user if domain configured.')
    if 'Basic' not in indicators and 'NTLM' not in indicators and 'OAuth/Bearer' not in indicators:
        print('- No standard WWW-Authenticate headers: host may require pre-auth form (unsupported by direct EWS calls).')

if __name__ == '__main__':
    main()