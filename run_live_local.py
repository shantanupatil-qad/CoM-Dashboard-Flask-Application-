"""One-day localhost demo with Salesforce live reads and no saved credentials."""
import argparse
import getpass
import json
import os
import sys

def collect_settings(environ=None, ask=input, secret=getpass.getpass):
    from werkzeug.security import generate_password_hash
    env = dict(os.environ if environ is None else environ)
    env['DATA_MODE'] = 'live'
    env['SF_ORIGIN'] = (env.get('SF_ORIGIN') or ask('Production Salesforce My Domain URL (https://...my.salesforce.com): ')).strip()
    env['SF_CLIENT_ID'] = env.get('SF_CLIENT_ID') or secret('OAuth client ID (hidden): ')
    env['SF_CLIENT_SECRET'] = env.get('SF_CLIENT_SECRET') or secret('OAuth client secret (hidden): ')
    env['SF_API_VERSION'] = env.get('SF_API_VERSION') or ask('Approved API version [v66.0]: ').strip() or 'v66.0'
    env.update(SF_CURRENCY='USD', SF_CURRENCY_CONFIRMED='true')
    username = ask('Choose a local dashboard username: ').strip()
    password = secret('Choose a local dashboard password (minimum 16 characters): ')
    confirm = secret('Repeat local dashboard password: ')
    if not username or len(password) < 16 or password != confirm:
        raise ValueError('Username is required and matching passwords must be at least 16 characters.')
    env['APP_USERS_JSON'] = json.dumps({username:generate_password_hash(password, method='pbkdf2:sha256')})
    env.pop('APP_USERS_FILE',None)
    return env

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8051)
    parser.add_argument('--cert',help='Optional local TLS certificate supplied by IT')
    parser.add_argument('--key',help='Private key for --cert')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535 or bool(args.cert) != bool(args.key):
        parser.error('Use a port from 1024 to 65535 and provide both --cert and --key, or neither.')
    if sys.version_info < (3,9):
        raise SystemExit('Use Python 3.9 or newer for this live-data launcher. See LOCAL-LIVE.md.')
    try:
        env = collect_settings()
        from salesforce import Repository, DataError
        repo = Repository('live',env)
        print('Validating Salesforce access and loading the full dataset...')
        repo.get()
        # Keep module-level app initialization consistent with the completed settings.
        os.environ.update(env)
        from app import create_app
        dashboard = create_app(env,repo)
        tls = (args.cert,args.key) if args.cert else 'adhoc'
        print(f'Live Salesforce checks passed. Open https://127.0.0.1:{args.port}')
        if not args.cert:
            print('The local browser certificate warning is expected for this temporary certificate.')
        print('Use the local username/password you just created. Stop with Control+C.')
        dashboard.run(host='127.0.0.1',port=args.port,ssl_context=tls,debug=False,use_reloader=False)
    except (ValueError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from None
    except KeyboardInterrupt:
        print('\nStopped.')
    except Exception as exc:
        from salesforce import DataError
        if isinstance(exc,DataError):
            raise SystemExit('Live connection could not be verified: '+str(exc)) from None
        raise SystemExit('Local startup failed ('+type(exc).__name__+'). Check the port and local TLS setup. Credentials have not been printed.') from None

if __name__ == '__main__':
    main()
