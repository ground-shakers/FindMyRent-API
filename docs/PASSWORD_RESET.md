# Password Reset Feature Documentation

## Overview

This document describes the secure password reset feature for FindMyRent, including the complete flow, security measures, API endpoints, and implementation details.

---

## Table of Contents

1. [Feature Summary](#feature-summary)
2. [Security Measures](#security-measures)
3. [User Flow](#user-flow)
4. [API Endpoints](#api-endpoints)
5. [Implementation Details](#implementation-details)
6. [Configuration](#configuration)
7. [Error Handling](#error-handling)

---

## Feature Summary

The password reset feature allows users to securely reset their password when they've forgotten it. The flow consists of two steps:

1. **Request Reset**: User submits their email address
2. **Complete Reset**: User clicks the link in the email and sets a new password

---

## Security Measures

The implementation follows security best practices to prevent common attacks:

| Security Measure | Description |
|-----------------|-------------|
| **Cryptographic Tokens** | 64-character URL-safe tokens with 256-bit entropy using `secrets.token_urlsafe(48)` |
| **Token Expiry** | Tokens expire after 1 hour |
| **One-Time Use** | Tokens are invalidated immediately after successful use |
| **Rate Limiting** | Maximum 3 reset requests per email per hour |
| **No User Enumeration** | Same response returned whether email exists or not |
| **Failed Attempt Tracking** | Maximum 5 failed token validations before lockout |
| **Password Strength** | Enforces uppercase, lowercase, number, and special character |
| **Secure Storage** | Tokens stored in Redis with automatic expiry |

---

## User Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     PASSWORD RESET FLOW                          │
└─────────────────────────────────────────────────────────────────┘

User clicks "Forgot Password"
            │
            ▼
┌─────────────────────────┐
│ POST /forgot-password   │
│ {email: "user@..."}     │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐     ┌─────────────────────────┐
│ Check if email exists   │────▶│ Email doesn't exist     │
│ (silently)              │     │ Log but don't reveal    │
└───────────┬─────────────┘     └─────────────────────────┘
            │ Email exists
            ▼
┌─────────────────────────┐
│ Generate secure token   │
│ Store in Redis (1 hour) │
│ Send email with link    │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────┐
│ Response: "If an account with this email exists, a password     │
│           reset link has been sent."                            │
│ (Same response regardless of email existence)                   │
└─────────────────────────────────────────────────────────────────┘

            │
            ▼ User clicks email link
┌─────────────────────────┐
│ POST /reset-password    │
│ {token, password,       │
│  confirm_password}      │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐     ┌─────────────────────────┐
│ Validate token          │────▶│ Invalid/Expired token   │
│                         │     │ Return error            │
└───────────┬─────────────┘     └─────────────────────────┘
            │ Valid
            ▼
┌─────────────────────────┐
│ Validate password       │
│ strength requirements   │
└───────────┬─────────────┘
            │ Valid
            ▼
┌─────────────────────────┐
│ Hash new password       │
│ Update user             │
│ Invalidate token        │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────┐
│ Response: "Password has been reset successfully."                │
└─────────────────────────────────────────────────────────────────┘
```

---

## API Endpoints

### POST /api/v1/auth/forgot-password

Request a password reset link.

**Request Body:**
```json
{
  "email": "user@example.com"
}
```

**Success Response (200 OK):**
```json
{
  "message": "If an account with this email exists, a password reset link has been sent.",
  "email": "user@example.com"
}
```

**Error Responses:**
- `503 Service Unavailable`: Redis connection failed

---

### POST /api/v1/auth/reset-password

Complete the password reset using the token from the email.

**Request Body:**
```json
{
  "token": "Abc123...XYZ",
  "password": "NewSecureP@ss123",
  "confirm_password": "NewSecureP@ss123"
}
```

**Success Response (200 OK):**
```json
{
  "message": "Password has been reset successfully. You can now log in with your new password."
}
```

**Error Responses:**
- `400 Bad Request`: Invalid or expired token
- `422 Unprocessable Content`: Password validation failed
- `503 Service Unavailable`: Redis connection failed

---

## Implementation Details

### Files Modified/Created

| File | Changes |
|------|---------|
| `schema/security.py` | Added `ForgotPasswordRequest`, `ForgotPasswordResponse`, `ResetPasswordRequest`, `ResetPasswordResponse` |
| `services/verification.py` | Added `PasswordResetService` class and `get_password_reset_service()` factory |
| `services/auth_service.py` | Added `forgot_password()` and `reset_password()` methods |
| `repositories/landlord_repository.py` | Added `find_by_email()` method |
| `routers/auth.py` | Added `/forgot-password` and `/reset-password` endpoints |
| `templates/emails/password_reset_email.html` | Email template for reset link |

### PasswordResetService Methods

```python
class PasswordResetService:
    # Configuration
    TOKEN_EXPIRY = timedelta(hours=1)
    MAX_REQUESTS_PER_HOUR = 3
    MAX_TOKEN_ATTEMPTS = 5
    
    def request_password_reset(self, email: str) -> bool:
        """Generate token, store in Redis, send email."""
        
    def validate_reset_token(self, token: str) -> Optional[str]:
        """Validate token, return email if valid."""
        
    def complete_password_reset(self, token: str) -> Optional[str]:
        """Validate and invalidate token (one-time use)."""
```

### Redis Key Structure

| Key Pattern | Purpose | TTL |
|------------|---------|-----|
| `password_reset:token:{token}` | Maps token to email | 1 hour |
| `password_reset:rate:{email}` | Rate limit counter | 1 hour |
| `password_reset:attempts:{token}` | Failed validation attempts | 1 hour |

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `FRONTEND_BASE_URL` | Base URL for password reset links | `https://findmyrent.com` |
| `REDIS_HOST` | Redis server host | `localhost` |
| `REDIS_PORT` | Redis server port | `6379` |

### Password Requirements

- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one number
- At least one special character (`@$!%*?&#`)

---

## Error Handling

### Rate Limiting

When a user exceeds 3 password reset requests per hour:
- The rate limit is tracked in Redis
- Requests are blocked for the remainder of the hour
- The standard success message is still returned (to prevent enumeration)

### Token Validation Failures

When a token fails validation 5 times:
- The token is automatically invalidated
- User must request a new password reset link

### Service Unavailability

If Redis is unavailable:
- Returns 503 Service Unavailable
- User is prompted to try again later

---

## Email Template

The password reset email uses the standard FindMyRent template styling:
- Purple gradient header
- Prominent "Reset My Password" button
- Fallback link for copy/paste
- 1-hour expiry notice
- Security warning for unauthorized requests
- Security tips section

Template location: `templates/emails/password_reset_email.html`

---

## Testing

### Test Coverage

The password reset feature includes **16 integration tests** across 2 test classes in `tests/integration/test_routers/test_auth_endpoints.py`:

**TestForgotPassword (5 tests):**
- `test_forgot_password_success` - Successful request returns expected response
- `test_forgot_password_invalid_email_format` - Invalid email format rejected
- `test_forgot_password_missing_email` - Missing email field rejected
- `test_forgot_password_empty_email` - Empty email rejected
- `test_forgot_password_service_unavailable` - Redis down returns 503

**TestResetPassword (11 tests):**
- `test_reset_password_success` - Valid token and password resets successfully
- `test_reset_password_token_too_short` - Token < 64 chars rejected
- `test_reset_password_missing_token` - Missing token rejected
- `test_reset_password_passwords_dont_match` - Mismatched passwords rejected
- `test_reset_password_weak_password_no_uppercase` - Password strength validated
- `test_reset_password_weak_password_no_lowercase` - Password strength validated
- `test_reset_password_weak_password_no_number` - Password strength validated
- `test_reset_password_weak_password_no_special_char` - Password strength validated
- `test_reset_password_password_too_short` - Password < 8 chars rejected
- `test_reset_password_invalid_token` - Invalid/expired token returns 400
- `test_reset_password_service_unavailable` - Redis down returns 503

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run only password reset tests
pytest tests/integration/test_routers/test_auth_endpoints.py -v -k "password"

# Run with coverage
pytest tests/ --cov=. --cov-report=html
```

### Manual Testing

1. Request password reset:
```bash
curl -X POST http://localhost:8000/api/v1/auth/forgot-password \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com"}'
```

2. Complete password reset (with token from email):
```bash
curl -X POST http://localhost:8000/api/v1/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{
    "token": "your-token-here",
    "password": "NewP@ssword123",
    "confirm_password": "NewP@ssword123"
  }'
```

