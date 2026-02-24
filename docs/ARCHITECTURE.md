# Barangay Management System - Technical Architecture

## System Overview

 technical architecture for aThis document outlines the comprehensive Barangay Management System designed to digitize and streamline barangay operations in the Philippines. The system uses PhilSys ID (National ID) for authentication instead of SMS OTP.

---

## Technology Stack

| Layer | Technology | Notes |
|-------|------------|-------|
| **Web Frontend** | React + TypeScript + Vite | Responsive admin dashboard |
| **Mobile App** | Flutter | Cross-platform (iOS/Android) |
| **Backend API** | Django REST Framework (Python) | RESTful API |
| **Database** | PostgreSQL / SQLite (development) | Relational data |
| **Auth** | **PhilSys ID (National ID)** | QR code + biometric verification |

---

## Role-Based Access Control (RBAC) Design

### User Roles & Permissions Matrix

| Role | Dashboard | Documents | Peace & Order | Health | Finance | Residents | Announcements | Settings |
|------|-----------|-----------|---------------|--------|---------|-----------|---------------|----------|
| **Punong Barangay** | Full | Full | Full | Full | Full | Full | Full | Full |
| **Secretary** | View | Full | View | View | View | Full | Full | Limited |
| **Treasurer** | View | View | View | View | Full | View | View | Limited |
| **Kagawad** | Committee | Committee | Committee | Committee | View | View | Publish | Limited |
| **SK Chairperson** | Youth Stats | Limited | View | View | View | Youth | Youth | Limited |
| **Lupong Tagapamayapa** | Mediation | View | Full | View | View | View | View | Limited |
| **Resident** | Public | Request | Report | View | View | Own | View | Own Profile |

---

## Authentication Flow (PhilSys ID)

### Primary Authentication: PhilSys QR Verification

```
┌──────────────────────────────────────────────────────────────────┐
│                        Login Flow                                 │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  1. User opens app                                               │
│         │                                                        │
│         ▼                                                        │
│  2. User clicks "Login with PhilSys"                             │
│         │                                                        │
│         ▼                                                        │
│  3. App displays QR Scanner                                      │
│         │                                                        │
│         ▼                                                        │
│  4. User scans PhilID/ePhilID QR code                            │
│         │                                                        │
│         ▼                                                        │
│  5. App decodes QR → extracts COSE_Sign1 structure               │
│         │                                                        │
│         ▼                                                        │
│  6. Server validates Ed25519 signature                           │
│         │                                                        │
│         ▼                                                        │
│  7. (Optional) Server checks PSA API for activation status        │
│         │                                                        │
│         ▼                                                        │
│  8. Server creates authenticated session                         │
│         │                                                        │
│         ▼                                                        │
│  9. User redirected to role-based dashboard                      │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

### Secondary Authentication: PSN + Biometric

For additional security or offline scenarios:
- User enters PhilSys Number (12-digit)
- User takes liveness selfie
- System matches biometric against PSA records

---

## Database Schema

### Core Tables

#### users
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| username | VARCHAR(150) | Unique username |
| email | VARCHAR(255) | User email |
| password_hash | VARCHAR(255) | Bcrypt hash |
| role | ENUM | User role (captain, secretary, etc.) |
| is_active | BOOLEAN | Account status |
| created_at | TIMESTAMP | Creation date |
| updated_at | TIMESTAMP | Last update |

#### residents
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| philSys_number | VARCHAR(12) | PhilSys Number (PSN) |
| philSys_card_number | VARCHAR(16) | PhilSys Card Number (PCN) |
| last_name | VARCHAR(100) | Last name |
| first_name | VARCHAR(100) | First name |
| middle_name | VARCHAR(100) | Middle name |
| suffix | VARCHAR(20) | Name suffix |
| birthdate | DATE | Date of birth |
| birthplace | VARCHAR(200) | Place of birth |
| gender | ENUM | Male/Female |
| civil_status | ENUM | Marital status |
| nationality | VARCHAR(100) | Nationality |
| address | TEXT | Full address |
| purok | VARCHAR(100) | Purok/Zone |
| contact_number | VARCHAR(20) | Phone number |
| email | VARCHAR(255) | Email address |
| household_id | UUID | FK to households |
| is_philsys_verified | BOOLEAN | PhilSys verification status |
| philsys_verified_at | TIMESTAMP | Verification timestamp |
| photo | VARCHAR(500) | Photo URL |
| is_active | BOOLEAN | Record status |
| created_at | TIMESTAMP | Creation date |
| updated_at | TIMESTAMP | Last update |

#### households
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| household_no | VARCHAR(50) | Household number |
| address | TEXT | Full address |
| purok | VARCHAR(100) | Purok/Zone |
| created_at | TIMESTAMP | Creation date |
| updated_at | TIMESTAMP | Last update |

#### barangay_officials
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| user_id | UUID | FK to users |
| resident_id | UUID | FK to residents |
| position | ENUM | Official position |
| committee_assignments | JSON | Committee assignments |
| term_start | DATE | Term start date |
| term_end | DATE | Term end date |
| is_active | BOOLEAN | Active status |

#### documents
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| type | ENUM | Document type |
| resident_id | UUID | FK to residents |
| status | ENUM | Pending/Approved/Rejected |
| submitted_by | UUID | FK to users |
| assigned_to | UUID | FK to users (approver) |
| notes | TEXT | Processing notes |
| created_at | TIMESTAMP | Creation date |
| updated_at | TIMESTAMP | Last update |

#### blotter
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| incident_date | DATE | Date of incident |
| incident_type | ENUM | Type of incident |
| description | TEXT | Incident description |
| location | VARCHAR(200) | Incident location |
| reporter_id | UUID | FK to residents |
| respondent_id | UUID | FK to residents (optional) |
| status | ENUM | Pending/Ongoing/Resolved |
| assigned_kagawad_id | UUID | FK to officials |
| resolution | TEXT | Resolution notes |
| created_at | TIMESTAMP | Creation date |
| updated_at | TIMESTAMP | Last update |

#### health_records
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| resident_id | UUID | FK to residents |
| record_type | ENUM | Medical record type |
| data | JSON | Record data |
| recorded_by | UUID | FK to users |
| created_at | TIMESTAMP | Creation date |

#### finances
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| type | ENUM | Income/Expense |
| category | VARCHAR(100) | Finance category |
| amount | DECIMAL(12,2) | Amount |
| description | TEXT | Description |
| receipt_number | VARCHAR(50) | Receipt number |
| created_by | UUID | FK to users |
| approved_by | UUID | FK to users |
| approved_at | TIMESTAMP | Approval timestamp |
| created_at | TIMESTAMP | Creation date |

#### announcements
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| title | VARCHAR(200) | Announcement title |
| content | TEXT | Full content |
| category | ENUM | Announcement category |
| priority | ENUM | Normal/Urgent |
| published_by | UUID | FK to users |
| published_at | TIMESTAMP | Publication date |
| expires_at | TIMESTAMP | Expiration date |
| created_at | TIMESTAMP | Creation date |

---

## API Endpoints

### Authentication

```
POST   /api/auth/philsys/verify-qr     # Verify PhilID QR code
POST   /api/auth/philsys/verify-psn    # Verify via PhilSys Number
POST   /api/auth/philsys/verify-bio    # Verify via biometric
POST   /api/auth/logout                # Logout
GET    /api/auth/me                    # Get current user
```

### Users & Profiles

```
GET    /api/users                       # List users (admin only)
POST   /api/users                       # Create user
GET    /api/users/{id}                 # Get user details
PUT    /api/users/{id}                 # Update user
DELETE /api/users/{id}                 # Delete user
GET    /api/users/roles                # Get available roles
```

### Residents

```
GET    /api/residents                   # List residents
POST   /api/residents                   # Create resident
GET    /api/residents/{id}              # Get resident details
PUT    /api/residents/{id}              # Update resident
DELETE /api/residents/{id}              # Delete resident
POST   /api/residents/{id}/verify-philsys  # Verify PhilSys
GET    /api/residents/{id}/philsys-status  # Get PhilSys status
GET    /api/residents/search            # Search residents
```

### Documents

```
GET    /api/documents                   # List documents
POST   /api/documents                   # Create document
GET    /api/documents/{id}              # Get document details
PUT    /api/documents/{id}              # Update document
DELETE /api/documents/{id}              # Delete document
POST   /api/documents/{id}/approve      # Approve document (captain)
POST   /api/documents/{id}/reject       # Reject document
GET    /api/documents/types             # Get document types
```

### Blotter / Peace & Order

```
GET    /api/blotter                     # List blotter entries
POST   /api/blotter                     # Create blotter entry
GET    /api/blotter/{id}                # Get blotter details
PUT    /api/blotter/{id}                # Update blotter entry
POST   /api/blotter/{id}/resolve        # Mark as resolved
POST   /api/blotter/{id}/assign         # Assign to kagawad
GET    /api/blotter/stats               # Get blotter statistics
```

### Health

```
GET    /api/health                      # List health records
POST   /api/health                      # Create health record
GET    /api/health/{id}                 # Get health record
PUT    /api/health/{id}                 # Update health record
GET    /api/health/resident/{id}        # Get resident's health records
GET    /api/health/stats                # Get health statistics
```

### Finance

```
GET    /api/finance                     # List finance records
POST   /api/finance                     # Create finance record
GET    /api/finance/{id}                # Get finance details
PUT    /api/finance/{id}                # Update finance record
POST   /api/finance/{id}/approve        # Approve (captain/treasurer)
GET    /api/finance/summary             # Get financial summary
GET    /api/finance/budget              # Get budget overview
```

### Announcements

```
GET    /api/announcements               # List announcements
POST   /api/announcements               # Create announcement
GET    /api/announcements/{id}          # Get announcement details
PUT    /api/announcements/{id}          # Update announcement
DELETE /api/announcements/{id}          # Delete announcement
POST   /api/announcements/{id}/publish  # Publish announcement
```

### Dashboard

```
GET    /api/dashboard/kpis              # Get KPI metrics
GET    /api/dashboard/activity          # Get recent activity
GET    /api/dashboard/alerts            # Get pending alerts
```

---

## UI Architecture per Role

### 1. Punong Barangay (Captain)

**Dashboard:**
- KPI cards: Total residents, Active documents, Pending blotter, Monthly collection
- Approval queue widget
- Quick actions: New announcement, Emergency broadcast
- Recent activity feed
- Alerts for urgent matters

**Sidebar Navigation:**
- Dashboard (Home)
- Documents (Full CRUD)
- Peace & Order (Full CRUD)
- Health Services (Full CRUD)
- Finance (Full CRUD)
- Residents (Full CRUD)
- Announcements (Full CRUD)
- Reports
- Settings

### 2. Secretary

**Dashboard:**
- Document tracking queue
- Recent submissions
- Quick submit button

**Primary Focus:**
- Document Management
- Resident Records

### 3. Treasurer

**Dashboard:**
- Financial summary widget
- Budget overview
- Recent transactions

**Primary Focus:**
- Finance/Budget tracking
- Disbursements

### 4. Kagawad (Committee-specific)

**Dashboard:**
- Committee-specific statistics
- Assigned tasks

**Sidebar:**
- Only modules relevant to assigned committee visible:
  - Committee on Health → Health module
  - Committee on Peace → Peace & Order module
  - Committee on Finance → Finance (view only)

### 5. SK Chairperson

**Dashboard:**
- Youth participation metrics
- Upcoming events

**Focus:**
- Youth programs
- SK projects

### 6. Lupong Tagapamayapa

**Dashboard:**
- Active disputes count
- Mediation schedule

**Focus:**
- Blotter/Dispute resolution
- Peace & Order

### 7. Resident (Public Portal)

**Dashboard:**
- Announcements feed
- My requests status

**Actions:**
- Submit document requests
- File reports/blotter
- View personal profile

---

## Mobile App Screens (Flutter)

### Captain/Treasurer/Secretary
- Home: Approvals, Alerts, Stats
- Menu: Full module access

### Kagawad
- Home: Committee tasks, Assigned cases
- Menu: Committee-specific modules

### Resident
- Home: Announcements, My Requests
- Actions: Request documents, File report, View status

---

## Implementation Phases

### Phase 1: Core Infrastructure
- [x] Project setup (Django backend, React frontend)
- [x] Database schema design
- [x] PhilSys authentication integration
- [x] Basic RBAC implementation

### Phase 2: Document Management
- [ ] Document request workflow
- [ ] Approval queue
- [ ] Document templates
- [ ] PDF generation

### Phase 3: Peace & Order
- [ ] Blotter system
- [ ] Incident reporting
- [ ] Case assignment
- [ ] Resolution tracking

### Phase 4: Health & Finance
- [ ] Health records management
- [ ] Finance tracking
- [ ] Budget overview
- [ ] Reports generation

### Phase 5: Announcements & Mobile
- [ ] Announcement system
- [ ] Push notifications
- [ ] Flutter mobile app
- [ ] Offline support

---

## Security Considerations

### Authentication
- PhilSys QR signature validation using Ed25519
- Optional biometric verification via PSA API
- Session tokens with configurable expiry
- Rate limiting on authentication endpoints

### Data Protection
- All API endpoints require authentication (except public announcements)
- Role-based access control at view level
- Input validation and sanitization
- SQL injection prevention via ORM

### Privacy Compliance
- Data Privacy Act of 2012 (Philippines) compliance
- PhilSys data handling per PSA guidelines
- User consent for data processing
- Data retention and disposal policies

---

## External Integrations

### PhilSys Verification
- Primary: OpenVerify (open-source) for QR validation
- Optional: PSA eVerify API (requires registration)
- Alternative: Third-party services (Trinsic, Zenoo)

### Push Notifications
- Firebase Cloud Messaging (FCM)

### File Storage
- Local filesystem (development)
- AWS S3 or equivalent (production)

---

## References

- [PhilSys Integration Documentation](./PHILSYS_INTEGRATION.md)
- [OpenVerify GitHub](https://github.com/bettergovph/openverify)
- [PhilSys Official](https://philsys.gov.ph)
- [PSA eVerify](https://verify.philsys.gov.ph)

---

**Document Version:** 2.0  
**Last Updated:** February 2024  
**Author:** Barangay System Development Team
