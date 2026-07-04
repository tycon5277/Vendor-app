# Test Credentials

## Vendor PWA (served on preview URL root, https://vendor-dashboard-app-2.preview.emergentagent.com)
- Regular Vendor Account: Phone `9999999999`, OTP `123456`
- Test shop 3 Fruits: Phone `1414141414`, OTP `123456`
- OTP is mocked; backend always accepts `123456`. `/api/auth/send-otp` returns `debug_otp` field.

## Webhooks
- Webhook Secret header: `X-Webhook-Secret: wh_sec_vendor_zone_2026`

## Notes
- Auth: phone + OTP via `POST /api/auth/send-otp` then `POST /api/auth/verify-otp` → returns `session_token` (Bearer token).
