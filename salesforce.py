"""Read-only Salesforce OAuth/REST adapter for complete dashboard snapshots."""
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

# TEMPORARY placeholder FX rates, pending an approved conversion policy from finance/management
# (SFSD-33860). Replace PLACEHOLDER_FX_TO_USD with the agreed source/rates once confirmed.
PLACEHOLDER_FX_TO_USD = {'USD': 1.0, 'GBP': 1.27, 'EUR': 1.08}

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
        self.http = session or requests.Session()
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
        opps = self.query('SELECT ' + ','.join(fields) + f' FROM Opportunity WHERE CampaignId IN ({ids}) AND ' + restrictions() + ' ORDER BY Id')
        influence = self.query('SELECT Id,CampaignId,OpportunityId,' + ','.join('Opportunity.' + f for f in fields) + f' FROM CampaignInfluence WHERE CampaignId IN ({ids}) AND ' + restrictions('Opportunity.') + ' ORDER BY Id')
        members = self.query('SELECT Id,ContactId,LeadId,FirstName,LastName,Title,Email,CompanyOrAccount,CampaignId,Status,HasResponded,CreatedDate,Contact.Name,Contact.Email,Contact.Title,Contact.AccountId,Contact.Account.Name FROM CampaignMember WHERE CampaignId IN (' + ids + ') ORDER BY Id')
        def opportunity(row):
            acv = number(row['Solutions_Rev_ACV_Net__c'], True)
            if self.multi:
                rate = PLACEHOLDER_FX_TO_USD.get(row['CurrencyIsoCode'])
                if rate is None:
                    raise DataError('Unsupported currency; the placeholder conversion table needs updating')
                if acv is not None:
                    acv = round(acv * rate, 2)
            return dict(id=check_id(row['Id']), campaignId=check_id(row['CampaignId'], True), acv=acv, isWon=boolean(row['IsWon']), saHit=boolean(row['Reached_S_Status__c']))
        result = dict(campaigns=[], sourcedOpps=[opportunity(row) for row in opps], influence=[], rows=[], sessions=sessions, etmOwners={})
        for row in influence:
            o = opportunity(row['Opportunity'])
            result['influence'].append(dict(ic=check_id(row['CampaignId']), oi=check_id(row['OpportunityId']), pc=o['campaignId'], acv=o['acv'], won=o['isWon'], sa=o['saHit']))
        for row in members:
            contact = row.get('Contact') or {}
            cid, lid = check_id(row['ContactId'], True), check_id(row['LeadId'], True)
            if not (cid or lid):
                raise DataError('Campaign membership has no person')
            account = contact.get('Account') or {}
            result['rows'].append(dict(id=check_id(row['Id']), cid=cid, lid=lid, name=' '.join(v for v in [text(row['FirstName'], True), text(row['LastName'], True)] if v) or '(no name)', title=text(row.get('Title'), True), email=text(row.get('Email'), True), company=text(row.get('CompanyOrAccount'), True), aid=check_id(contact.get('AccountId'), True), accountName=text(account.get('Name'), True), ctitle=text(contact.get('Title'), True), cname=text(contact.get('Name'), True), cemail=text(contact.get('Email'), True), camp=check_id(row['CampaignId']), st=text(row['Status']), hr=boolean(row['HasResponded']), cd=source_date(row['CreatedDate'])))
        if any(row['camp'] not in cfg['family'] for row in result['rows']) or any(row['campaignId'] not in cfg['family'] for row in result['sourcedOpps']) or any(row['ic'] not in cfg['family'] for row in result['influence']):
            raise DataError('Unexpected campaign in Salesforce source results')
        aids = sorted({r['aid'] for r in result['rows'] if r['aid']})
        def chunks(values):
            for start in range(0, len(values), 100):
                yield values[start:start + 100]
        attrs, associations, owners = [], [], []
        for batch in chunks(aids):
            quoted = ','.join("'" + check_id(v) + "'" for v in batch)
            attrs += self.query(f'SELECT Id, Remote_Licensed__c FROM Account WHERE Id IN ({quoted})')
            associations += self.query(f'SELECT ObjectId, Territory2Id, Territory2.Name, Territory2.Territory2Type.MasterLabel, Territory2.Territory2Model.State FROM ObjectTerritory2Association WHERE ObjectId IN ({quoted})')
        tids = sorted({check_id(r['Territory2Id']) for r in associations})
        for batch in chunks(tids):
            quoted = ','.join("'" + check_id(v) + "'" for v in batch)
            owners += self.query(f"SELECT Territory2Id, UserId, User.Name, RoleInTerritory2 FROM UserTerritory2Association WHERE Territory2Id IN ({quoted}) AND IsActive = true AND RoleInTerritory2 IN ('AE','Channel Manager')")
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
