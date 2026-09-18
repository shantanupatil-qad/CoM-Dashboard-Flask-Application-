"""Read-only BigQuery adapter for complete dashboard snapshots."""
import math
import os
import re
import threading
import time
from datetime import date as date_type, datetime
from decimal import Decimal

from config import FAMILIES


class DataError(Exception):
    pass


def check_id(value, nullable=False):
    if value is None and nullable:
        return value
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}", value):
        raise DataError("Invalid source record identifier")
    return value


def text(value, nullable=False):
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        raise DataError("Unexpected field type")
    return value


def boolean(value):
    if type(value) is not bool:
        raise DataError("Expected Boolean field")
    return value


def number(value, nullable=False, integer=False):
    if value is None and nullable:
        return None
    if type(value) not in (int, float, Decimal) or not math.isfinite(value):
        raise DataError("Expected numeric field")
    if integer and (value < 0 or int(value) != value):
        raise DataError("Expected nonnegative count")
    return int(value) if integer else value


def source_date(value):
    if isinstance(value, (datetime, date_type)):
        return value.isoformat()
    text(value)
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DataError("Invalid source date") from exc
    return value


class BigQuery:
    """Loads normalized dashboard tables using ADC or the configured GCP identity."""

    TABLE_ENV = {
        "campaigns": "BQ_CAMPAIGNS_TABLE",
        "opportunities": "BQ_OPPORTUNITIES_TABLE",
        "influence": "BQ_INFLUENCE_TABLE",
        "members": "BQ_MEMBERS_TABLE",
        "accounts": "BQ_ACCOUNTS_TABLE",
        "territories": "BQ_TERRITORIES_TABLE",
        "users": "BQ_USERS_TABLE",
    }

    def __init__(self, environ=None, client=None):
        env = os.environ if environ is None else environ
        self.project = env.get("BQ_PROJECT", "").strip()
        self.dataset = env.get("BQ_DATASET", "").strip()
        self.location = env.get("BQ_LOCATION") or None
        self.validate_config(env)
        self.tables = {}
        for key, variable in self.TABLE_ENV.items():
            value = (env.get(variable) or key).strip()
            if not re.fullmatch(r"[A-Za-z0-9_]{1,128}", value):
                raise DataError("Invalid BigQuery table setting")
            self.tables[key] = value
        if client is not None:
            self.client = client
        else:
            try:
                from google.cloud import bigquery
                self.client = bigquery.Client(project=self.project, location=self.location)
            except Exception as exc:
                raise DataError("BigQuery client initialization failed; configure Application Default Credentials") from exc
        self.deadline = time.monotonic() + 50

    @staticmethod
    def validate_config(environ=None):
        env = os.environ if environ is None else environ
        project = (env.get("BQ_PROJECT") or "").strip()
        dataset = (env.get("BQ_DATASET") or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", project) or not re.fullmatch(r"[A-Za-z0-9_]{1,128}", dataset):
            raise DataError("BigQuery project and dataset settings are incomplete or invalid")
        for variable in BigQuery.TABLE_ENV.values():
            value = (env.get(variable) or variable.removesuffix("_TABLE").lower()).strip()
            if not re.fullmatch(r"[A-Za-z0-9_]{1,128}", value):
                raise DataError("Invalid BigQuery table setting")

    def _table(self, name):
        return f"`{self.project}.{self.dataset}.{self.tables[name]}`"

    def query(self, sql, parameters=()):
        if time.monotonic() >= self.deadline:
            raise DataError("BigQuery collection timed out")
        try:
            job = self.client.query(sql, job_config=self._job_config(parameters), location=self.location)
            rows = list(job.result(timeout=max(1, self.deadline - time.monotonic())))
        except Exception as exc:
            raise DataError("BigQuery query failed; check table access and field mappings") from exc
        if len(rows) > 20000:
            raise DataError("Dataset exceeds the 20,000-row safety limit")
        return [dict(row.items()) for row in rows]

    @staticmethod
    def _job_config(parameters):
        if not parameters:
            return None
        try:
            from google.cloud import bigquery
            return bigquery.QueryJobConfig(query_parameters=list(parameters))
        except ImportError as exc:
            raise DataError("BigQuery client library is not installed") from exc

    @staticmethod
    def _ids(values):
        return ", ".join("'" + check_id(value).replace("'", "''") + "'" for value in values)

    def _campaign_ids(self, cfg):
        return [campaign["id"] for campaign in cfg["campaigns"]]

    def load(self):
        from campaigns import build_config, etm_owners

        parent_ids = [family["parentId"] for family in FAMILIES.values()]
        sessions = self.query(
            f"SELECT id AS Id, name AS Name FROM {self._table('campaigns')} "
            f"WHERE parent_id IN ({self._ids(parent_ids)}) "
            "AND (LOWER(name) LIKE '%br session%' OR LOWER(name) LIKE '%th session%')"
        )
        for row in sessions:
            check_id(row["Id"])
            text(row["Name"])
        cfg = build_config(sessions)
        ids = self._ids(self._campaign_ids(cfg))
        opps = self.query(f"SELECT * FROM {self._table('opportunities')} WHERE campaign_id IN ({ids})")
        influence = self.query(f"SELECT * FROM {self._table('influence')} WHERE campaign_id IN ({ids})")
        members = self.query(f"SELECT * FROM {self._table('members')} WHERE campaign_id IN ({ids})")

        def opportunity(row):
            return dict(id=check_id(row["id"]), campaignId=check_id(row.get("campaign_id"), True),
                        acv=number(row.get("acv"), True), isWon=boolean(row["is_won"]),
                        saHit=boolean(row["sa_hit"]))

        result = dict(campaigns=[], sourcedOpps=[opportunity(row) for row in opps], influence=[], rows=[], sessions=sessions, etmOwners={})
        for row in influence:
            opportunity_row = opportunity(dict(id=row["opportunity_id"], campaign_id=row.get("primary_campaign_id"),
                                                acv=row.get("acv"), is_won=row["is_won"], sa_hit=row["sa_hit"]))
            result["influence"].append(dict(ic=check_id(row["campaign_id"]), oi=check_id(row["opportunity_id"]),
                                            pc=opportunity_row["campaignId"], acv=opportunity_row["acv"],
                                            won=opportunity_row["isWon"], sa=opportunity_row["saHit"]))
        for row in members:
            cid, lid = check_id(row.get("contact_id"), True), check_id(row.get("lead_id"), True)
            if not (cid or lid):
                raise DataError("Campaign membership has no person")
            result["rows"].append(dict(
                id=check_id(row["id"]), cid=cid, lid=lid,
                name=" ".join(value for value in (text(row.get("first_name"), True), text(row.get("last_name"), True)) if value) or "(no name)",
                title=text(row.get("title"), True), email=text(row.get("email"), True), company=text(row.get("company"), True),
                aid=check_id(row.get("account_id"), True), accountName=text(row.get("account_name"), True),
                ctitle=text(row.get("contact_title"), True), cname=text(row.get("contact_name"), True),
                cemail=text(row.get("contact_email"), True), camp=check_id(row["campaign_id"]),
                st=text(row["status"]), hr=boolean(row["has_responded"]), cd=source_date(row["created_date"])))
        if any(row["camp"] not in cfg["family"] for row in result["rows"]):
            raise DataError("Unexpected campaign in BigQuery member results")
        account_ids = sorted({row["aid"] for row in result["rows"] if row["aid"]})
        if account_ids:
            account_rows = self.query(f"SELECT id, remote_licensed FROM {self._table('accounts')} WHERE id IN ({self._ids(account_ids)})")
            associations = self.query(f"SELECT * FROM {self._table('territories')} WHERE object_id IN ({self._ids(account_ids)})")
            territory_ids = sorted({check_id(row["territory_id"]) for row in associations})
            owners = self.query(f"SELECT * FROM {self._table('users')} WHERE territory_id IN ({self._ids(territory_ids)}) AND is_active = TRUE") if territory_ids else []
            eligible = {check_id(row["id"]): text(row.get("remote_licensed"), True) for row in account_rows}
            result["etmOwners"] = {account_id: etm_owners(account_id, eligible.get(account_id), associations, owners) for account_id in account_ids}
        return result


class Repository:
    """One complete snapshot per process. Failed refreshes never publish partial results."""
    def __init__(self, mode, environ=None, loader=None):
        if mode not in ("demo", "live"):
            raise DataError("DATA_MODE must be demo or live")
        self.mode, self.environ, self.loader = mode, environ, loader
        self.lock, self.value, self.expires = threading.Lock(), None, 0

    def get(self):
        with self.lock:
            if self.value is not None and time.monotonic() < self.expires:
                return self.value
            if self.loader:
                data = self.loader()
            elif self.mode == "demo":
                from demo import demo_data
                data = demo_data()
            else:
                data = BigQuery(self.environ).load()
            self.value, self.expires = data, time.monotonic() + 60
            return data
