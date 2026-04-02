"""
Viewpoint Cities: NJ and RI
Jersey City, Newark, Edison, Providence, Warwick, Cranston.
"""

CONFIGS = {
    # New Jersey
    'jersey_city_nj': {
        'name':        'Jersey City, NJ',
        'base_url':    'https://jerseycity.viewpointcloud.com',
        'permit_type': 'Electrical',  # Solar falls under Electrical
        'filter_keyword': 'solar',  # Filter results for solar
        'source':      'jersey_city_viewpoint',
        'state':       'NJ',
    },
    
    'newark_nj': {
        'name':        'Newark, NJ',
        'base_url':    'https://newark.viewpointcloud.com',
        'permit_type': 'Electrical',
        'filter_keyword': 'solar',
        'source':      'newark_viewpoint',
        'state':       'NJ',
    },
    
    'edison_nj': {
        'name':        'Edison, NJ',
        'base_url':    'https://edisonportal.viewpointcloud.com',
        'permit_type': 'Electrical - Solar',
        'source':      'edison_viewpoint',
        'state':       'NJ',
    },
    
    'bridgeport_ct': {
        'name':        'Bridgeport, CT',
        'base_url':    'https://bridgeport.viewpointcloud.com',
        'permit_type': 'Electrical - Solar',
        'source':      'bridgeport_viewpoint',
        'state':       'CT',
    },
    
    # Rhode Island
    'providence_ri': {
        'name':        'Providence, RI',
        'base_url':    'https://providence.viewpointcloud.com',
        'permit_type': 'Electrical - Solar',
        'source':      'providence_viewpoint',
        'state':       'RI',
    },
    
    'warwick_ri': {
        'name':        'Warwick, RI',
        'base_url':    'https://warwick.viewpointcloud.com',
        'permit_type': 'Electrical',
        'filter_keyword': 'solar',
        'source':      'warwick_viewpoint',
        'state':       'RI',
    },
    
    'cranston_ri': {
        'name':        'Cranston, RI',
        'base_url':    'https://cranston.viewpointcloud.com',
        'permit_type': 'Electrical - Solar',
        'source':      'cranston_viewpoint',
        'state':       'RI',
    },
}
