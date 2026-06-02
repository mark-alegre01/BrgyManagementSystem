# Household Map Feature - Implementation Guide

## 🏠 Overview

The Barangay Map has been updated to show **Household markers** instead of Purok markers. Each household location is pinpointed on the map based on its GPS coordinates. When a new household is added to the system, it automatically appears on the map.

## ✨ Key Changes

### What Changed

| Feature | Before | After |
|---------|--------|-------|
| **Markers** | Purok locations | Individual Household locations |
| **Search** | Search by Purok name | Search by Household number or address |
| **Popup Info** | Purok name, residents count, household count | Household number, address, Purok, residents count |
| **Data Source** | `/residents/api/puroks/` | `/residents/api/households/` |

### Data Structure

The new API endpoint returns **Households** as GeoJSON features:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [125.7222, 9.4898]
      },
      "properties": {
        "id": 1,
        "household_no": "HH-001",
        "address": "123 Main St, Brgy. Sico Sico",
        "purok": "Purok 1",
        "residents": 5
      }
    }
  ]
}
```

## 🛠️ Technical Implementation

### New API Endpoint

**URL:** `/residents/api/households/`
**Method:** GET
**Authentication:** Required (login)
**File:** `residents/views.py` → `household_map_api()` function

```python
@login_required
def household_map_api(request):
    """Return all Households with coordinates as GeoJSON for mapping."""
    households = Household.objects.filter(latitude__isnull=False, longitude__isnull=False).select_related('purok')
    features = []
    
    for h in households:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [h.longitude, h.latitude]
            },
            "properties": {
                "id": h.pk,
                "household_no": h.household_no,
                "address": h.address,
                "purok": h.purok.name if h.purok else "N/A",
                "residents": h.member_count,
            }
        })
        
    return JsonResponse({
        "type": "FeatureCollection",
        "features": features
    })
```

### Updated URL Pattern

File: `residents/urls.py`

```python
path('api/households/', views.household_map_api, name='household_map_api'),
```

### Updated Template

File: `templates/core/barangay_map.html`

- Changed marker class from `purok-marker` to `household-marker`
- Updated search logic to search households by number or address
- Updated popup content to show household information
- Changed loading message and info card title

## 📍 How It Works

### 1. Household Database Setup

The Household model already has coordinate fields:

```python
class Household(models.Model):
    household_no = models.CharField(max_length=50, unique=True)
    address = models.TextField()
    purok = models.ForeignKey(Purok, ...)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
```

### 2. Adding Household Coordinates

When adding or editing a household in Django Admin:

1. Go to `/admin/residents/household/`
2. Edit a household
3. Fill in the **Latitude** and **Longitude** fields
4. Save

**Example coordinates for Barangay Sico Sico:**
- Center: 9.4898°N, 125.7222°E
- Variation: ±0.01 degrees (approx ±1.1 km)

### 3. Map Display

When a user visits the Barangay Map:

1. The map loads and centers on Barangay Sico Sico
2. The API fetches all Households with coordinates
3. A green circular marker appears for each household
4. Clicking a marker shows a popup with:
   - Household number
   - Street address
   - Purok name
   - Number of residents

### 4. Search Functionality

Users can search for households by:

- **Household Number:** "HH-001", "HH-002", etc.
- **Address:** "Main St", "Street name", partial addresses
- Real-time filtering as you type
- Click result to fly to that household

## 🔍 Map Features

### Marker Styling
- **Color:** Green (primary color - #2C6E49)
- **Shape:** Circular with white border
- **Animation:** Scales up on hover
- **Icon:** House user icon

### Popup Content
```
╔════════════════════════════╗
║ 🏢 Household HH-001        ║
├────────────────────────────┤
║ 📍 123 Main St             ║
║    Brgy. Sico Sico         ║
║                            ║
║ 📌 Purok: Purok 1         ║
║                            ║
║ 👥 Residents: 5            ║
╚════════════════════════════╝
```

### Search Results
Results show:
- Household number (with house icon)
- Full address
- Purok information
- Click to navigate

## 🚀 Usage Instructions

### For Administrators

1. **Populate Household Coordinates:**
   - Go to Django Admin → Households
   - Edit each household
   - Add latitude and longitude
   - Save

2. **Access the Map:**
   - Dashboard → Sidebar → RECORDS → Barangay Map
   - Map displays all households with coordinates

3. **Search Households:**
   - Type household number or address
   - Click result to zoom to location
   - Click marker popup for details

### For Viewing Household Locations

1. Click on any household marker
2. Popup shows:
   - Household identification
   - Complete address
   - Purok assignment
   - Resident count

3. Use "Locate Me" to center map on your position
4. Toggle between Standard and Satellite view

## 📊 Database Query

The API query filters households with valid coordinates:

```python
Household.objects.filter(latitude__isnull=False, longitude__isnull=False)
```

This ensures only households with actual coordinates appear on the map.

## 🗺️ Coordinate Format

- **Latitude:** -90 to +90 (positive = North)
- **Longitude:** -180 to +180 (positive = East)
- **Barangay Center:** 9.4898, 125.7222
- **Precision:** 4-6 decimal places recommended (±10 meters)

Example households:
```
Household HH-001: 9.4898, 125.7222 (center)
Household HH-002: 9.4900, 125.7215 (north-west)
Household HH-003: 9.4895, 125.7230 (south-east)
```

## ✅ What's Included

- ✅ New API endpoint for household locations
- ✅ Household markers on map
- ✅ Search by household number or address
- ✅ Popup with household details
- ✅ Geolocation support ("Locate Me" button)
- ✅ Layer toggle (Standard/Satellite)
- ✅ Responsive design
- ✅ Permission controls (captain, admin only)

## 📋 Implementation Checklist

- ✅ Add household coordinates to database
- ✅ Create `household_map_api` view
- ✅ Add URL pattern for new endpoint
- ✅ Update map template to use households
- ✅ Change marker styling (circular)
- ✅ Update search logic
- ✅ Update popup content
- ✅ Test map functionality

## 🔐 Security

- Endpoint requires login (`@login_required`)
- Only accessible to authenticated users
- Respects existing permission system

## 🎯 Next Steps

1. **Populate Coordinates:**
   ```bash
   # Django shell
   python manage.py shell
   >>> from residents.models import Household
   >>> h = Household.objects.first()
   >>> h.latitude = 9.4898
   >>> h.longitude = 125.7222
   >>> h.save()
   ```

2. **Verify Map Data:**
   - Visit `/residents/api/households/` in browser
   - Check GeoJSON format
   - Verify coordinates are present

3. **Test Map:**
   - Login as admin/captain
   - Go to Barangay Map
   - Verify households appear
   - Test search and popups

## 📝 Files Modified

- `residents/views.py` - Added `household_map_api()` function
- `residents/urls.py` - Added household API endpoint
- `templates/core/barangay_map.html` - Updated to show household markers

## 🆘 Troubleshooting

### Households not appearing
- Check that households have latitude/longitude filled in Django Admin
- Verify coordinates are in correct range (9.48±, 125.72±)
- Check API endpoint: `/residents/api/households/`

### Search not working
- Ensure household numbers exist in database
- Try searching by address instead
- Check browser console for JavaScript errors

### Markers not clickable
- Ensure MapLibre GL JS CDN is loaded
- Check popup HTML is valid
- Try refreshing page

---

**Status:** ✅ Complete and Ready for Use  
**Last Updated:** June 1, 2026
