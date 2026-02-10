# User Analytics Implementation Summary

## Changes Made

This document summarizes all the changes made to implement the user analytics endpoint with proper access control.

### 1. Schema Updates (`schema/users.py`)

**Added:**

- `UserAnalyticsResponse` class - Response schema for the analytics endpoint with all required fields and serialization aliases

**Updated:**

- Import statement to include `Optional` type for nullable fields

### 2. Router Updates (`routers/users.py`)

**Added:**

- `get_analytics_for_users()` endpoint at `/api/v1/users/analytics`
  - Accessible only to Admin and Super User with `read:user:analytics` scope
  - Returns aggregated analytics data from `UserAnalyticsView`
  - Proper error handling for database connection issues, validation errors, and missing data
  - Logging with logfire for monitoring and debugging

**Updated:**

- Import statement to include `UserAnalyticsResponse` schema

### 3. Security Updates (`security/helpers.py`)

**Updated:**

- `oauth2_scheme` OAuth2PasswordBearer configuration
- Added new scope: `"read:user:analytics": "Read user analytics data"`

### 4. New Files Created

#### `scripts/update_permissions.py`

- Python script to programmatically update permissions in the database
- Adds `read:user:analytics` scope to admin and super_user permissions
- Handles both updating existing permissions and creating new ones if missing

#### `scripts/USER_ANALYTICS_README.md`

- Complete documentation for the analytics endpoint
- Includes:
  - Endpoint details and authentication requirements
  - Response schema example
  - Error codes and meanings
  - Implementation details
  - Usage examples
  - Testing instructions
  - Future enhancement suggestions

#### `scripts/PERMISSIONS_UPDATE_GUIDE.md`

- Step-by-step guide for adding the new scope to permissions
- Multiple methods provided:
  - Manual MongoDB shell commands
  - Python script execution
  - MongoDB Compass GUI
- Troubleshooting section
- Verification steps

## Key Features

### Access Control

- **Role-Based:** Only `admin` and `super_user` roles can access
- **Scope-Based:** Requires `read:user:analytics` scope in JWT token
- **Type-Safe:** Uses FastAPI's Security dependency with proper typing

### Analytics Data Provided

- **User Statistics:**
  - Total users
  - KYC verification metrics
  - Landlord property statistics
  - Top landlord identification

- **Demographics:**
  - Age distribution (5 brackets: 18-25, 26-35, 36-45, 46-60, 60+)
  - Average age
  - Gender distribution (overall and for landlords)

- **Growth Metrics:**
  - Users registered today
  - Users registered this month

### Error Handling

- 404: No analytics data available
- 401: Unauthorized (invalid/missing token)
- 403: Forbidden (insufficient permissions)
- 500: Internal server error
- 503: Service unavailable (database issues)

### Performance Optimization

- Uses MongoDB aggregation pipeline
- Results cached in `user_analytics_cache` collection
- Efficient data computation using `$facet` for parallel processing

## Database Schema

### Permissions Collection

```json
{
  "user_type": "admin" | "super_user" | "landlord",
  "permissions": ["scope1", "scope2", ..., "read:user:analytics"]
}
```

### User Analytics View

- Source: `User` collection
- Computed: On-demand (no caching at database level)
- Updates: Real-time data with each query

## Migration Steps

1. **Update Code:**
   - ✅ Schema updated with `UserAnalyticsResponse`
   - ✅ Router updated with analytics endpoint
   - ✅ Security scopes updated with new permission

2. **Update Database Permissions:**

   ```bash
   # Option 1: Use Python script
   python scripts/update_permissions.py
   
   # Option 2: Use MongoDB shell (see PERMISSIONS_UPDATE_GUIDE.md)
   ```

3. **Restart Application:**

   ```bash
   # Application will pick up the new scope definition
   # Existing tokens won't have the scope - users need to login again
   ```

4. **Test the Endpoint:**

   ```bash
   # Login as admin to get new token with updated scopes
   # Access /api/v1/users/analytics endpoint
   ```

## Security Considerations

1. **Token Refresh Required:** Existing admin tokens won't have the new scope. Users must login again to get updated permissions.

2. **Scope Validation:** FastAPI automatically validates that the token contains the required scope before allowing access.

3. **Data Privacy:** The analytics endpoint doesn't expose individual user passwords or sensitive personal information.

4. **Audit Logging:** All access to the analytics endpoint is logged via logfire for security auditing.

## Testing Checklist

- [ ] Verify admin user can access `/api/v1/users/analytics`
- [ ] Verify super_user can access `/api/v1/users/analytics`
- [ ] Verify landlord users get 403 Forbidden error
- [ ] Verify unauthenticated requests get 401 Unauthorized
- [ ] Verify response contains all expected fields
- [ ] Verify analytics data is accurate
- [ ] Check error handling for empty database
- [ ] Test with database connection issues

## Next Steps

1. Run the permissions update script or manually update the database
2. Restart the application
3. Test the endpoint with admin credentials
4. Monitor logs for any issues
5. Consider implementing caching strategy for production use
6. Plan for analytics dashboard UI development

## Questions or Issues?

Refer to:

- `USER_ANALYTICS_README.md` for endpoint documentation
- `PERMISSIONS_UPDATE_GUIDE.md` for permission configuration
- Application logs in logfire for debugging
