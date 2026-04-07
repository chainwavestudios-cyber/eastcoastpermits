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

ARCGIS_URL = (
    'https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services'
    '/permits/FeatureServer/0/query'
)


def scrape_philadelphia_api(start_date: str, end_date: str) -> list:
    """
    Scrape Philadelphia electrical permits via ArcGIS Feature Service,
    filtered for solar at the query level.

    Args:
        start_date: 'YYYY-MM-DD'
        end_date:   'YYYY-MM-DD'

    Returns:
        List of solar permit dicts ready for Base44 ingest.
    """
    log.info(f'[Philadelphia] Scraping {start_date} to {end_date}')

    start_ts = f"{start_date} 00:00:00"
    end_ts   = f"{end_date} 23:59:59"

    # ArcGIS LIKE is case-insensitive by default — no LOWER() needed
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

    permits  = []
    offset   = 0
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
                log.error('[Philadelphia] Empty response from ArcGIS')
                break

            # Log first 300 chars so we can debug non-JSON responses
            if not raw.startswith('{'):
                log.error(f'[Philadelphia] Non-JSON response: {raw[:300]}')
                break

            data = resp.json()

            if 'error' in data:
                log.error(f'[Philadelphia] ArcGIS error: {data["error"]}')
                break

            features = data.get('features', [])
            if not features:
                break

            for f in features:
                p = f.get('attributes', {})

                # ArcGIS returns dates as epoch milliseconds → YYYY-MM-DD
                issued = p.get('permitissuedate')
                if isinstance(issued, (int, float)) and issued:
                    issued = datetime.utcfromtimestamp(issued / 1000).strftime('%Y-%m-%d')

                # Full street address with zip
                address      = p.get('address', '') or ''
                zip_code     = p.get('zip', '') or ''
                full_address = f"{address}, Philadelphia, PA {zip_code}".strip(', ')

                permits.append({
                    'permitNumber':    p.get('permitnumber'),
                    'address':         full_address,
                    'streetAddress':   address,
                    'zip':             zip_code,
                    'description':     p.get('approvedscopeofwork') or p.get('typeofwork'),
                    'status':          p.get('status'),
                    'issuedDate':      issued,
                    'ownerName':       p.get('opa_owner'),       # e.g. "MALTBY MARK DANIEL"
                    'opaAccountNum':   p.get('opa_account_num'), # OPA parcel ID
                    'contractorName':  p.get('contractorname'),
                    'contractorAddr':  (p.get('contractoraddress1') or '').replace('\r\n', ', '),
                    'propertyType':    p.get('commercialorresidential'),  # Residential / Commercial
                    'councilDistrict': p.get('council_district'),
                    'city':            'Philadelphia',
                    'state':           'PA',
                    'source':          'philadelphia_arcgis',
                })

            log.info(
                f'[Philadelphia] offset={offset} '
                f'fetched={len(features)} total={len(permits)}'
            )

            if len(features) < page_size:
                break
            offset += page_size

        except requests.exceptions.RequestException as e:
            log.error(f'[Philadelphia] Request failed: {e}')
            break
        except ValueError as e:
            log.error(f'[Philadelphia] JSON parse error: {e}')
            break
        except Exception as e:
            log.error(f'[Philadelphia] Unexpected error: {e}')
            break

    log.info(f'[Philadelphia] Done — {len(permits)} solar permits')
    return permits
