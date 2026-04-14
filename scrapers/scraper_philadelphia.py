"""
Philadelphia L&I Permit Scraper
Scrapes solar electrical permits from the Philadelphia open data platform.

Data returned per permit:
  - address + zip (full mailing address)
  - opa_owner (property owner name — the homeowner)
  - approvedscopeofwork / typeofwork (system size, panel model, inverter)
  - contractorname / contractoraddress1
  - status, issuedDate, propertyType (Residential/Commercial)

Phone/email NOT in permit data — enriched downstream via Apollo/Hunter.

Endpoint chain (tried in order):
  1. data.phila.gov CARTO SQL API  — primary, official City of Philadelphia host
  2. phl.carto.com CARTO SQL API   — legacy fallback, same dataset
  3. ArcGIS FeatureServer          — last resort (service migrated, may be stale)
"""

import requests
import logging
from datetime import datetime

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Endpoint configuration
# ---------------------------------------------------------------------------

# Primary: data.phila.gov hosts the official City CARTO SQL API
CARTO_PRIMARY_URL = 'https://data.phila.gov/carto/api/v2/sql'

# Legacy CARTO domain (same dataset, older subdomain)
CARTO_LEGACY_URL = 'https://phl.carto.com/api/v2/sql'

# Confirmed table name from OpenDataPhilly:
# https://opendataphilly.org/datasets/licenses-and-inspections-building-and-zoning-permits/
# Direct download URL uses: phl.carto.com/api/v2/sql?q=SELECT * FROM li_permits
CARTO_TABLE = 'li_permits'

# ArcGIS FeatureServer — last resort. The original org ID (fLeGjb7u4uXqeF9q)
# hosted the old 'permits' service which went dead. 'LI_PERMITS' is the current
# layer name on PHLmaps (data-phl.opendata.arcgis.com/maps/phl::li-permits).
# To get the current org ID: open that page, DevTools > Network, look for
# a request to services.arcgis.com/.../LI_PERMITS/FeatureServer
ARCGIS_URL = (
    'https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services'
    '/LI_PERMITS/FeatureServer/0/query'
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _normalize_permit(p: dict, source: str) -> dict:
    """Normalize a raw permit row into the standard output shape."""
    issued = p.get('permitissuedate')
    # ArcGIS returns epoch milliseconds; CARTO returns ISO strings
    if isinstance(issued, (int, float)) and issued:
        issued = datetime.utcfromtimestamp(issued / 1000).strftime('%Y-%m-%d')
    elif isinstance(issued, str) and issued:
        issued = issued[:10]  # trim any time component

    address      = p.get('address', '') or ''
    zip_code     = p.get('zip', '') or ''
    full_address = f"{address}, Philadelphia, PA {zip_code}".strip(', ')

    # CARTO uses 'typeofwork'; ArcGIS has both 'typeofwork' and 'approvedscopeofwork'
    description = (
        p.get('approvedscopeofwork')
        or p.get('typeofwork')
        or p.get('permitdescription')
    )

    return {
        'permitNumber':    p.get('permitnumber'),
        'address':         full_address,
        'streetAddress':   address,
        'zip':             zip_code,
        'description':     description,
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


# ---------------------------------------------------------------------------
# Scrape via CARTO SQL API
# ---------------------------------------------------------------------------

def _scrape_via_carto(start_date: str, end_date: str,
                      base_url: str, source_label: str) -> tuple:
    """
    Query the CARTO SQL API for solar electrical permits.
    Returns (permits_list, success_bool).
    """
    log.info('[Philadelphia/%s] Querying %s', source_label, base_url)

    sql = (
        f"SELECT permitnumber, address, zip, permittype, typeofwork, "
        f"approvedscopeofwork, status, permitissuedate, "
        f"commercialorresidential, opa_owner, opa_account_num, "
        f"contractorname, contractoraddress1, council_district "
        f"FROM {CARTO_TABLE} "
        f"WHERE permittype = 'ELECTRICAL' "
        f"AND permitissuedate >= '{start_date}' "
        f"AND permitissuedate <= '{end_date} 23:59:59' "
        f"AND ("
        f"  typeofwork ILIKE '%solar%' OR "
        f"  typeofwork ILIKE '%photovoltaic%' OR "
        f"  typeofwork ILIKE '%pv system%' OR "
        f"  typeofwork ILIKE '%pv module%' OR "
        f"  approvedscopeofwork ILIKE '%solar%' OR "
        f"  approvedscopeofwork ILIKE '%photovoltaic%' OR "
        f"  approvedscopeofwork ILIKE '%pv system%' OR "
        f"  approvedscopeofwork ILIKE '%pv module%'"
        f") "
        f"ORDER BY permitissuedate DESC "
        f"LIMIT 5000"
    )

    try:
        resp = requests.get(base_url, params={'q': sql, 'format': 'json'}, timeout=30)
        resp.raise_for_status()

        raw = resp.text.strip()
        if not raw:
            log.error('[Philadelphia/%s] Empty response body (HTTP %s)',
                      source_label, resp.status_code)
            return [], False

        if not raw.startswith('{'):
            log.error('[Philadelphia/%s] Non-JSON response (first 300 chars): %s',
                      source_label, raw[:300])
            return [], False

        data = resp.json()

        if 'error' in data:
            log.error('[Philadelphia/%s] API error: %s', source_label, data['error'])
            return [], False

        rows = data.get('rows', [])
        permits = [_normalize_permit(r, source=f'philadelphia_{source_label.lower()}')
                   for r in rows]
        log.info('[Philadelphia/%s] fetched=%d', source_label, len(permits))
        return permits, True

    except requests.exceptions.RequestException as e:
        log.error('[Philadelphia/%s] Request failed: %s', source_label, e)
        return [], False
    except ValueError as e:
        log.error('[Philadelphia/%s] JSON parse error: %s', source_label, e)
        return [], False
    except Exception as e:
        log.error('[Philadelphia/%s] Unexpected error: %s', source_label, e)
        return [], False


# ---------------------------------------------------------------------------
# Scrape via ArcGIS FeatureServer (last resort)
# ---------------------------------------------------------------------------

def _scrape_via_arcgis(start_date: str, end_date: str) -> tuple:
    """
    ArcGIS FeatureServer fallback. Paginates up to 1000 records per page.
    Returns (permits_list, success_bool).
    """
    log.info('[Philadelphia/ArcGIS] Trying FeatureServer fallback')

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
                log.error('[Philadelphia/ArcGIS] Empty response (HTTP %s) — '
                          'service URL may have moved. Check: '
                          'https://data-phl.opendata.arcgis.com/maps/phl::li-permits',
                          resp.status_code)
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


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def scrape_philadelphia_api(start_date: str, end_date: str) -> list:
    """
    Scrape Philadelphia solar electrical permits.

    Tries endpoints in order:
      1. data.phila.gov CARTO (primary)
      2. phl.carto.com CARTO (legacy fallback)
      3. ArcGIS FeatureServer (last resort)

    Args:
        start_date: 'YYYY-MM-DD'
        end_date:   'YYYY-MM-DD'

    Returns:
        List of solar permit dicts ready for Base44 ingest.
    """
    log.info('[Philadelphia] Scraping %s to %s', start_date, end_date)

    # 1. Primary CARTO endpoint
    permits, ok = _scrape_via_carto(start_date, end_date,
                                    CARTO_PRIMARY_URL, 'CARTO_PRIMARY')
    if ok:
        log.info('[Philadelphia] Done via primary CARTO — %d solar permits', len(permits))
        return permits

    # 2. Legacy CARTO endpoint
    log.warning('[Philadelphia] Primary CARTO failed — trying legacy phl.carto.com')
    permits, ok = _scrape_via_carto(start_date, end_date,
                                    CARTO_LEGACY_URL, 'CARTO_LEGACY')
    if ok:
        log.info('[Philadelphia] Done via legacy CARTO — %d solar permits', len(permits))
        return permits

    # 3. ArcGIS last resort
    log.warning('[Philadelphia] Both CARTO endpoints failed — trying ArcGIS FeatureServer')
    permits, ok = _scrape_via_arcgis(start_date, end_date)

    log.info('[Philadelphia] Done — %d solar permits (arcgis_ok=%s)', len(permits), ok)
    return permits
