"""
Accela scraper for East Coast cities.
Reuses your existing scraper_accela.py logic, just with East Coast configs.
"""

from cities.accela_cities import CONFIGS as CITY_CONFIGS
import logging

log = logging.getLogger(__name__)

# TODO: Import and adapt your existing scraper_accela.py scrape_accela_async function
# For now, this is a stub

async def scrape_accela_east_async(start_date: str, end_date: str, city_key: str) -> list:
    """
    Scrape Accela portal for East Coast cities.
    This should use your existing scraper_accela.py logic.
    
    Args:
        start_date: 'YYYY-MM-DD'
        end_date: 'YYYY-MM-DD'
        city_key: Key from CITY_CONFIGS
    
    Returns:
        List of permit dicts
    """
    config = CITY_CONFIGS[city_key]
    
    # TODO: Call your existing scrape_accela_async with this config
    # from scraper_accela import scrape_accela_async
    # return await scrape_accela_async(start_date, end_date, config)
    
    log.warning(f'Accela scraper not yet implemented for {config["name"]}')
    return []


def scrape_accela_east(start_date: str, end_date: str, city_key: str) -> list:
    """Sync wrapper"""
    import asyncio
    return asyncio.run(scrape_accela_east_async(start_date, end_date, city_key))


async def discover_permit_types(city_key: str) -> dict:
    """
    Discover available permit types for an Accela city.
    Navigate to the portal and list all dropdown options.
    """
    from playwright.async_api import async_playwright
    
    config = CITY_CONFIGS[city_key]
    result = {
        'city': config['name'],
        'key': city_key,
        'status': 'unknown',
        'all_options': [],
        'solar_options': [],
        'recommended': None,
        'error': None
    }
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await (await browser.new_context()).new_page()
            
            search_url = f"{config['base_url']}/Cap/CapHome.aspx?module={config['module']}"
            
            try:
                await page.goto(search_url, wait_until='networkidle', timeout=30000)
                await page.wait_for_selector('[id*="txtGSStartDate"]', timeout=15000)
                result['status'] = 'ok'
            except Exception as e:
                result['status'] = 'failed'
                result['error'] = str(e)
                await browser.close()
                return result
            
            # Extract permit type options
            options = await page.evaluate("""
                () => {
                    const sel = document.querySelector('select[id*="ddlGSPermitType"]') ||
                                document.querySelector('select[id*="PermitType"]');
                    if (sel) {
                        return Array.from(sel.options).map(o => o.text.trim());
                    }
                    return [];
                }
            """)
            
            result['all_options'] = options
            
            # Find solar-related options
            solar_keywords = ['solar', 'pv', 'photovoltaic']
            solar = [o for o in options if any(k in o.lower() for k in solar_keywords)]
            result['solar_options'] = solar
            
            if solar:
                result['recommended'] = solar[0]
            
            await browser.close()
            
    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)
    
    return result
