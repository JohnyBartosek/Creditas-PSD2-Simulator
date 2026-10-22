"""Oracle connection for the Datasheets tool."""

import os
import re
from datetime import date, datetime
from pathlib import Path

from Helpers.environment_config import PROJECT_ROOT, load_db_config

REQUEST_EVENT_FIELDS = (
    "id",
    "code",
    "xrequestid",
    "tppid",
    "tppname",
    "psd2licencenumber",
    "psd2serviceflag",
    "psd2endpoint",
    "partyid",
    "userinvolvedflag",
    "country",
    "started",
    "ended",
    "resultflag",
    "errordescription",
    "requestduration",
    "paymentid",
    "valid_from",
    "valid_to",
    "valid",
    "hst_created_date",
    "hst_created_by",
    "hst_modified_date",
    "hst_modified_by",
    "standingorderid",
    "accountid",
)
_OK_RESULTS = {"Y", "YES", "1", "OK", "TRUE", "SUCCESS", "S"}
_FAILED_RESULTS = {"N", "NO", "0", "ERROR", "FALSE", "FAIL", "FAILED", "E", "F"}
_DURATION = re.compile(
    r"^P(?:(?P<days>\d+(?:\.\d+)?)D)?"
    r"(?:T(?:(?P<hours>\d+(?:\.\d+)?)H)?(?:(?P<minutes>\d+(?:\.\d+)?)M)?(?:(?P<seconds>\d+(?:\.\d+)?)S)?)?$",
    re.IGNORECASE,
)
_REQUEST_COLUMNS = """
SELECT ID, CODE, XREQUESTID, TPPID, TPPNAME, PSD2LICENCENUMBER, PSD2SERVICEFLAG,
       PSD2ENDPOINT, PARTYID, USERINVOLVEDFLAG, COUNTRY, STARTED, ENDED, RESULTFLAG,
       ERRORDESCRIPTION, REQUESTDURATION, PAYMENTID, VALID_FROM, VALID_TO, VALID,
       HST_CREATED_DATE, HST_CREATED_BY, HST_MODIFIED_DATE, HST_MODIFIED_BY,
       STANDINGORDERID, ACCOUNTID
FROM PSD.MCH_OAM_REQUESTEVENTPSD
WHERE STARTED >= :started_from AND STARTED <= :started_to
"""
_STATS_SQL = """
SELECT COUNT(*) AS total,
       SUM(CASE WHEN LOWER(RESULTFLAG) = 'success' THEN 1 ELSE 0 END) AS ok_count,
       SUM(CASE WHEN LOWER(RESULTFLAG) = 'error' THEN 1 ELSE 0 END) AS error_count,
       COUNT(DISTINCT TPPNAME) AS tpp_count
FROM PSD.MCH_OAM_REQUESTEVENTPSD
WHERE STARTED >= :started_from AND STARTED <= :started_to
"""

_CLIENT_ROOT = PROJECT_ROOT / "ThirdParty" / "instantclient"


def _oracle_client_lib_dir() -> Path | None:
    """Directory that contains oci.dll, if Instant Client is installed locally."""
    configured = os.environ.get("ORACLE_CLIENT_LIB_DIR", "").strip()
    candidates = []
    if configured:
        candidates.append(Path(configured))
    candidates.append(_CLIENT_ROOT)
    candidates.append(_CLIENT_ROOT.parent)
    for candidate in candidates:
        if (candidate / "oci.dll").is_file():
            return candidate
        if candidate.is_dir():
            nested = sorted(candidate.glob("instantclient*/oci.dll"))
            if nested:
                return nested[-1].parent
    return None


def _enable_thick_mode() -> None:
    """
    The ITG database requires native network encryption. python-oracledb can
    do that only in thick mode, which loads Oracle Instant Client.
    """
    import oracledb

    if not oracledb.is_thin_mode():
        return

    lib_dir = _oracle_client_lib_dir()
    if lib_dir is None:
        raise RuntimeError(
            "This database requires Oracle native network encryption. "
            f"Install Instant Client so that oci.dll is in {_CLIENT_ROOT}."
        )
    try:
        oracledb.init_oracle_client(lib_dir=str(lib_dir))
    except Exception as exc:
        message = str(exc)
        if "thin mode" in message.lower():
            raise RuntimeError(
                "Restart the application. Thick mode has to start before the first database connection."
            ) from exc
        raise


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    read = getattr(value, "read", None)
    if callable(read):
        data = read()
        if isinstance(data, bytes):
            return data.decode("utf-8", errors="replace")
        return "" if data is None else str(data)
    return str(value)


def format_duration(value: str) -> str:
    """Turn an ISO-8601 duration such as PT1.035S into a short readable value."""
    text = str(value or "").strip()
    if not text:
        return ""
    match = _DURATION.match(text)
    if not match or not text.upper().startswith("P"):
        return text
    days = float(match.group("days") or 0)
    hours = float(match.group("hours") or 0)
    minutes = float(match.group("minutes") or 0)
    seconds = float(match.group("seconds") or 0)
    total = days * 86400 + hours * 3600 + minutes * 60 + seconds
    if total < 1:
        return f"{total * 1000:.0f} ms"
    if total < 60:
        shown = f"{total:.3f}".rstrip("0").rstrip(".")
        return f"{shown} s"
    if total < 3600:
        whole = int(total // 60)
        rest = total - whole * 60
        rest_text = f"{rest:.1f}".rstrip("0").rstrip(".")
        return f"{whole} min {rest_text} s"
    whole_hours = int(total // 3600)
    whole_minutes = int((total % 3600) // 60)
    rest = total % 60
    return f"{whole_hours} h {whole_minutes} min {rest:.0f} s"


def _tone(result: str, error: str) -> str:
    flag = result.strip().upper()
    if error.strip() or flag in _FAILED_RESULTS:
        return "error"
    if flag in _OK_RESULTS:
        return "ok"
    return ""


def blank_request_event() -> dict[str, str]:
    row = {name: "" for name in REQUEST_EVENT_FIELDS}
    row["index"] = ""
    row["tone"] = ""
    return row


def _require_config(environment: str | None = None) -> dict:
    config = load_db_config(environment)
    path = config["config_path"]
    if not config["configured"]:
        raise ValueError(f"Database connection is not configured. Create {path}.")
    missing = [
        name
        for name in ("host", "port", "database", "username")
        if not str(config.get(name) or "").strip()
    ]
    if missing:
        raise ValueError(f"{path} is missing: {', '.join(missing)}.")
    if not str(config.get("password") or ""):
        raise ValueError(f"Password is empty. Fill it in {path}.")
    try:
        port = int(config["port"])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Port in {path} is not a number.") from exc
    config["port_number"] = port
    return config


def _connect(config: dict):
    try:
        import oracledb
    except ImportError as exc:
        raise RuntimeError("Python package 'oracledb' is not installed.") from exc

    _enable_thick_mode()
    dsn = oracledb.makedsn(config["host"], config["port_number"], service_name=config["database"])
    try:
        return oracledb.connect(
            user=config["username"],
            password=config["password"],
            dsn=dsn,
            tcp_connect_timeout=15,
        )
    except oracledb.DatabaseError as exc:
        if "ORA-02391" in str(exc):
            raise RuntimeError(
                "ORA-02391: this account has reached its simultaneous session limit. "
                "Close other connections to this database and try again."
            ) from exc
        raise


def test_db_connection(environment: str | None = None) -> str:
    """Open the configured Oracle database and return who the session belongs to."""
    config = _require_config(environment)
    connection = _connect(config)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT USER FROM DUAL")
            row = cursor.fetchone()
    finally:
        connection.close()

    user = row[0] if row else config["username"]
    return f"Connected as {user}."


def _rows_from_cursor(cursor) -> list[dict[str, str]]:
    columns = [item[0].lower() for item in cursor.description]
    rows = []
    for record in cursor:
        item = blank_request_event()
        for name, value in zip(columns, record):
            if name in item:
                item[name] = _cell(value)
        item["requestduration"] = format_duration(item["requestduration"])
        item["tone"] = _tone(item["resultflag"], item["errordescription"])
        rows.append(item)
    return rows


def fetch_request_page(
    environment: str | None,
    started_from: datetime,
    started_to: datetime,
    limit: int = 25,
    before_started: datetime | None = None,
    before_id: str | None = None,
    include_stats: bool = True,
) -> dict:
    """One page of request events inside a start-time window, newest first."""
    size = max(1, min(int(limit), 200))
    config = _require_config(environment)
    binds: dict = {"started_from": started_from, "started_to": started_to}
    cursor_sql = ""
    if before_started is not None and before_id not in (None, ""):
        cursor_sql = """
          AND (
            STARTED < :before_started
            OR (STARTED = :before_started AND ID < :before_id)
          )
        """
        binds["before_started"] = before_started
        ident = str(before_id).strip()
        if ident.endswith(".0"):
            ident = ident[:-2]
        try:
            binds["before_id"] = int(ident)
        except (TypeError, ValueError):
            binds["before_id"] = ident
    sql = (
        _REQUEST_COLUMNS
        + cursor_sql
        + " ORDER BY STARTED DESC NULLS LAST, ID DESC"
        + f" FETCH FIRST {size} ROWS ONLY"
    )
    connection = _connect(config)
    try:
        with connection.cursor() as cursor:
            stats = {"total": 0, "ok": 0, "error": 0, "tpps": 0}
            if include_stats:
                cursor.execute(_STATS_SQL, binds)
                total, ok_count, error_count, tpp_count = cursor.fetchone()
                stats = {
                    "total": int(total or 0),
                    "ok": int(ok_count or 0),
                    "error": int(error_count or 0),
                    "tpps": int(tpp_count or 0),
                }
            cursor.execute(sql, binds)
            rows = _rows_from_cursor(cursor)
        return {"rows": rows, "has_more": len(rows) == size, **stats}
    finally:
        connection.close()
