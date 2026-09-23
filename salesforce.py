"""Read-only Salesforce OAuth/REST adapter for complete dashboard snapshots."""
import concurrent.futures
import json
import math
import os
import re
import threading
import time
from datetime import datetime
from decimal import Decimal
from urllib.parse import urlencode, urlparse
import requests
from config import FAMILIES

class DataError(Exception):
    pass

# Corporate currency conversion rates (SFSD-33860), expressed as units of currency per
# 1 USD -- the same convention as Salesforce's CurrencyType.ConversionRate. To convert an
# amount FROM this currency TO USD, divide by the rate.
FX_RATE_PER_USD = {
    'USD': 1.0,         # U.S. Dollar
    'AUD': 1.404307,    # Australian Dollar
    'BRL': 5.144215,    # Brazilian Real
    'CAD': 1.39957,     # Canadian Dollar
    'CHF': 0.82272,     # Swiss Franc
    'CNY': 6.746,       # Chinese Yuan
    'CZK': 21.207277,   # Czech Koruna
    'EUR': 0.87124,     # Euro
    'GBP': 0.746893,    # British Pound
    'IDR': 17818.00,    # Indonesian Rupiah
    'INR': 96.001,      # Indian Rupee
    'JPY': 157.015,     # Japanese Yen
    'MXN': 17.2323,     # Mexican Peso
    'MYR': 3.9235,      # Malaysian Ringgit
    'NZD': 1.747855,    # New Zealand Dollar
    'PLN': 3.7998,      # Polish Zloty
    'SEK': 9.839509,    # Swedish Krona
    'SGD': 1.276125,    # Singapore Dollar
    'THB': 33.345,      # Thai Baht
    'ZAR': 16.25585,    # South African Rand
}

def check_id(value, nullable=False):
    if value is None and nullable:
        return value
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9]{15}(?:[A-Za-z0-9]{3})?', value):
        raise DataError('Invalid Salesforce record identifier')
    return value

def text(value, nullable=False):
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        raise DataError('Unexpected field type')
    return value

def boolean(value):
    if type(value) is not bool:
        raise DataError('Expected Boolean field')
    return value

# The official "QAD | Redzone - Insights - CoM FY27" Salesforce dashboard (Public Dashboards
# folder), replicated on the app's Home tab using its own live, pre-computed report results.
DASHBOARD_ID = '01ZTR00000ECX6b2AH'

def quill_runs(rich_text_json):
    # Parses a Quill Delta-style rich text note into plain runs of text with bold/underline
    # flags, dropping formatting we don't render (font size, alignment, etc).
    try:
        ops = json.loads(rich_text_json or '[]')
    except ValueError:
        return []
    if not isinstance(ops, list):
        return []
    runs = []
    for op in ops:
        if not isinstance(op, dict):
            continue
        insert = op.get('insert')
        if not isinstance(insert, str) or insert.strip() in ('', '\n'):
            continue
        attrs = op.get('attributes') if isinstance(op.get('attributes'), dict) else {}
        runs.append(dict(text=insert, bold=bool(attrs.get('bold')), underline=bool(attrs.get('underline'))))
    return runs

def is_qad_owned(*names):
    # QAD's own accounts/employees must never appear in registration, engagement, or account
    # reporting -- matches 'QAD', 'QAD Inc.', 'QAD Is/Esc', 'QAD User Groups', 'QAD | Redzone', etc.
    return any(str(n or '').strip().lower().startswith('qad') for n in names)

def number(value, nullable=False, integer=False):
    if value is None and nullable:
        return None
    if type(value) not in (int, float, Decimal) or not math.isfinite(value):
        raise DataError('Expected numeric field')
    if integer and (value < 0 or int(value) != value):
        raise DataError('Expected nonnegative count')
    return int(value) if integer else value

def source_date(value):
    text(value)
    # Salesforce returns offsets like '+0000' (no colon); Python's fromisoformat before 3.11
    # only accepts '+00:00'. Normalize so validation works under the supported 3.9+ runtimes.
    normalized = re.sub(r'([+-]\d{2})(\d{2})$', r'\1:\2', value.replace('Z', '+00:00'))
    try:
        datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise DataError('Invalid source date') from exc
    return value

class Salesforce:
    def __init__(self, environ=None, session=None):
        e = os.environ if environ is None else environ
        self.origin = e.get('SF_ORIGIN', '').rstrip('/')
        self.client_id = e.get('SF_CLIENT_ID', '')
        self.secret = e.get('SF_CLIENT_SECRET', '')
        self.version = e.get('SF_API_VERSION', 'v66.0')
        self.multi = e.get('SF_MULTI_CURRENCY', 'false') == 'true'
        u = urlparse(self.origin)
        if (u.scheme != 'https' or not u.hostname or not u.hostname.endswith('.my.salesforce.com')
                or u.username or u.password or u.port or u.path or u.query or u.fragment
                or not self.client_id or not self.secret or not re.fullmatch(r'v\d{2,3}\.0', self.version)):
            raise DataError('Salesforce connection settings are incomplete or invalid')
        if e.get('SF_CURRENCY') != 'USD' or e.get('SF_CURRENCY_CONFIRMED') != 'true':
            raise DataError('Confirm that the original USD financial presentation is valid before enabling live mode')
        if session:
            self.http = session
        else:
            self.http = requests.Session()
            # load() fires batched queries concurrently; widen the pool so those requests
            # get their own connections instead of queuing behind the default size of 10.
            adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
            self.http.mount('https://', adapter)
        self.token = None
        self.deadline = time.monotonic() + 50

    def request(self, path, **kwargs):
        if not path.startswith('/services/') or path.startswith('//'):
            raise DataError('Invalid upstream path')
        for attempt in range(3):
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise DataError('Salesforce collection timed out')
            try:
                response = self.http.request(url=self.origin + path, timeout=min(8, remaining), allow_redirects=False, **kwargs)
            except requests.RequestException:
                if attempt == 2:
                    raise DataError('Salesforce is temporarily unavailable') from None
                time.sleep(.3 * (attempt + 1))
                continue
            if response.status_code == 429 or response.status_code >= 500:
                response.close()
                if attempt == 2:
                    raise DataError('Salesforce is busy; please retry')
                time.sleep(.3 * (attempt + 1))
                continue
            if 300 <= response.status_code < 400:
                raise DataError('Unexpected Salesforce redirect')
            return response
        raise DataError('Salesforce request failed')

    def login(self):
        response = self.request('/services/oauth2/token', method='POST', data=dict(grant_type='client_credentials', client_id=self.client_id, client_secret=self.secret))
        if response.status_code != 200:
            raise DataError('Salesforce authentication failed; check the integration user and OAuth app')
        try:
            data = response.json()
            if data['instance_url'].rstrip('/') != self.origin:
                raise DataError('Salesforce returned a different instance origin')
            self.token = text(data['access_token'])
            if not self.token:
                raise DataError('Missing access token')
        except (ValueError, KeyError, TypeError):
            raise DataError('Invalid authentication response') from None

    def query(self, soql):
        if not self.token:
            self.login()
        path = f'/services/data/{self.version}/query?' + urlencode({'q': soql})
        rows, visited, expected = [], set(), None
        while path:
            if path in visited or len(visited) >= 100:
                raise DataError('Invalid pagination or dataset too large')
            visited.add(path)
            response = self.request(path, method='GET', headers={'Authorization': 'Bearer ' + self.token})
            if response.status_code == 401:
                self.login()
                response = self.request(path, method='GET', headers={'Authorization': 'Bearer ' + self.token})
            if response.status_code != 200:
                raise DataError('Salesforce query failed; check object access and field mappings')
            try:
                data = response.json()
                total = number(data['totalSize'], integer=True)
                done = boolean(data['done'])
                if not isinstance(data['records'], list):
                    raise DataError('Invalid records response')
                if expected is None:
                    expected = total
                if expected != total or total > 20000:
                    raise DataError('Invalid or oversized Salesforce result')
                rows.extend(data['records'])
                if len(rows) > 20000:
                    raise DataError('Dataset exceeds the 20,000-row safety limit')
                if done:
                    if len(rows) != expected:
                        raise DataError('Incomplete Salesforce results; partial totals are not displayed')
                    break
                path = data['nextRecordsUrl']
                if not re.fullmatch(r'/services/data/' + re.escape(self.version) + r'/query/[A-Za-z0-9_-]+', path):
                    raise DataError('Invalid Salesforce pagination URL')
            except (ValueError, KeyError, TypeError):
                raise DataError('Invalid Salesforce query response') from None
        return rows

    def authed_get(self, path):
        if not self.token:
            self.login()
        response = self.request(path, method='GET', headers={'Authorization': 'Bearer ' + self.token})
        if response.status_code == 401:
            self.login()
            response = self.request(path, method='GET', headers={'Authorization': 'Bearer ' + self.token})
        if response.status_code != 200:
            raise DataError('Salesforce dashboard fetch failed')
        try:
            return response.json()
        except ValueError:
            raise DataError('Invalid Salesforce dashboard response') from None

    def dashboard_snapshot(self, dashboard_id):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            status_future = pool.submit(self.authed_get, f'/services/data/{self.version}/analytics/dashboards/{dashboard_id}')
            describe_future = pool.submit(self.authed_get, f'/services/data/{self.version}/analytics/dashboards/{dashboard_id}/describe')
            status = status_future.result()
            describe = describe_future.result()
        try:
            components = describe['components']
            component_data = status['componentData']
            if not isinstance(components, list) or not isinstance(component_data, list) or len(components) != len(component_data):
                raise DataError('Dashboard component mismatch')
            def color_breaks(props):
                breaks = ((props.get('visualizationProperties') or {}).get('breakPoints') or [{}])[0].get('breaks') or []
                return [dict(color='#' + b['color'], lowerBound=number(b['lowerBound'], True) if b.get('lowerBound') is not None else None,
                             upperBound=number(b['upperBound'], True) if b.get('upperBound') is not None else None) for b in breaks]
            notes, metrics, bars, gauges = [], [], [], []
            for meta, data in zip(components, component_data):
                props = meta.get('properties') or {}
                viz = props.get('visualizationType')
                header = text(meta.get('header'), True) or ''
                if viz == 'RichText':
                    notes.append(quill_runs((props.get('content') or {}).get('richTextContent')))
                    continue
                if not data:
                    continue
                fact_map = data['reportResult']['factMap']
                if viz == 'Metric':
                    entry = ((fact_map.get('T!T') or {}).get('aggregates') or [{}])[0]
                    metrics.append(dict(header=header, value=number(entry.get('value'), True), label=text(entry.get('label'), True), breaks=color_breaks(props)))
                elif viz == 'Bar':
                    groupings = data['reportResult']['groupingsDown']['groupings']
                    groups = []
                    for g in groupings:
                        entry = ((fact_map.get(g['key'] + '!T') or {}).get('aggregates') or [{}])[0]
                        groups.append(dict(label=text(g['label']), value=number(entry.get('value'), True) or 0, valueLabel=text(entry.get('label'), True)))
                    bars.append(dict(header=header, groups=groups))
                elif viz == 'Gauge':
                    entry = ((fact_map.get('T!T') or {}).get('aggregates') or [{}])[0]
                    breaks = color_breaks(props)
                    green = next((b for b in breaks if b['color'] == '#00716b'), None)
                    gauges.append(dict(header=header, value=number(entry.get('value'), True), label=text(entry.get('label'), True),
                                        target=green['lowerBound'] if green else None, breaks=breaks))
            return dict(notes=notes, metrics=metrics, bars=bars, gauges=gauges)
        except (KeyError, TypeError, IndexError) as exc:
            raise DataError('Invalid Salesforce dashboard response') from exc

    def load(self):
        from campaigns import build_config, etm_owners
        sessions = self.query("SELECT Id, Name FROM Campaign WHERE ParentId = '701TR00000tTIebYAG' AND (Name LIKE '%BR Session%' OR Name LIKE '%TH Session%')")
        for row in sessions:
            check_id(row['Id']); text(row['Name'])
        cfg = build_config(sessions)
        ids = ','.join("'" + c['id'] + "'" for c in cfg['campaigns'])
        def restrictions(prefix=''):
            return (f"{prefix}Category__c IN ('Solutions','Services') AND {prefix}OwnerId != '00530000000lVx8AAE' AND {prefix}Type != 'Admin $0' AND {prefix}Substage__c != 'Closed-Duplicate' " + ' '.join(f"AND (NOT {prefix}Name LIKE '%{word}%')" for word in ('DEBOOK','DE-BOOK','DE BOOK','Amendment','Renewal')))
        fields = ['Id', 'CampaignId', 'Solutions_Rev_ACV_Net__c', 'IsWon', 'Reached_S_Status__c']
        if self.multi:
            fields.append('CurrencyIsoCode')
        # These queries are independent of each other (the dashboard snapshot doesn't depend
        # on campaign ids at all), so run them concurrently instead of waiting on each in turn.
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            opps_future = pool.submit(self.query, 'SELECT ' + ','.join(fields) + f' FROM Opportunity WHERE CampaignId IN ({ids}) AND ' + restrictions() + ' ORDER BY Id')
            influence_future = pool.submit(self.query, 'SELECT Id,CampaignId,OpportunityId,' + ','.join('Opportunity.' + f for f in fields) + f' FROM CampaignInfluence WHERE CampaignId IN ({ids}) AND ' + restrictions('Opportunity.') + ' ORDER BY Id')
            members_future = pool.submit(self.query, 'SELECT Id,ContactId,LeadId,FirstName,LastName,Title,Email,CompanyOrAccount,CampaignId,Status,HasResponded,CreatedDate,Contact.Name,Contact.Email,Contact.Title,Contact.AccountId,Contact.Account.Name FROM CampaignMember WHERE CampaignId IN (' + ids + ') ORDER BY Id')
            dashboard_future = pool.submit(self.dashboard_snapshot, DASHBOARD_ID)
            opps = opps_future.result()
            influence = influence_future.result()
            members = members_future.result()
            sf_dashboard = dashboard_future.result()
        def opportunity(row):
            acv = number(row['Solutions_Rev_ACV_Net__c'], True)
            if self.multi:
                rate = FX_RATE_PER_USD.get(row['CurrencyIsoCode'])
                if rate is None:
                    raise DataError('Unsupported currency; the FX conversion table needs updating')
                if acv is not None:
                    acv = round(acv / rate, 2)
            return dict(id=check_id(row['Id']), campaignId=check_id(row['CampaignId'], True), acv=acv, isWon=boolean(row['IsWon']), saHit=boolean(row['Reached_S_Status__c']))
        result = dict(campaigns=[], sourcedOpps=[opportunity(row) for row in opps], influence=[], rows=[], sessions=sessions, etmOwners={}, sfDashboard=sf_dashboard)
        for row in influence:
            o = opportunity(row['Opportunity'])
            result['influence'].append(dict(ic=check_id(row['CampaignId']), oi=check_id(row['OpportunityId']), pc=o['campaignId'], acv=o['acv'], won=o['isWon'], sa=o['saHit']))
        for row in members:
            contact = row.get('Contact') or {}
            cid, lid = check_id(row['ContactId'], True), check_id(row['LeadId'], True)
            if not (cid or lid):
                raise DataError('Campaign membership has no person')
            account = contact.get('Account') or {}
            if is_qad_owned(account.get('Name'), row.get('CompanyOrAccount')):
                continue
            result['rows'].append(dict(id=check_id(row['Id']), cid=cid, lid=lid, name=' '.join(v for v in [text(row['FirstName'], True), text(row['LastName'], True)] if v) or '(no name)', title=text(row.get('Title'), True), email=text(row.get('Email'), True), company=text(row.get('CompanyOrAccount'), True), aid=check_id(contact.get('AccountId'), True), accountName=text(account.get('Name'), True), ctitle=text(contact.get('Title'), True), cname=text(contact.get('Name'), True), cemail=text(contact.get('Email'), True), camp=check_id(row['CampaignId']), st=text(row['Status']), hr=boolean(row['HasResponded']), cd=source_date(row['CreatedDate'])))
        if any(row['camp'] not in cfg['family'] for row in result['rows']) or any(row['campaignId'] not in cfg['family'] for row in result['sourcedOpps']) or any(row['ic'] not in cfg['family'] for row in result['influence']):
            raise DataError('Unexpected campaign in Salesforce source results')
        aids = sorted({r['aid'] for r in result['rows'] if r['aid']})
        def chunks(values):
            for start in range(0, len(values), 100):
                yield values[start:start + 100]
        attrs, associations, owners = [], [], []
        aid_batches = list(chunks(aids))
        if aid_batches:
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(20, len(aid_batches) * 2)) as pool:
                attr_futures, assoc_futures = [], []
                for batch in aid_batches:
                    quoted = ','.join("'" + check_id(v) + "'" for v in batch)
                    attr_futures.append(pool.submit(self.query, f'SELECT Id, Remote_Licensed__c FROM Account WHERE Id IN ({quoted})'))
                    assoc_futures.append(pool.submit(self.query, f'SELECT ObjectId, Territory2Id, Territory2.Name, Territory2.Territory2Type.MasterLabel, Territory2.Territory2Model.State FROM ObjectTerritory2Association WHERE ObjectId IN ({quoted})'))
                for future in attr_futures:
                    attrs += future.result()
                for future in assoc_futures:
                    associations += future.result()
        tids = sorted({check_id(r['Territory2Id']) for r in associations})
        tid_batches = list(chunks(tids))
        if tid_batches:
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(20, len(tid_batches))) as pool:
                owner_futures = []
                for batch in tid_batches:
                    quoted = ','.join("'" + check_id(v) + "'" for v in batch)
                    owner_futures.append(pool.submit(self.query, f"SELECT Territory2Id, UserId, User.Name, RoleInTerritory2 FROM UserTerritory2Association WHERE Territory2Id IN ({quoted}) AND IsActive = true AND RoleInTerritory2 IN ('AE','Channel Manager')"))
                for future in owner_futures:
                    owners += future.result()
        attr = {check_id(a['Id']): text(a.get('Remote_Licensed__c'), True) for a in attrs}
        result['etmOwners'] = {aid: etm_owners(aid, attr.get(aid), associations, owners) for aid in aids}
        return result

class Repository:
    def __init__(self, mode, environ=None, loader=None):
        if mode not in ('demo', 'live'):
            raise DataError('DATA_MODE must be demo or live')
        self.mode, self.environ, self.loader = mode, environ, loader
        self.lock, self.value, self.expires = threading.Lock(), None, 0
    def get(self):
        with self.lock:
            if self.value is not None and time.monotonic() < self.expires:
                return self.value
            data = self.loader() if self.loader else (__import__('demo').demo_data() if self.mode == 'demo' else Salesforce(self.environ).load())
            self.value, self.expires = data, time.monotonic() + 60
            return data
