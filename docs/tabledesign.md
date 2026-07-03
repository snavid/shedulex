# Shedulex Database Table Design (Section 3.5)

**Project:** Shedulex — Intelligent Dynamic Academic Timetable Management System  
**DBMS:** PostgreSQL 16  
**Pattern:** Database-per-service (8 databases)  
**ORM:** SQLAlchemy with Alembic migrations

This document replaces the outdated single-database design (`Subjects`, `Venues`, `TimetableSlots`, `INT` keys) with the **actual implemented Shedulex schema**.

---

## 3.5 Database Design

Shedulex uses PostgreSQL with a **database-per-service** pattern. Each microservice owns its tables independently. Primary keys are **UUID strings** (`VARCHAR(36)`), not auto-increment integers.

| Database | Microservice | Purpose |
|----------|--------------|---------|
| `auth_db` | auth-service | Users, roles, sessions |
| `timetable_db` | timetable-engine | Scheduling entities, GA data, timetables |
| `adjustment_db` | adjustment-engine | AI assistant sessions and conflict logs |
| `notification_db` | notification-service | SMS/email notifications |
| `calendar_db` | calendar-service | Academic events, semesters, holidays |
| `document_db` | document-service | Export audit trail |
| `analytics_db` | analytics-service | No local tables (queries timetable-service) |
| `audit_db` | audit-service | Security and activity audit logs |

---

## 3.5.1 System Tables Overview

### Table 3.1 — `auth_db` Tables

| Table Name | Description |
|------------|-------------|
| `roles` | System roles and permission sets (admin, timetable_officer, hod, lecturer, student) |
| `users` | User accounts with authentication credentials and profile data |
| `user_sessions` | Active JWT sessions for login tracking and revocation |

### Table 3.2 — `timetable_db` Tables (Core Scheduling)

| Table Name | Description |
|------------|-------------|
| `universities` | Institution profiles (e.g. KIUT) |
| `academic_years` | Academic year containers with semester date windows |
| `departments` | Academic departments within a university |
| `programs` | Study programmes (e.g. BIT, BCS) within departments |
| `student_groups` | Student cohorts/classes within programmes |
| `courses` | Course/module catalogue with credit hours and lab requirements |
| `lecturers` | Lecturer profiles, availability, and workload limits |
| `rooms` | Lecture halls, labs, and seminar rooms with capacity |
| `time_slots` | Schedulable day/time periods (linked to templates) |
| `timetable_templates` | Reusable daily period templates (e.g. Standard 8–5) |
| `template_time_blocks` | Named blocks within a template (Period 1, Lunch, etc.) |
| `timetables` | Generated timetable headers with GA fitness metadata |
| `timetable_entries` | Individual scheduled sessions (course + lecturer + room + slot) |
| `timetable_snapshots` | Versioned snapshots for restore |
| `constraints` | Hard/soft scheduling rules consumed by the Genetic Algorithm |
| `course_student_groups` | Junction: courses ↔ student groups (M:N) |
| `lecturer_programs` | Junction: lecturers ↔ programmes (M:N) |
| `course_group_lecturers` | Per-group lecturer overrides for shared courses |

### Table 3.3 — Supporting Service Tables

| Database | Table Name | Description |
|----------|------------|-------------|
| `adjustment_db` | `conversation_sessions` | Sora AI chat sessions with message history |
| `adjustment_db` | `adjustment_requests` | Legacy single-shot AI adjustment records |
| `adjustment_db` | `conflict_logs` | Logged timetable conflicts and resolutions |
| `notification_db` | `notification_templates` | Reusable SMS/email message templates |
| `notification_db` | `notifications` | Sent/queued notification records |
| `calendar_db` | `academic_events` | Calendar events (exams, deadlines, closures) |
| `calendar_db` | `academic_semesters` | Semester configuration and date ranges |
| `calendar_db` | `academic_holidays` | Public and institutional holidays |
| `document_db` | `export_events` | PDF/Excel/CSV export audit trail |
| `audit_db` | `audit_logs` | System-wide security and activity logs |

### Mapping: Old Design → Shedulex (Corrections)

| Old (Incorrect) | Correct Shedulex Table | Notes |
|-----------------|------------------------|-------|
| `Subjects` | `courses` | Renamed; linked to `programs` and `departments` |
| `Venues` | `rooms` | Includes `room_type`, equipment flags |
| `TimetableSlots` | `timetable_entries` + `time_slots` | **Split:** slots define periods; entries are scheduled sessions |
| `Users.role` ENUM column | `roles` + `users.role_id` | Normalized to 3NF |
| `Logs` | `audit_logs` | Separate microservice (`audit_db`) |
| `lecturer.department` VARCHAR | `lecturers.department_id` FK | FK to `departments` |
| `INT` primary keys | `VARCHAR(36)` UUID | All services use UUID strings |

---

## 3.5.2 Table Structures

### 3.5.2.1 `roles` Table — `auth_db`

**Table 3.4 roles Table**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PRIMARY KEY | Unique role identifier (UUID) |
| name | VARCHAR(50) | UNIQUE, NOT NULL | Role name (admin, timetable_officer, hod, lecturer, student) |
| description | VARCHAR(255) | NULL | Role description |
| permissions | JSON | DEFAULT [] | Permission list for RBAC |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Record creation timestamp |

---

### 3.5.2.2 `users` Table — `auth_db`

**Table 3.5 users Table**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PRIMARY KEY | Unique user identifier (UUID) |
| email | VARCHAR(255) | UNIQUE, NOT NULL, INDEX | Login email |
| username | VARCHAR(100) | UNIQUE, NOT NULL, INDEX | Username |
| password_hash | VARCHAR(255) | NOT NULL | Bcrypt-hashed password |
| first_name | VARCHAR(100) | NOT NULL | User first name |
| last_name | VARCHAR(100) | NOT NULL | User last name |
| phone | VARCHAR(20) | NULL | Contact phone number |
| department | VARCHAR(100) | NULL | Department label (display) |
| staff_id | VARCHAR(50) | UNIQUE, NULL | Institutional staff ID |
| university_id | VARCHAR(36) | NULL | Soft reference to timetable-service university |
| role_id | VARCHAR(36) | FK → roles(id), NOT NULL | Assigned role |
| is_active | BOOLEAN | DEFAULT TRUE | Account active flag |
| is_approved | BOOLEAN | DEFAULT TRUE | Admin approval flag |
| is_verified | BOOLEAN | DEFAULT FALSE | Email verification flag |
| must_change_password | BOOLEAN | DEFAULT FALSE | Force password change on login |
| verification_token | VARCHAR(255) | NULL | Email verification token |
| reset_token | VARCHAR(255) | NULL | Password reset token |
| reset_token_expires | TIMESTAMPTZ | NULL | Reset token expiry |
| last_login | TIMESTAMPTZ | NULL | Last successful login |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Account creation date |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | Last update timestamp |

---

### 3.5.2.3 `user_sessions` Table — `auth_db`

**Table 3.6 user_sessions Table**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PRIMARY KEY | Session identifier |
| user_id | VARCHAR(36) | FK → users(id), NOT NULL | Session owner |
| jti | VARCHAR(255) | UNIQUE, NOT NULL, INDEX | JWT token ID |
| device_info | VARCHAR(500) | NULL | Client device description |
| ip_address | VARCHAR(45) | NULL | Client IP address |
| is_active | BOOLEAN | DEFAULT TRUE | Session active flag |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Session start time |
| expires_at | TIMESTAMPTZ | NULL | Session expiry time |

---

### 3.5.2.4 `universities` Table — `timetable_db`

**Table 3.7 universities Table**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PRIMARY KEY | University identifier |
| name | VARCHAR(200) | UNIQUE, NOT NULL | Full university name |
| code | VARCHAR(20) | UNIQUE, NOT NULL | Short code (e.g. KIUT) |
| address | VARCHAR(300) | NULL | Physical address |
| website | VARCHAR(255) | NULL | University website URL |
| logo_url | VARCHAR(500) | NULL | Logo image URL |
| is_active | BOOLEAN | DEFAULT TRUE | Active status |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Record creation date |

---

### 3.5.2.5 `departments` Table — `timetable_db`

**Table 3.8 departments Table**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PRIMARY KEY | Department identifier |
| name | VARCHAR(150) | NOT NULL | Department name |
| code | VARCHAR(20) | NOT NULL | Department code |
| faculty | VARCHAR(150) | NULL | Parent faculty name |
| head_name | VARCHAR(150) | NULL | Head of department name |
| university_id | VARCHAR(36) | FK → universities(id) | Owning university |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Record creation date |

**Unique constraint:** `(code, university_id)`

---

### 3.5.2.6 `programs` Table — `timetable_db`

**Table 3.9 programs Table**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PRIMARY KEY | Programme identifier |
| name | VARCHAR(200) | NOT NULL | Programme name (e.g. Bachelor of IT) |
| code | VARCHAR(20) | NOT NULL | Programme code (e.g. BIT) |
| department_id | VARCHAR(36) | FK → departments(id), NOT NULL | Owning department |
| academic_level | VARCHAR(50) | NOT NULL, DEFAULT 'Bachelor' | Certificate, Diploma, Bachelor, Master, PhD |
| duration_years | INTEGER | DEFAULT 3 | Programme duration |
| description | VARCHAR(500) | NULL | Programme description |
| is_active | BOOLEAN | DEFAULT TRUE | Active status |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Record creation date |

**Unique constraint:** `(code, department_id)`

---

### 3.5.2.7 `courses` Table — `timetable_db`

*Replaces the old `Subjects` table.*

**Table 3.10 courses Table**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PRIMARY KEY | Course identifier |
| name | VARCHAR(200) | NOT NULL | Course title |
| code | VARCHAR(20) | UNIQUE, NOT NULL | Course code (e.g. BIT201) |
| department_id | VARCHAR(36) | FK → departments(id) | Offering department |
| program_id | VARCHAR(36) | FK → programs(id) | Parent programme |
| lecturer_id | VARCHAR(36) | FK → lecturers(id) | Default lecturer |
| semester | INTEGER | NOT NULL, DEFAULT 1 | Semester number |
| year_of_study | INTEGER | NOT NULL, DEFAULT 1 | Year of study |
| credit_hours | INTEGER | DEFAULT 3 | Credit hours |
| weekly_hours | INTEGER | DEFAULT 3 | Contact hours per week |
| student_count | INTEGER | DEFAULT 30 | Enrolled students |
| requires_lab | BOOLEAN | DEFAULT FALSE | Requires lab room (GA hard constraint) |
| course_type | VARCHAR(50) | DEFAULT 'core' | core, elective, lab |
| priority | INTEGER | DEFAULT 1 | GA scheduling priority (higher first) |
| is_active | BOOLEAN | DEFAULT TRUE | Active status |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Record creation date |

---

### 3.5.2.8 `lecturers` Table — `timetable_db`

**Table 3.11 lecturers Table**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PRIMARY KEY | Lecturer identifier |
| user_id | VARCHAR(36) | NULL | Soft reference to auth-service user |
| name | VARCHAR(150) | NOT NULL | Lecturer full name |
| email | VARCHAR(255) | UNIQUE, NOT NULL | Contact email |
| phone | VARCHAR(20) | NULL | Contact phone |
| staff_id | VARCHAR(50) | UNIQUE, NULL | Institutional staff ID |
| department_id | VARCHAR(36) | FK → departments(id) | Home department |
| specialization | VARCHAR(200) | NULL | Area of specialization |
| max_hours_per_week | INTEGER | DEFAULT 20 | Weekly teaching hour limit |
| max_hours_per_day | INTEGER | DEFAULT 6 | Daily teaching hour limit |
| max_consecutive_hours | INTEGER | DEFAULT 3 | Max consecutive periods |
| preferred_days | JSON | DEFAULT [] | Preferred teaching days |
| unavailable_slots | JSON | DEFAULT [] | Explicitly blocked slot IDs |
| availability | JSON | DEFAULT {} | Available slots per day `{day: [slot_ids]}` |
| is_active | BOOLEAN | DEFAULT TRUE | Active status |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Record creation date |

---

### 3.5.2.9 `rooms` Table — `timetable_db`

*Replaces the old `Venues` table.*

**Table 3.12 rooms Table**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PRIMARY KEY | Room identifier |
| name | VARCHAR(100) | NOT NULL | Room display name |
| code | VARCHAR(20) | UNIQUE, NOT NULL | Room code |
| capacity | INTEGER | NOT NULL, DEFAULT 30 | Maximum student capacity |
| room_type | VARCHAR(50) | DEFAULT 'lecture' | lecture, lab, seminar |
| building | VARCHAR(100) | NULL | Building name |
| floor | INTEGER | DEFAULT 1 | Floor number |
| has_projector | BOOLEAN | DEFAULT TRUE | Projector available |
| has_lab_equipment | BOOLEAN | DEFAULT FALSE | Lab equipment available |
| is_available | BOOLEAN | DEFAULT TRUE | Available for scheduling |
| university_id | VARCHAR(36) | FK → universities(id), INDEX | Owning university |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Record creation date |

---

### 3.5.2.10 `time_slots` Table — `timetable_db`

*Defines **when** classes can occur. Not the same as `timetable_entries`.*

**Table 3.13 time_slots Table**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PRIMARY KEY | Time slot identifier |
| day | VARCHAR(20) | NOT NULL | Day of week (Monday–Saturday) |
| start_time | VARCHAR(10) | NOT NULL | Start time (e.g. 08:00) |
| end_time | VARCHAR(10) | NOT NULL | End time (e.g. 09:00) |
| slot_index | INTEGER | NULL | Sequential ordering within day |
| is_break | BOOLEAN | DEFAULT FALSE | Non-schedulable break period |
| slot_type | VARCHAR(20) | DEFAULT 'class' | class, break, lunch, lab, exam |
| label | VARCHAR(100) | NULL | Display label (e.g. Period 1) |
| template_id | VARCHAR(36) | FK → timetable_templates(id) | Parent template |
| academic_year | VARCHAR(20) | NULL | Academic year scope |

---

### 3.5.2.11 `constraints` Table — `timetable_db`

**Table 3.14 constraints Table**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PRIMARY KEY | Constraint identifier |
| name | VARCHAR(200) | NOT NULL | Constraint display name |
| constraint_type | VARCHAR(50) | NOT NULL | hard or soft |
| category | VARCHAR(100) | NULL | lecturer, room, student, academic, system |
| rule_type | VARCHAR(100) | NULL | GA rule routing key (e.g. max_daily_hours) |
| entity_type | VARCHAR(50) | NULL | Scoped entity type |
| entity_id | VARCHAR(36) | NULL | Scoped entity ID |
| university_id | VARCHAR(36) | NULL | University scope |
| department_id | VARCHAR(36) | FK → departments(id) | Department scope |
| weight | FLOAT | DEFAULT 1.0 | Soft constraint penalty weight |
| config | JSON | DEFAULT {} | Rule-specific parameters |
| is_active | BOOLEAN | DEFAULT TRUE | Active flag |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Record creation date |

---

### 3.5.2.12 `timetables` Table — `timetable_db`

**Table 3.15 timetables Table**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PRIMARY KEY | Timetable identifier |
| name | VARCHAR(200) | NOT NULL | Timetable title |
| semester | INTEGER | NOT NULL | Semester number |
| academic_year | VARCHAR(20) | NOT NULL | Academic year label (e.g. 2025-2026) |
| department_id | VARCHAR(36) | FK → departments(id) | Department scope |
| program_id | VARCHAR(36) | FK → programs(id) | Programme scope |
| template_id | VARCHAR(36) | FK → timetable_templates(id) | Period template used |
| academic_year_id | VARCHAR(36) | FK → academic_years(id) | Academic year record |
| calendar_semester_id | VARCHAR(36) | NULL | Soft ref to calendar-service semester |
| status | VARCHAR(30) | DEFAULT 'draft' | draft, generating, active, archived |
| version | INTEGER | DEFAULT 1 | Version number |
| fitness_score | FLOAT | NULL | Best GA fitness score |
| violation_report | JSON | DEFAULT [] | GA violation summary |
| generation_time_seconds | FLOAT | NULL | GA runtime in seconds |
| generations_run | INTEGER | NULL | GA generations executed |
| created_by | VARCHAR(36) | NULL | User who generated timetable |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | Creation timestamp |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | Last update timestamp |

---

### 3.5.2.13 `timetable_entries` Table — `timetable_db`

*Replaces the old `TimetableSlots` table. Each row is one **scheduled session**.*

**Table 3.16 timetable_entries Table**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PRIMARY KEY | Entry identifier |
| timetable_id | VARCHAR(36) | FK → timetables(id), NOT NULL, INDEX | Parent timetable |
| course_id | VARCHAR(36) | FK → courses(id), NOT NULL | Scheduled course |
| lecturer_id | VARCHAR(36) | FK → lecturers(id), NOT NULL, INDEX | Assigned lecturer |
| room_id | VARCHAR(36) | FK → rooms(id), NOT NULL, INDEX | Assigned room |
| time_slot_id | VARCHAR(36) | FK → time_slots(id), NOT NULL, INDEX | Assigned time period |
| student_group_id | VARCHAR(36) | FK → student_groups(id) | Target student group |
| is_locked | BOOLEAN | DEFAULT FALSE | Locked entries cannot be moved |
| notes | VARCHAR(500) | NULL | Optional session notes |

---

### 3.5.2.14 `audit_logs` Table — `audit_db`

*Replaces the old generic `Logs` table.*

**Table 3.17 audit_logs Table**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | VARCHAR(36) | PRIMARY KEY | Log entry identifier |
| user_id | VARCHAR(36) | INDEX | User who performed action |
| university_id | VARCHAR(36) | INDEX, NULL | University scope |
| action | VARCHAR(100) | NOT NULL | Action name (e.g. timetable.generate) |
| resource_type | VARCHAR(100) | NULL | Affected resource type |
| resource_id | VARCHAR(36) | NULL | Affected resource ID |
| description | TEXT | NULL | Human-readable description |
| ip_address | VARCHAR(45) | NULL | Client IP address |
| user_agent | VARCHAR(500) | NULL | Client user agent |
| service | VARCHAR(50) | NULL | Originating microservice |
| status | VARCHAR(20) | DEFAULT 'success' | success, failure, warning |
| metadata | JSON | DEFAULT {} | Additional structured data |
| created_at | TIMESTAMPTZ | DEFAULT NOW(), INDEX | Action timestamp |

---

### 3.5.2.15 Junction Tables — `timetable_db`

**Table 3.18 course_student_groups**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| course_id | VARCHAR(36) | PK, FK → courses(id) | Course |
| student_group_id | VARCHAR(36) | PK, FK → student_groups(id) | Student group |

**Table 3.19 lecturer_programs**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| lecturer_id | VARCHAR(36) | PK, FK → lecturers(id) | Lecturer |
| program_id | VARCHAR(36) | PK, FK → programs(id) | Programme |

**Table 3.20 course_group_lecturers**

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| course_id | VARCHAR(36) | PK, FK → courses(id) | Course |
| student_group_id | VARCHAR(36) | PK, FK → student_groups(id) | Student group |
| lecturer_id | VARCHAR(36) | FK → lecturers(id), NULL | Override lecturer for this group |

---

## 3.5.3 Entity Relationship Summary

```
universities
  ├── departments
  │     ├── programs → student_groups
  │     ├── courses ←→ student_groups (course_student_groups)
  │     ├── lecturers ←→ programs (lecturer_programs)
  │     └── constraints
  ├── rooms
  └── academic_years → timetables
                          └── timetable_entries
                                ├── courses
                                ├── lecturers
                                ├── rooms
                                ├── time_slots
                                └── student_groups

timetable_templates → template_time_blocks
                   → time_slots

auth: roles → users → user_sessions
audit: audit_logs
notification: notification_templates, notifications
adjustment: conversation_sessions, conflict_logs
calendar: academic_events, academic_semesters, academic_holidays
document: export_events
```

---

## 3.5.4 Notes for Report

1. **Use `courses` not `Subjects`** — the codebase uses `courses` throughout (`Backend/timetable-engine/app/models/domain.py`).
2. **Use `rooms` not `Venues`** — includes `room_type` and equipment flags for GA constraints.
3. **`timetable_entries` ≠ `time_slots`** — slots define available periods; entries are GA output sessions.
4. **`audit_logs` not `Logs`** — logging is a separate microservice, not embedded in timetable tables.
5. **Roles are normalized** — `users.role_id` references `roles.id`; no ENUM column on users.
6. **All PKs are UUID** — `VARCHAR(36)`, generated via `uuid.uuid4()`.

For normalization examples (1NF → 3NF), see [`normalization.md`](./normalization.md).

---

*Source: `Backend/timetable-engine/app/models/domain.py`, `Backend/auth-service/app/models/user.py`, `Backend/audit-service/app/models/audit_log.py`, `scripts/init_databases.sql`*
