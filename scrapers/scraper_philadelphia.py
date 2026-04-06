"""
Philadelphia L&I Permit Scraper
Uses the Philadelphia ArcGIS Feature Service — no JavaScript required.
"""

import requests
import logging
from datetime import datetime

log = logging.getLogger(__name__)

ARCGIS_URL = (
    'https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services'
    '/permits/FeatureServer/0/query'
)

SOLAR_KEYWORDS = ['solar', 'photovoltaic', 'pv panel', 'pv system', 'pv module']


def _is_solar(p: dict) -> bool:
    text = ' '.join([
        p.get('typeofwork', '') or '',
        p.get('approvedscopeofwork', '') or '',
    ]).lower()
    return any(kw in text for kw in SOLAR_KEYWORDS)


def scrape_philadelphia_api(start_date: str, end_date: str) -> list:
    """
    Scrape Philadelphia electrical permits via ArcGIS Feature Service,
    filter for solar, return list of permit dicts.

    Args:
        start_date: 'YYYY-MM-DD'
        end_date:   'YYYY-MM-DD'
    """
    log.info(f'[Philadelphia] Scraping {start_date} to {end_date}')

    start_ts = f"{start_date} 00:00:00"
    end_ts   = f"{end_date} 23:59:59"

    where = (
        f"permittype = 'ELECTRICAL' "
        f"AND permitissuedate >= '{start_ts}' "
        f"AND permitissuedate <= '{end_ts}'"
    )

    permits = []
    offset   = 0
    page_size = 1000

    while True:
        params = {
            'where':             where,
            'outFields':         (
                'permitnumber,address,permittype,typeofwork,approvedscopeofwork,'
                'status,permitissuedate,contractorname,contractoraddress1,'
                'opa_owner,commercialorresidential'
            ),
            'f':                 'json',
            'resultRecordCount': page_size,
            'resultOffset':      offset,
            'orderByFields':     'permitissuedate DESC',
        }

        try:
            resp = requests.get(ARCGIS_URL, params=params, timeout=30)
            resp.raise_for_status()

            if not resp.text.strip():
                log.error('[Philadelphia] Empty response from ArcGIS')
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
                if not _is_solar(p):
                    continue

                # ArcGIS returns dates as epoch milliseconds
                issued = p.get('permitissuedate')
                if isinstance(issued, (int, float)) and issued:
                    issued = datetime.utcfromtimestamp(issued / 1000).strftime('%Y-%m-%d')

                permits.append({
                    'permitNumber':   p.get('permitnumber'),
                    'address':        p.get('address'),
                    'description':    p.get('approvedscopeofwork') or p.get('typeofwork'),
                    'status':         p.get('status'),
                    'issuedDate':     issued,
                    'appliedDate':    None,
                    'applicantName':  p.get('opa_owner'),
                    'contractorName': p.get('contractorname'),
                    'contractorAddr': p.get('contractoraddress1'),
                    'propertyType':   p.get('commercialorresidential'),
                    'city':           'Philadelphia',
                    'state':          'PA',
                    'source':         'philadelphia_arcgis',
                })

            log.info(f'[Philadelphia] offset={offset} fetched={len(features)} solar_total={len(permits)}')

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
