"""
Scrappy-East: Solar Permit Scraper for CT, NJ, PA, RI
Standalone Flask API mirroring Scrappy architecture for East Coast cities.
"""

from flask import Flask, request, jsonify, send_file
import requests
import os
import glob
import threading
import logging
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

# One Playwright scrape at a time per worker
_PLAYWRIGHT_LOCK = threading.Lock()

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Base44 config (East Coast specific org)
# ---------------------------------------------------------------------------
BASE44_APP_ID     = os.environ.get('BASE44_APP_ID', '69ac768167fa5ab007eb6ae7')
BASE44_DOMAIN     = os.environ.get('BASE44_DOMAIN', 'agentbmanscraper.base44.app')
BASE44_SECRET     = os.environ.get('INTERNAL_SECRET', '')
BASE44_BASE_URL   = os.environ.get('BASE44_BASE_URL',
                      f'https://{BASE44_DOMAIN}/api/apps/{BASE44_APP_ID}/functions')
BASE44_INGEST_URL = f'{BASE44_BASE_URL}/ingestSolarPermits'

# SEPARATE organization ID for East Coast leads
EAST_COAST_ORGANIZATION_ID = os.environ.get('EAST_COAST_ORGANIZATION_ID', 'YOUR_EAST_COAST_ORG_ID')

BASE44_ENABLED = os.environ.get('BASE44_ENABLED', 'false').lower() == 'true'
MAX_CITIES_PER_JOB = max(1, int(os.environ.get('MAX_CITIES_PER_JOB', '5')))


def post_to_base44(leads, city, start_date, end_date, campaign_id=None, organization_id=None):
    """Post scraped leads to Base44"""
    if not BASE44_ENABLED:
        log.info('[Base44] DISABLED — set BASE44_ENABLED=true to enable')
        print(f'[Base44] DISABLED — would have posted {len(leads)} leads from {city}')
        return

    if not BASE44_SECRET:
        log.warning('INTERNAL_SECRET not set — skipping Base44 post')
        return

    org = (organization_id or EAST_COAST_ORGANIZATION_ID).strip()

    city_label = city.replace('_', ' ').title()
    scraped_at = datetime.utcnow().isoformat() + 'Z'

    # Add metadata to each lead
    for lead in leads:
        lead['cityKey']         = city
        lead['city']            = city_label
        lead['state']           = _extract_state_from_city(city)  # CT, NJ, PA, or RI
        lead['uniqueId']        = f"{city}_{lead.get('permitNumber', '')}"
        lead['enrichmentStage'] = 'scraped'
        lead['scrapedAt']       = scraped_at
        lead['organization_id'] = org
        lead['region']          = 'east_coast'  # Tag for filtering
        if campaign_id:
            lead['campaignId'] = campaign_id

    try:
        res = requests.post(
            BASE44_INGEST_URL,
            headers={
                'x-internal-secret': BASE44_SECRET,
                'Content-Type':      'application/json',
            },
            json={'leads': leads, 'campaign_id': campaign_id or ''},
            timeout=60
        )
        result = res.json()
        log.info(f'[Base44] {city_label}: {result}')
        print(f'Base44 ingest [{city_label}]: total={result.get("total")} '
              f'created={result.get("created")} updated={result.get("updated")} '
              f'errors={result.get("errors")}')
    except Exception as e:
        log.error(f'[Base44] Post failed: {e}')
        print(f'Base44 post failed: {e}')


def _extract_state_from_city(city_key: str) -> str:
    """Extract state code from city key"""
    if '_ct' in city_key:
        return 'CT'
    elif '_nj' in city_key:
        return 'NJ'
    elif '_pa' in city_key:
        return 'PA'
    elif '_ri' in city_key:
        return 'RI'
    return 'Unknown'


# ---------------------------------------------------------------------------
# Lazy scraper loader
# ---------------------------------------------------------------------------
def get_scraper(city: str):
    """Load appropriate scraper for the city"""
    city = city.lower().replace(' ', '_').replace('-', '_')

    # Try Accela cities first (CT and PA)
    from scrapers.scraper_accela_east import scrape_accela_east, CITY_CONFIGS as ACCELA_CONFIGS
    if city in ACCELA_CONFIGS:
        return scrape_accela_east, {'city_key': city}

    # Try Viewpoint cities (NJ and RI)
    from scrapers.scraper_viewpoint import scrape_viewpoint, CITY_CONFIGS as VIEWPOINT_CONFIGS
    if city in VIEWPOINT_CONFIGS:
        return scrape_viewpoint, {'city_key': city}

    # Philadelphia custom API
    if city in ('philadelphia', 'philadelphia_pa', 'philly'):
        from scrapers.scraper_philadelphia import scrape_philadelphia_api
        return scrape_philadelphia_api, {}

    # List all available cities
    all_cities = list(ACCELA_CONFIGS.keys()) + list(VIEWPOINT_CONFIGS.keys()) + ['philadelphia_pa']
    raise ValueError(f'Unknown city: {city}. Available: {", ".join(sorted(all_cities))}')


def run_and_post(city, start_date, end_date, campaign_id=None, organization_id=None):
    """Run scraper and post results to Base44"""
    with _PLAYWRIGHT_LOCK:
        try:
            scrape_fn, kwargs = get_scraper(city)
            leads = scrape_fn(start_date=start_date, end_date=end_date, **kwargs)
            print(f'Scraped {len(leads)} leads from {city}')
            post_to_base44(leads, city, start_date, end_date, campaign_id, organization_id)
            return leads
        except Exception as e:
            print(f'Scrape failed [{city}]: {e}')
            log.exception(f'Scrape error [{city}]')
            return []


def _run_campaign_cities_sequential(cities, start_date, end_date, campaign_id, organization_id):
    """Background worker: scrape cities sequentially"""
    for city in cities:
        run_and_post(city, start_date, end_date, campaign_id, organization_id)
    log.info(f'Campaign {campaign_id} finished all cities: {cities}')


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    return jsonify({
        'status':           'ok',
        'service':          'scrappy-east',
        'region':           'CT, NJ, PA, RI',
        'base44_enabled':   BASE44_ENABLED,
        'endpoints': {
            'health':           'GET /health',
            'cities':           'GET /cities — list all available cities',
            'scrape':           'POST /scrape — scrape single city',
            'campaign':         'POST /scrape/campaign — scrape multiple cities',
            'discover':         'GET /discover/<city> — find permit types',
        }
    })


@app.route('/health')
def health():
    return jsonify({
        'status':         'ok',
        'region':         'east_coast',
        'base44_enabled': BASE44_ENABLED,
    })


@app.route('/cities')
def list_cities():
    """List all available East Coast cities"""
    from scrapers.scraper_accela_east import CITY_CONFIGS as ACCELA_CONFIGS
    from scrapers.scraper_viewpoint import CITY_CONFIGS as VIEWPOINT_CONFIGS
    
    cities = {}
    
    # Accela cities
    for key, config in ACCELA_CONFIGS.items():
        cities[key] = {
            'name': config['name'],
            'platform': 'Accela',
            'state': _extract_state_from_city(key),
            'status': 'active'
        }
    
    # Viewpoint cities
    for key, config in VIEWPOINT_CONFIGS.items():
        cities[key] = {
            'name': config['name'],
            'platform': 'Viewpoint',
            'state': _extract_state_from_city(key),
            'status': 'active'
        }
    
    # Philadelphia
    cities['philadelphia_pa'] = {
        'name': 'Philadelphia, PA',
        'platform': 'Custom API',
        'state': 'PA',
        'status': 'active'
    }
    
    # Group by state
    by_state = {}
    for key, info in cities.items():
        state = info['state']
        if state not in by_state:
            by_state[state] = []
        by_state[state].append({**info, 'key': key})
    
    return jsonify({
        'total': len(cities),
        'cities': cities,
        'by_state': by_state
    })


@app.route('/scrape', methods=['POST'])
def scrape_single():
    """
    Scrape a single city.
    Body: {
        "city": "hartford_ct",
        "days": 30,
        "campaignId": "optional"
    }
    Or: {
        "city": "hartford_ct", 
        "startDate": "2024-01-01",
        "endDate": "2024-03-31"
    }
    """
    data = request.json or {}
    city = data.get('city', '').strip()
    campaign_id = data.get('campaignId')
    organization_id = data.get('organizationId')
    
    if not city:
        return jsonify({'success': False, 'error': 'city required'}), 400
    
    # Calculate date range
    if 'startDate' in data and 'endDate' in data:
        start_date = data['startDate']
        end_date = data['endDate']
    else:
        days = int(data.get('days', 30))
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    try:
        leads = run_and_post(city, start_date, end_date, campaign_id, organization_id)
        return jsonify({
            'success': True,
            'city': city,
            'count': len(leads),
            'startDate': start_date,
            'endDate': end_date,
            'leads': leads[:10]  # Preview first 10
        })
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except Exception as e:
        log.exception(f'Scrape error [{city}]')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/scrape/campaign', methods=['POST'])
def scrape_campaign():
    """
    Scrape multiple cities as a campaign (runs in background).
    Body: {
        "cities": ["hartford_ct", "new_haven_ct", "stamford_ct"],
        "days": 30,
        "campaignId": "east_coast_q1_2024",
        "organizationId": "optional"
    }
    """
    data = request.json or {}
    cities = data.get('cities', [])
    campaign_id = data.get('campaignId', f'campaign_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
    organization_id = data.get('organizationId')
    
    if not cities or not isinstance(cities, list):
        return jsonify({'success': False, 'error': 'cities array required'}), 400
    
    if len(cities) > MAX_CITIES_PER_JOB:
        return jsonify({
            'success': False,
            'error': f'Max {MAX_CITIES_PER_JOB} cities per campaign (got {len(cities)})'
        }), 400
    
    # Calculate date range
    if 'startDate' in data and 'endDate' in data:
        start_date = data['startDate']
        end_date = data['endDate']
    else:
        days = int(data.get('days', 30))
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    # Run in background
    thread = threading.Thread(
        target=_run_campaign_cities_sequential,
        args=(cities, start_date, end_date, campaign_id, organization_id)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'success': True,
        'campaignId': campaign_id,
        'cities': cities,
        'startDate': start_date,
        'endDate': end_date,
        'status': 'running',
        'message': 'Campaign started in background'
    })


@app.route('/discover/<city_key>', methods=['GET'])
def discover_city(city_key):
    """
    Discover available permit types for a city.
    Navigates to the portal and lists all permit type options.
    """
    import asyncio
    
    try:
        scrape_fn, kwargs = get_scraper(city_key)
        
        # Only works for Accela cities currently
        if 'scraper_accela_east' not in str(scrape_fn):
            return jsonify({
                'error': 'Discovery only available for Accela cities',
                'city': city_key
            }), 400
        
        from scrapers.scraper_accela_east import discover_permit_types
        result = asyncio.run(discover_permit_types(kwargs['city_key']))
        return jsonify(result)
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        log.exception(f'Discovery error [{city_key}]')
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
