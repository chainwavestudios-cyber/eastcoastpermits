# Scrappy-East

Solar permit scraper for **Connecticut, New Jersey, Pennsylvania, and Rhode Island**.

Separate deployment from Scrappy (West Coast) to keep East Coast customers isolated.

## 🏙️ Supported Cities

### Connecticut (4 cities)
- **Hartford** (Accela)
- **New Haven** (Accela)
- **Stamford** (Accela)
- **Bridgeport** (Viewpoint)

### New Jersey (3 cities)
- **Jersey City** (Viewpoint)
- **Newark** (Viewpoint)
- **Edison** (Viewpoint)

### Pennsylvania (3 cities)
- **Philadelphia** (Custom API) ⭐ *Easiest to scrape*
- **Pittsburgh** (Accela)
- **Allentown** (Accela)

### Rhode Island (3 cities)
- **Providence** (Viewpoint)
- **Warwick** (Viewpoint)
- **Cranston** (Viewpoint)

**Total: 13 scrapable cities**

## 🚀 Quick Start

### 1. Deploy to Render

```bash
# Push to GitHub
git init
git add .
git commit -m "Initial commit"
git push origin main

# Connect to Render
# - Create new Web Service
# - Connect your repo
# - Render will auto-detect render.yaml
```

### 2. Set Environment Variables in Render

Required:
- `INTERNAL_SECRET` - Generate a random secret
- `EAST_COAST_ORGANIZATION_ID` - Your Base44 org ID for East Coast
- `BASE44_ENABLED=true` - When ready to push to Base44

Optional:
- `MAX_CITIES_PER_JOB=5` - Max cities per campaign

### 3. Test the API

```bash
# Health check
curl https://scrappy-east.onrender.com/health

# List cities
curl https://scrappy-east.onrender.com/cities

# Scrape Philadelphia (easiest - has API)
curl -X POST https://scrappy-east.onrender.com/scrape \
  -H "Content-Type: application/json" \
  -d '{"city": "philadelphia_pa", "days": 30}'

# Run campaign across multiple cities
curl -X POST https://scrappy-east.onrender.com/scrape/campaign \
  -H "Content-Type: application/json" \
  -H "x-internal-secret: YOUR_SECRET" \
  -d '{
    "cities": ["hartford_ct", "new_haven_ct", "jersey_city_nj"],
    "days": 30,
    "campaignId": "east_coast_jan_2024"
  }'
```

## 📊 Expected Volume

| City | Permits/Month | Platform |
|------|---------------|----------|
| Philadelphia, PA | ~120 | API ⭐ |
| Pittsburgh, PA | ~30 | Accela |
| Jersey City, NJ | ~25 | Viewpoint |
| Edison, NJ | ~22 | Viewpoint |
| Newark, NJ | ~20 | Viewpoint |
| Stamford, CT | ~18 | Accela |
| Hartford, CT | ~15 | Accela |
| Providence, RI | ~15 | Viewpoint |
| New Haven, CT | ~12 | Accela |
| Bridgeport, CT | ~10 | Viewpoint |

**Total: ~287 permits/month** across all 13 cities

## 🔧 Implementation Status

### ✅ Complete
- [x] Flask API structure
- [x] City configurations
- [x] Base44 integration
- [x] Render deployment config
- [x] Philadelphia API scraper (ready to use!)

### 🚧 To Implement
- [ ] Copy your `scraper_accela.py` logic into `scrapers/scraper_accela_east.py`
- [ ] Implement Viewpoint scraper (simpler than Accela)
- [ ] Test discovery endpoint for each Accela city
- [ ] Build frontend UI (separate from West Coast)

## 🛠️ Next Steps

### Step 1: Copy Your Accela Logic

Your existing `scraper_accela.py` already works! Just copy it:

```python
# In scrapers/scraper_accela_east.py
from your_west_coast_scrappy import scraper_accela

# Use the exact same function, different configs
scrape_accela_east_async = scraper_accela.scrape_accela_async
```

### Step 2: Test Philadelphia First

Philadelphia is the easiest - it has a public API! No Playwright needed.

```bash
POST /scrape
{
  "city": "philadelphia_pa",
  "days": 7
}
```

### Step 3: Discover Permit Types

For each Accela city, find the exact permit type label:

```bash
GET /discover/hartford_ct
GET /discover/new_haven_ct
GET /discover/pittsburgh_pa
```

This navigates to the portal and shows you all available permit types.
Update `cities/accela_cities.py` with the exact labels.

### Step 4: Build Viewpoint Scraper

Viewpoint is simpler than Accela (no ASP.NET ViewState complexity).
Pattern:
1. Navigate to search page
2. Fill date range
3. Select "Electrical" permit type
4. Parse results table

### Step 5: Frontend

Build a separate UI (not mixed with West Coast customers):
- City selector (grouped by state)
- Date range picker
- Campaign manager
- Results viewer

Can reuse your West Coast UI structure, just different branding/cities.

## 📁 Project Structure

```
scrappy-east/
├── app.py                          # Main Flask API
├── requirements.txt
├── render.yaml                     # Render deployment
├── dockerfile
├── cities/
│   ├── accela_cities.py           # CT, PA configs
│   └── viewpoint_cities.py        # NJ, RI configs
├── scrapers/
│   ├── scraper_accela_east.py     # Accela scraper (copy from West)
│   ├── scraper_viewpoint.py       # Viewpoint scraper (new)
│   └── scraper_philadelphia.py    # Philly API (complete!)
└── docs/
    └── README.md
```

## 🔑 Key Differences from West Coast Scrappy

1. **Separate Base44 Organization** - Different org ID for East Coast leads
2. **State Tags** - All leads tagged with CT/NJ/PA/RI
3. **Different Platforms** - More Viewpoint, less custom portals
4. **Regional Branding** - "East Coast" vs "California" in UI
5. **Isolated Deployment** - No mixing with West Coast data

## 💡 Tips

- **Start with Philadelphia** - Easiest city, public API, ~120 permits/month
- **Use discovery endpoint** - Don't guess permit type labels
- **Viewpoint > Accela** - Viewpoint cities are easier to scrape
- **Test locally first** - Use same structure as your West Coast Scrappy
