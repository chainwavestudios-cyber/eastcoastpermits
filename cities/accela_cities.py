"""
East Coast Accela Cities: CT and PA
Accela portal configurations for Hartford, New Haven, Stamford, Pittsburgh, Allentown.
"""

CONFIGS = {
    # Connecticut
    'hartford_ct': {
        'name':        'Hartford, CT',
        'base_url':    'https://aca-prod.accela.com/HARTFORD',
        'module':      'Building',
        'permit_type': 'Building/Electrical/Solar',  # Confirm via discovery
        'source':      'hartford_accela',
        'state':       'CT',
    },
    
    'new_haven_ct': {
        'name':        'New Haven, CT',
        'base_url':    'https://aca-prod.accela.com/NEWHAVEN',
        'module':      'Building',
        'permit_type': 'Electrical/Solar',
        'source':      'new_haven_accela',
        'state':       'CT',
    },
    
    'stamford_ct': {
        'name':        'Stamford, CT',
        'base_url':    'https://aca-prod.accela.com/STAMFORD',
        'module':      'Building',
        'permit_type': 'Electrical - Solar',
        'source':      'stamford_accela',
        'state':       'CT',
    },
    
    # Pennsylvania
    'pittsburgh_pa': {
        'name':        'Pittsburgh, PA',
        'base_url':    'https://aca-prod.accela.com/PITTSBURGH',
        'module':      'Building',
        'permit_type': 'Building/Electrical/Solar',
        'source':      'pittsburgh_accela',
        'state':       'PA',
    },
    
    'allentown_pa': {
        'name':        'Allentown, PA',
        'base_url':    'https://aca-prod.accela.com/ALLENTOWN',
        'module':      'Building',
        'permit_type': 'Electrical/Solar Panel',
        'source':      'allentown_accela',
        'state':       'PA',
    },
}
