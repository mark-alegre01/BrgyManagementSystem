# PhilSys ID Authentication Integration Documentation

## Overview

The Philippine Identification System (PhilSys), now rebranded as the National ID System, is the government's unified national ID program managed by the Philippine Statistics Authority (PSA). This document outlines the integration of PhilSys for resident verification in the Barangay Management System.

## PhilSys ID Types

### 1. Physical PhilID (formerly ePhilID)
- PVC card issued by PSA
- Contains a QR code at the back
- Security features: holograms, microprinting, ghost photo
- Version 1: Legacy PhilID (dark blue)
- Version 3: New ePhilID (with updated design)

### 2. Digital National ID
- Available via PhilSys website or eGov PH app
- QR code that can be scanned for verification
- Accepted as valid proof of identity (PSA Advisory June 2024)

### 3. PhilSys Number (PSN)
- Unique 12-digit number assigned to each registrant
- Can be used for verification via the PhilSys Check portal

## Verification Methods

### Method 1: QR Code Verification (Recommended)

**Endpoint:** `POST /api/philsys/verify-qr`

Scan the QR code on the PhilID/ePhilID card using the device camera. The QR contains:
- Personal information (Name, DOB, POB)
- Photo (in encrypted form)
- Digital signature

**Process:**
1. User presents PhilID/ePhilID
2. App scans QR code
3. Server validates QR signature
4. Server optionally checks with PhilSys online API
5. Returns verified demographic data

### Method 2: PhilSys Number (PSN) Verification

**Endpoint:** `POST /api/philsys/verify-psn`

Verify using the 12-digit PhilSys Number against PSA records.

### Method 3: Biometric Verification

**Endpoint:** `POST /api/philsys/verify-biometric`

Match user's selfie against the biometric template stored in PhilSys. Requires:
- User takes a liveness selfie
- System compares with PSA biometric database
- Returns match result

## Integration Options

### Option A: Using Official PhilSys eVerify API

The PSA provides an eVerify portal at `https://verify.philsys.gov.ph/`

**API Endpoints:**
- QR Classification: `POST /api/pub/qr/check`
- Full Verification: `POST /api/pub/qr/verify`

**Requirements:**
- Registration as a Relying Party (RP) with PSA
- API credentials/token
- Compliance with PSA data privacy policies

### Option B: Using Third-Party Services

| Provider | Service | Features |
|----------|---------|----------|
| **Trinsic** | PhilSys Biometric Match | Biometric verification, 90M+ records |
| **Zenoo** | PhilSys Biometric Match | Identity verification API |
| **Kairos** | NIDAS | National ID Authentication |
| **V-Key** | Digital Identity Solutions | Secure digital verification |

### Option C: OpenVerify (Open Source)

**Repository:** https://github.com/bettergovph/openverify

A developer-focused toolkit for PhilSys QR verification:
- Detects Version 1 (legacy) and Version 3 (ePhilID) cards
- Performs signature validation
- Server proxy to PhilSys verification API
- Image-to-QR extraction endpoint
- eVerify support for digital IDs

**Endpoints:**
- `POST /api/scan-image` - Upload image, extract and verify QR
- `POST /api/verify` - Forward to PhilSys verifier
- `POST /api/everify/check` - Classify QR type
- `GET /api/everify/egov-ph` - Fetch eGovPH profile

## Implementation Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Barangay Management System                   │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐ │
│  │   Web App  │    │ Mobile App  │    │   QR Scanner UI     │ │
│  └──────┬──────┘    └──────┬──────┘    └──────────┬──────────┘ │
└─────────┼──────────────────┼──────────────────────┼─────────────┘
          │                  │                      │
          ▼                  ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Authentication Layer                       │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │              PhilSys Verification Service                   ││
│  │  • QR Signature Validation                                   ││
│  │  • CBOR Decoding (ePhilID)                                   ││
│  │  • Ed25519 Signature Check (Legacy PhilID)                   ││
│  │  • PSA API Integration                                       ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    External Services                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ PhilSys API │  │  eGov PH    │  │  PSA Database          │ │
│  │ (verify.)   │  │  Consent    │  │  (via registered RP)   │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

### Resident Registration with PhilSys Verification

1. **Resident presents PhilID**
   - User shows physical PhilID or Digital National ID

2. **QR Code Scanning**
   - App scans QR using device camera
   - QR decoded to extract COSE_Sign1 structure

3. **Signature Validation**
   - Verify Ed25519 signature using PSA public key
   - Decrypt CBOR payload for ePhilID
   - Extract demographic data

4. **Data Matching (Optional)**
   - Submit to PSA API for online verification
   - Get activation status (ACTIVATED/REVOKED)

5. **Account Creation**
   - Map PhilSys data to resident record
   - Link PhilSys Number (PSN) to account
   - Store verification timestamp

## QR Code Structure

### Legacy PhilID (Version 1)
```
{
  "d": "2022-05-11",           # Issue date
  "i": "PSA",                  # Issuer
  "img": "...",                # Base64 photo (optional)
  "sb": {                      # Subject
    "BF": "[6,3]",             # Biometric format
    "DOB": "2003-05-27",       # Date of birth
    "PCN": "2795801750683042", # PhilSys Card Number
    "POB": "City of...",       # Place of birth
    "fn": "FIRSTNAME",         # First name
    "ln": "LASTNAME",          # Last name
    "mn": "MIDDLENAME",        # Middle name
    "s": "Male"                # Sex
  }
}
```

### ePhilID (Version 3)
- Base45 encoded
- Compressed with ZLIB
- CBOR structure with:
  - PersonalInfo: Name, DOB, POB, Sex
  - Photo: JPEG in base64
  - Signature: COSE_Sign1

## API Endpoints

### POST /api/auth/philsys/send-otp
Request OTP for PhilSys-linked phone number.

### POST /api/auth/philsys/verify-otp
Verify OTP and create authenticated session.

### POST /api/philsys/verify-qr
Verify PhilID QR code.

**Request:**
```json
{
  "qr_data": "base64_encoded_qr_string"
}
```

**Response:**
```json
{
  "verified": true,
  "personal_info": {
    "first_name": "JUAN",
    "last_name": "DELA CRUZ",
    "middle_name": "MARIANO",
    "birthdate": "1990-01-01",
    "place_of_birth": "City of Manila",
    "sex": "Male",
    "nationality": "Filipino"
  },
  "psn": "123456789012",
  "pcn": "2795801750683042",
  "status": "ACTIVATED",
  "verification_timestamp": "2024-01-15T10:30:00Z"
}
```

### POST /api/philsys/verify-psn
Verify using PhilSys Number.

**Request:**
```json
{
  "psn": "123456789012",
  "birthdate": "1990-01-01"
}
```

### GET /api/residents/{id}/philsys-status
Get PhilSys verification status for a resident.

## Security Considerations

### Data Privacy
- PhilSys data is sensitive personal information
- Comply with Data Privacy Act of 2012 (Philippines)
- Obtain explicit consent before processing
- Encrypt data at rest and in transit
- Implement data retention policies

### Authentication Security
- Use TLS 1.3 for all connections
- Implement rate limiting on verification endpoints
- Log all verification attempts
- Use secure session management
- Implement biometric liveness detection

### PSA Compliance
- Register as Relying Party with PSA
- Follow PSA API usage guidelines
- Display appropriate disclaimers
- Provide audit logs when requested
- Comply with PSA Terms of Service

## Environment Variables

```bash
# PhilSys Configuration
PHILSYS_API_URL=https://verify.philsys.gov.ph
PHILSYS_API_KEY=your_api_key
PHILSYS_PUBLIC_KEY=base64_encoded_ed25519_key
PHILSYS_COOKIE=__verify-token=xxx; _ga=xxx

# Optional: Third-party service
TRINSIC_API_KEY=your_trinsic_key
```

## Error Codes

| Code | Description |
|------|-------------|
| PHILSYS_001 | Invalid QR code format |
| PHILSYS_002 | QR signature verification failed |
| PHILSYS_003 | Expired/Revoked PhilID |
| PHILSYS_004 | Network error connecting to PSA |
| PHILSYS_005 | Invalid PSN format |
| PHILSYS_006 | Biometric match failed |
| PHILSYS_007 | PSA API authentication failed |

## Best Practices

1. **Offline-first verification**: Implement offline QR validation first, then optionally verify online
2. **Graceful degradation**: If PhilSys API is unavailable, allow manual verification with supervisor approval
3. **Multiple ID types**: Support both physical PhilID and Digital National ID
4. **Audit trail**: Log all verification attempts with timestamps and user IDs
5. **User consent**: Display clear consent dialog before processing PhilSys data
6. **Error handling**: Provide clear error messages to users when verification fails
7. **Fallback options**: Have backup verification methods for edge cases

## References

- [PhilSys Official Website](https://philsys.gov.ph)
- [PhilSys eVerify](https://verify.philsys.gov.ph)
- [eGov PH App](https://philsys.gov.ph/ephilid/)
- [OpenVerify GitHub](https://github.com/bettergovph/openverify)
- [PSA Advisory on Digital National ID](https://philsys.gov.ph/public-advisory-19/)
- [Trinsic PhilSys Documentation](https://docs.trinsic.id/docs/philsys-biometric-match)
- [Republic Act No. 11055](https://www.officialgazette.gov.ph/2017/08/02/republic-act-no-11055/) - PhilSys Act

---

**Document Version:** 1.0  
**Last Updated:** February 2024  
**Author:** Barangay System Development Team
