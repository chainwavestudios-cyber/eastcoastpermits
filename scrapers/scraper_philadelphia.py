"""
Philadelphia L&I Permit Scraper
Uses the Philadelphia ArcGIS Feature Service — no JavaScript required.

Data returned per permit:
  - address + zip (full mailing address)
  - opa_owner (property owner name — the homeowner)
  - approvedscopeofwork (system size, panel model, inverter)
  - contractorname / contractoraddress1
  - status, issuedDate, propertyType (Residential/Commercial)

Phone/email NOT in permit data — enriched downstream via Apollo/Hunter.
"""

import requests
import logging
from datetime import datetime

log = logging.getLogger(__name__)

# Primary ArcGIS Feature Service URL
# NOTE: The old org ID (fLeGjb7u4uXqeF9q) was Philadelphia's original ArcGIS Online org.
# The dataset has been migrated — the current canonical layer is "LI PERMITS" on PHLmaps.
# Try the new URL first; falls back to CARTO if empty.
ARCGIS_URL = (
    'https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services'
    '/LI_PERMITS/FeatureServer/0/query'
)

# Official Philadelphia L&I permits via CARTO SQL API (OpenDataPhilly canonical source).
# Table name confirmed: li_permits  (https://phl.carto.com/api/v2/sql)
# Docs: https://opendataphilly.org/datasets/licenses-and-inspections-building-and-zoning-permits/
PHILLY_ODP_URL = 'https://phl.carto.com/api/v2/sql'
PHILLY_CARTO_TABLE = 'li_permits'


def _normalize_permit(p: dict, source: str) -> dict:
    """Normalize a raw permit attribute dict into the standard output shape."""
    issued = p.get('permitissuedate')
    # ArcGIS returns epoch milliseconds; CARTO returns ISO strings
    if isinstance(issued, (int, float)) and issued:
        issued = datetime.utcfromtimestamp(issued / 1000).strftime('%Y-%m-%d')
    elif isinstance(issued, str) and issued:
        issued = issued[:10]  # trim any time component

    address      = p.get('address', '') or ''
    zip_code     = p.get('zip', '') or ''
    full_address = f"{address}, Philadelphia, PA {zip_code}".strip(', ')

    return {
        'permitNumber':    p.get('permitnumber'),
        'address':         full_address,
        'streetAddress':   address,
        'zip':             zip_code,
        'description':     p.get('approvedscopeofwork') or p.get('typeofwork'),
        'status':          p.get('status'),
        'issuedDate':      issued,
        'ownerName':       p.get('opa_owner'),
        'opaAccountNum':   p.get('opa_account_num'),
        'contractorName':  p.get('contractorname'),
        'contractorAddr':  (p.get('contractoraddress1') or '').replace('\r\n', ', '),
        'propertyType':    p.get('commercialorresidential'),
        'councilDistrict': p.get('council_district'),
        'city':            'Philadelphia',
        'state':           'PA',
        'source':          source,
    }


def _scrape_via_arcgis(start_date: str, end_date: str) -> list:
    """
    Primary path: Philadelphia ArcGIS Feature Service.
    Returns (permits_list, success_bool).
    """
    start_ts = f"{start_date} 00:00:00"
    end_ts   = f"{end_date} 23:59:59"

    where = (
        f"permittype = 'ELECTRICAL' "
        f"AND permitissuedate >= '{start_ts}' "
        f"AND permitissuedate <= '{end_ts}' "
        f"AND ("
        f"approvedscopeofwork LIKE '%solar%' OR "
        f"approvedscopeofwork LIKE '%photovoltaic%' OR "
        f"approvedscopeofwork LIKE '%pv system%' OR "
        f"approvedscopeofwork LIKE '%pv module%' OR "
        f"typeofwork LIKE '%solar%'"
        f")"
    )

    out_fields = (
        'permitnumber,address,zip,permittype,typeofwork,approvedscopeofwork,'
        'status,permitissuedate,commercialorresidential,'
        'opa_owner,opa_account_num,'
        'contractorname,contractoraddress1,'
        'council_district,censustract'
    )

    permits   = []
    offset    = 0
    page_size = 1000

    while True:
        params = {
            'where':             where,
            'outFields':         out_fields,
            'f':                 'json',
            'resultRecordCount': page_size,
            'resultOffset':      offset,
            'orderByFields':     'permitissuedate DESC',
        }

        try:
            resp = requests.get(ARCGIS_URL, params=params, timeout=30)
            resp.raise_for_status()

            raw = resp.text.strip()
            if not raw:
                log.error('[Philadelphia/ArcGIS] Empty response body (HTTP %s). '
                          'The service URL may have moved.', resp.status_code)
                return permits, False

            if not raw.startswith('{'):
                log.error('[Philadelphia/ArcGIS] Non-JSON response (first 500 chars): %s',
                          raw[:500])
                return permits, False

            data = resp.json()

            if 'error' in data:
                log.error('[Philadelphia/ArcGIS] API error payload: %s', data['error'])
                return permits, False

            features = data.get('features', [])
            if not features:
                break  # Normal end-of-pages

            for f in features:
                permits.append(_normalize_permit(f.get('attributes', {}),
                                                 source='philadelphia_arcgis'))

            log.info('[Philadelphia/ArcGIS] offset=%d fetched=%d total=%d',
                     offset, len(features), len(permits))

            if len(features) < page_size:
                break
            offset += page_size

        except requests.exceptions.RequestException as e:
            log.error('[Philadelphia/ArcGIS] Request failed: %s', e)
            return permits, False
        except ValueError as e:
            log.error('[Philadelphia/ArcGIS] JSON parse error: %s', e)
            return permits, False
        except Exception as e:
            log.error('[Philadelphia/ArcGIS] Unexpected error: %s', e)
            return permits, False

    return permits, True


def _scrape_via_carto(start_date: str, end_date: str) -> list:
    """
    Fallback path: Philadelphia Open Data via CARTO SQL API.
    Same underlying permit dataset, different endpoint.
    """
    log.info('[Philadelphia/CARTO] Falling back to CARTO endpoint')

    sql = (
        "SELECT permitnumber, address, zip, permittype, typeofwork, "
        "approvedscopeofwork, status, permitissuedate, "
        "commercialorresidential, opa_owner, opa_account_num, "
        "contractorname, contractoraddress1, council_district "
        f"FROM {PHILLY_CARTO_TABLE} "
        "WHERE permittype = 'ELECTRICAL' "
        f"AND permitissuedate >= '{start_date}' "
        f"AND permitissuedate <= '{end_date} 23:59:59' "
        "AND ("
        "approvedscopeofwork ILIKE '%solar%' OR "
        "approvedscopeofwork ILIKE '%photovoltaic%' OR "
        "approvedscopeofwork ILIKE '%pv system%' OR "
        "approvedscopeofwork ILIKE '%pv module%' OR "
        "typeofwork ILIKE '%solar%'"
        ") "
        "ORDER BY permitissuedate DESC "
        "LIMIT 5000"
    )

    try:
        resp = requests.get(PHILLY_ODP_URL, params={'q': sql, 'format': 'json'},
                            timeout=30)
        resp.raise_for_status()

        raw = resp.text.strip()
        if not raw or not raw.startswith('{'):
            log.error('[Philadelphia/CARTO] Unexpected response: %s', raw[:300])
            return []

        data = resp.json()
        rows = data.get('rows', [])
        permits = [_normalize_permit(r, source='philadelphia_carto') for r in rows]
        log.info('[Philadelphia/CARTO] fetched=%d', len(permits))
        return permits

    except Exception as e:
        log.error('[Philadelphia/CARTO] Failed: %s', e)
        return []


def scrape_philadelphia_api(start_date: str, end_date: str) -> list:
    """
    Scrape Philadelphia solar electrical permits.

    Tries the ArcGIS Feature Service first; if that returns empty/error,
    falls back to the Philadelphia Open Data CARTO endpoint.

    Args:
        start_date: 'YYYY-MM-DD'
        end_date:   'YYYY-MM-DD'

    Returns:
        List of solar permit dicts ready for Base44 ingest.
    """
    log.info('[Philadelphia] Scraping %s to %s', start_date, end_date)

    permits, arcgis_ok = _scrape_via_arcgis(start_date, end_date)

    if not arcgis_ok and not permits:
        log.warning('[Philadelphia] ArcGIS failed — trying CARTO fallback')
        permits = _scrape_via_carto(start_date, end_date)

    log.info('[Philadelphia] Done — %d solar permits', len(permits))
    return permits
