"""
Philadelphia L&I API Scraper
Philadelphia has a PUBLIC API - no Playwright needed!
This is by far the easiest scraper.
"""

import requests
import logging
from datetime import datetime

log = logging.getLogger(__name__)


def scrape_philadelphia_api(start_date: str, end_date: str) -> list:
    """
    Scrape Philadelphia permits via their public L&I API.
    
    Args:
        start_date: 'YYYY-MM-DD'
        end_date: 'YYYY-MM-DD'
    
    Returns:
        List of solar permit dicts
    """
    # Philadelphia L&I API endpoint
    # Actual endpoint may vary - check https://li.phila.gov for docs
    API_URL = 'https://li.phila.gov/api/permits'
    
    permits = []
    
    log.info(f'Scraping Philadelphia via API ({start_date} to {end_date})')
    
    try:
        # Make API request
        params = {
            'permitType': 'ELECTRICAL',  # Solar is under electrical
            'fromDate': start_date,
            'toDate': end_date,
            'limit': 1000,
            'offset': 0
        }
        
        response = requests.get(API_URL, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        # Filter for solar permits
        solar_keywords = ['solar', 'photovoltaic', 'pv', 'panel']
        
        for permit in data.get('permits', []):
            description = permit.get('description', '').lower()
            work_type = permit.get('work_type', '').lower()
            
            # Check if it's a solar permit
            if any(keyword in description or keyword in work_type for keyword in solar_keywords):
                permits.append({
                    'permitNumber': permit.get('permit_number'),
                    'address': permit.get('address'),
                    'description': permit.get('description'),
                    'status': permit.get('status'),
                    'issuedDate': permit.get('issued_date'),
                    'appliedDate': permit.get('applied_date'),
                    'applicantName': permit.get('applicant_name'),
                    'contractorName': permit.get('contractor_name'),
                    'value': permit.get('estimated_cost'),
                    'city': 'Philadelphia',
                    'state': 'PA',
                    'source': 'philadelphia_api'
                })
        
        log.info(f'Found {len(permits)} solar permits in Philadelphia')
        
    except requests.exceptions.RequestException as e:
        log.error(f'Philadelphia API request failed: {e}')
    except Exception as e:
        log.error(f'Philadelphia scrape error: {e}')
    
    return permits
