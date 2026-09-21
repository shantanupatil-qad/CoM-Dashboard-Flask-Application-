"""Python application, preserving the supplied dashboard's page structure."""
import json
import os
import secrets
from collections import defaultdict, deque
from threading import Lock
from time import monotonic
from dash import Dash, Input, Output, State, ALL, ctx
from dash.exceptions import PreventUpdate
from flask import request, Response
from werkzeug.security import check_password_hash, generate_password_hash
import views
from model import event_stats, people, accounts, page_items
from salesforce import Repository, Salesforce, DataError, check_id

SCOPES = ('campaign', 'person', 'account')

def initial_state():
    return dict(page=0, filter='', selected=None, contact=None, revision=0)

def validated_state(raw):
    if not isinstance(raw, dict):
        raise ValueError('Invalid view state')
    state = {key: raw.get(key, value) for key, value in initial_state().items()}
    for field in ('page', 'revision'):
        if type(state[field]) is not int or not 0 <= state[field] <= 10000:
            raise ValueError('Invalid view state')
    if not isinstance(state['filter'], str) or len(state['filter']) > 120:
        raise ValueError('Invalid filter')
    for field in ('selected', 'contact'):
        check_id(state[field], nullable=True)
    return state

def transition(raw, action, key='', term=''):
    state = validated_state(raw)
    if not isinstance(term, str) or len(term) > 120:
        raise ValueError('Invalid filter')
    if action in ('filter', 'clear'):
        state.update(page=0, filter=term.strip() if action == 'filter' else '', selected=None, contact=None)
        if action == 'clear':
            term = ''
    elif action == 'next':
        state['page'] = min(10000, state['page'] + 1)
    elif action == 'prev':
        state['page'] = max(0, state['page'] - 1)
    elif action == 'select':
        state.update(selected=check_id(key), contact=None)
    elif action == 'contact':
        state['contact'] = check_id(key)
    elif action == 'back':
        state.update(selected=None, contact=None)
    elif action == 'back-contact':
        state['contact'] = None
    elif action == 'retry':
        state['revision'] = (state['revision'] + 1) % 10001
    else:
        raise PreventUpdate
    return state, term

def render_view(scope, raw, repository):
    from campaigns import CURRENT, build_config
    data = repository.get()
    token = CURRENT.set(build_config(data.get('sessions', [])))
    try:
        return _render_view(scope, raw, repository)
    finally:
        CURRENT.reset(token)

def _render_view(scope, raw, repository):
    state = validated_state(raw)
    data = repository.get()
    if scope == 'campaign':
        return views.campaign_page(event_stats(data))
    items = people(data) if scope == 'person' else accounts(data)
    if state['selected']:
        field = 'id' if scope == 'person' else 'aid'
        selected = next((item for item in items if item[field] == state['selected']), None)
        if selected is None:
            raise DataError('The selected record is no longer available')
        if scope == 'person':
            return views.person_detail(selected)
        if state['contact']:
            contact = next((c for c in views.account_contacts(selected) if c['id'] == state['contact']), None)
            if contact is None:
                raise DataError('The selected contact is not available in this account')
            return views.person_detail(contact, 'account')
        return views.account_detail(selected)
    rows, has_next = page_items(items, state['page'], state['filter'],
                                ('name', 'email', 'company') if scope == 'person' else ('aname',))
    if scope == 'person':
        return views.person_table(rows, state['page'], has_next, state['filter'])
    return views.account_table(rows, state['page'], has_next, state['filter'])

def create_app(environ=None, repository=None):
    env = dict(os.environ if environ is None else environ)
    mode = env.get('DATA_MODE', 'demo')
    # Explicit, off-by-default carve-out for a local single-user demo; a real deployment
    # must not inherit "no login" just because DATA_MODE=live is set.
    require_auth = mode == 'live' and env.get('LIVE_ALLOW_NO_AUTH') != 'true'
    repo = repository or Repository(mode, env)
    users = {}
    if mode == 'live':
        Salesforce(env)  # Validate settings without an upstream call.
    if require_auth:
        try:
            if env.get('APP_USERS_JSON'):
                users = json.loads(env['APP_USERS_JSON'])
            else:
                with open(env['APP_USERS_FILE'], encoding='utf-8') as file:
                    users = json.load(file)
            if not isinstance(users, dict) or not users or any(not isinstance(k, str) or not isinstance(v, str) or not v.startswith(('scrypt:', 'pbkdf2:')) for k, v in users.items()):
                raise ValueError()
        except (KeyError, OSError, ValueError):
            raise RuntimeError('Live mode requires APP_USERS_JSON or APP_USERS_FILE with approved usernames and scrypt password hashes') from None
    app = Dash(__name__, suppress_callback_exceptions=True,
               title='Champions of Manufacturing — FY27' + (' (Sample data)' if mode == 'demo' else ''),
               update_title=None)
    server = app.server
    if env.get('TRUST_PROXY') == 'true':
        # Only set this when a single trusted reverse proxy (e.g. Cloud Run's own front end)
        # terminates TLS in front of this process; otherwise a client could spoof
        # X-Forwarded-Proto and bypass the HTTPS requirement below.
        from werkzeug.middleware.proxy_fix import ProxyFix
        server.wsgi_app = ProxyFix(server.wsgi_app, x_proto=1, x_for=1, x_host=1)
    server.config['MAX_CONTENT_LENGTH'] = 128 * 1024
    dummy_hash = generate_password_hash(secrets.token_urlsafe(24), method='pbkdf2:sha256') if users else ''
    attempts = defaultdict(deque)
    attempt_lock = Lock()

    @server.before_request
    def protect():
        if mode == 'live':
            if not request.is_secure:
                return Response('HTTPS is required', status=403)
        if require_auth:
            # Limit failed authentication attempts per trusted proxy/client address.
            address = request.remote_addr or 'unknown'
            now = monotonic()
            with attempt_lock:
                for key in list(attempts):
                    while attempts[key] and attempts[key][0] < now - 60:
                        attempts[key].popleft()
                    if not attempts[key]:
                        del attempts[key]
                if len(attempts.get(address, ())) >= 10:
                    return Response('Try again shortly', status=429, headers={'Retry-After': '60'})
            auth = request.authorization
            valid = auth is not None and auth.type == 'basic' and check_password_hash(users.get(auth.username, dummy_hash), auth.password or '') and auth.username in users
            if not valid:
                with attempt_lock:
                    attempts[address].append(now)
                return Response('Sign in required', status=401, headers={'WWW-Authenticate': 'Basic realm="QAD dashboard", charset="UTF-8"'})
        if request.method == 'POST':
            origin = request.headers.get('Origin')
            if request.headers.get('Sec-Fetch-Site') == 'cross-site' or (origin and origin.rstrip('/') != request.host_url.rstrip('/')):
                return Response('Invalid request origin', status=403)

    @server.after_request
    def headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'no-referrer'
        if mode == 'live':
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        return response

    @server.get('/healthz')
    def health():
        return {'status': 'ok', 'mode': mode}

    @server.get('/readyz')
    def readiness():
        if mode != 'live':
            return {'status': 'not_ready', 'reason': 'Live Salesforce mode is not enabled'}, 503
        try:
            repo.get()
            return {'status': 'ready', 'mode': 'live'}
        except DataError as exc:
            return {'status': 'not_ready', 'reason': str(exc)}, 503
        except Exception:
            return {'status': 'not_ready', 'reason': 'Salesforce validation failed'}, 503

    app.layout = views.layout
    @app.callback(Output('active-tab', 'data'),
                  *[Output(s+'-panel', 'style') for s in SCOPES],
                  *[Output('nav-'+s, 'style') for s in SCOPES],
                  *[Input('nav-'+s, 'n_clicks') for s in SCOPES], State('active-tab', 'data'))
    def navigate(*args):
        active = ctx.triggered_id.removeprefix('nav-') if ctx.triggered_id else args[-1]
        if active not in SCOPES:
            active = 'campaign'
        return [active] + [dict(display='block' if active == s else 'none') for s in SCOPES] + [views.nav_style(active == s) for s in SCOPES]

    def safe_render(scope, state):
        try:
            return render_view(scope, state, repo)
        except (DataError, ValueError) as exc:
            return views.error_box(str(exc), scope)
        except Exception:
            # No source records, credentials or exception payloads enter browser/logs.
            reference = secrets.token_hex(4)
            server.logger.error('Dashboard rendering failed; reference=%s', reference)
            return views.error_box('Unable to load data. Reference: '+reference, scope)

    @app.callback(Output('campaign-content', 'children'), Input('active-tab', 'data'), Input('campaign-state', 'data'), Input('live-poll', 'n_intervals'))
    def campaign_content(active, state, _ticks):
        if active != 'campaign':
            raise PreventUpdate
        return safe_render('campaign', state)

    @app.callback(Output('campaign-state', 'data'), Input({'scope':'campaign','action':ALL,'key':ALL}, 'n_clicks'), State('campaign-state', 'data'), prevent_initial_call=True)
    def campaign_retry(clicks, state):
        if not any(clicks):
            raise PreventUpdate
        return transition(state, 'retry')[0]

    def register(scope):
        @app.callback(Output(scope+'-state', 'data'), Output(scope+'-input', 'value'),
                      Input({'scope':scope,'action':ALL,'key':ALL}, 'n_clicks'), Input(scope+'-input', 'n_submit'),
                      State(scope+'-state', 'data'), State(scope+'-input', 'value'), prevent_initial_call=True)
        def interact(clicks, submits, state, term):
            triggered = ctx.triggered_id
            if isinstance(triggered, dict):
                # Ignore dynamic components inserted with zero clicks.
                if not any(entry.get('value') for entry in ctx.inputs_list[0] if entry.get('id') == triggered):
                    raise PreventUpdate
                action, key = triggered['action'], triggered['key']
            elif triggered == scope+'-input' and submits:
                action, key = 'filter', ''
            else:
                raise PreventUpdate
            try:
                return transition(state, action, key, term or '')
            except (ValueError, DataError):
                raise PreventUpdate

        @app.callback(Output(scope+'-content', 'children'), Output(scope+'-filter-wrap', 'style'), Output(scope+'-clear', 'style'),
                      Input(scope+'-state', 'data'), Input('active-tab', 'data'), Input('live-poll', 'n_intervals'))
        def content(state, active, _ticks):
            if active != scope:
                raise PreventUpdate
            try:
                checked = validated_state(state)
            except (ValueError, DataError):
                checked = initial_state()
            return (safe_render(scope, state), dict(display='none' if checked['selected'] else 'flex', gap=10, marginBottom=20, maxWidth=500),
                    dict(display='block' if checked['filter'] else 'none'))
    for scope in ('person', 'account'):
        register(scope)
    return app

app = create_app()
server = app.server
if __name__ == '__main__':
    print('Local dashboard: http://127.0.0.1:8050 — '+os.environ.get('DATA_MODE', 'demo')+' mode')
    app.run(host='127.0.0.1', port=8050, debug=False)
