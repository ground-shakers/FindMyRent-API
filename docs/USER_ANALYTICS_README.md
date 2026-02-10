# User Analytics Endpoint

## Overview

This document describes the user analytics endpoint implementation that provides comprehensive analytics data about users in the system.

## Endpoint Details

### GET `/api/v1/users/analytics`

Retrieves aggregated analytics data for all users in the system.

**Authentication Required:** Yes  
**Authorization:** Admin and Super User only  
**Required Scope:** `read:user:analytics`

#### Response Schema

```json
{
  "totalUsers": 150,
  "verifiedKycUsers": 85,
  "unverifiedKycUsers": 65,
  "kycCompletionRate": 56.67,
  "landlordsWithProperties": 45,
  "landlordsWithoutProperties": 20,
  "topLandlordId": "507f1f77bcf86cd799439011",
  "averageAge": 34.5,
  "age18to25": 30,
  "age26to35": 50,
  "age36to45": 40,
  "age46to60": 25,
  "age60Plus": 5,
  "usersToday": 5,
  "usersThisMonth": 42,
  "maleUsers": 80,
  "femaleUsers": 70,
  "maleLandlords": 30,
  "femaleLandlords": 15
}
```

#### Possible Errors

- **404 Not Found:** No analytics data is available
- **401 Unauthorized:** Missing or invalid authentication token
- **403 Forbidden:** User does not have required permissions
- **500 Internal Server Error:** Unexpected error occurred
- **503 Service Unavailable:** Database connection issue

## Implementation Details

### Files Modified

1. **`routers/users.py`**
   - Added `get_analytics_for_users` endpoint
   - Imports `UserAnalyticsResponse` schema
   - Imports `UserAnalyticsView` from aggregations

2. **`schema/users.py`**
   - Added `UserAnalyticsResponse` schema class
   - Includes all analytics fields with proper serialization aliases

3. **`security/helpers.py`**
   - Added `read:user:analytics` scope to OAuth2 scheme

4. **`scripts/update_permissions.py`** (NEW)
   - Migration script to add the new scope to admin and super_user permissions

### Database Aggregation

The endpoint uses the `UserAnalyticsView` which is a Beanie view that aggregates data from the `User` collection. The aggregation pipeline:

1. Normalizes date of birth and listing counts
2. Calculates user ages
3. Groups data into facets:
   - User statistics (KYC, properties, age groups, gender)
   - Growth metrics (today, this month)
   - Top landlord identification
4. Computes the final analytics output with calculated fields

**Note:** The view is computed on-demand when queried. For production use with large datasets, consider implementing application-level caching (e.g., Redis) with appropriate TTL.

### Running the Permission Migration

To add the new scope to existing admin and super_user permissions:

```bash
python scripts/update_permissions.py
```

## Security Considerations

- Only users with `admin` or `super_user` role can access this endpoint
- The `read:user:analytics` scope must be included in the user's JWT token
- Analytics data is read-only and does not expose sensitive user information (passwords excluded)

## Usage Example

```python
import requests

headers = {
    "Authorization": "Bearer <admin_access_token>"
}

response = requests.get(
    "http://localhost:8000/api/v1/users/analytics",
    headers=headers
)

if response.status_code == 200:
    analytics = response.json()
    print(f"Total Users: {analytics['totalUsers']}")
    print(f"KYC Completion Rate: {analytics['kycCompletionRate']}%")
else:
    print(f"Error: {response.json()['detail']}")
```

## Testing

To test the endpoint:

1. Ensure you have admin or super_user credentials
2. Login to get an access token with the `read:user:analytics` scope
3. Make a GET request to `/api/v1/users/analytics`
4. Verify the response contains all expected analytics fields

## Future Enhancements

Potential improvements for the analytics endpoint:

- **Add Redis caching:** Cache analytics results with TTL (e.g., 5-15 minutes) to reduce database load
- Add date range filtering
- Include tenant-specific analytics
- Add property listing analytics
- Create analytics dashboard visualizations
- Add export functionality (CSV, Excel)
- Implement real-time updates via WebSockets
