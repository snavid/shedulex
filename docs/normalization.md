# Database Normalization — Shedulex (Third Normal Form)

**Project:** Shedulex — Intelligent Dynamic Academic Timetable Management System  
**Database:** PostgreSQL (`timetable_db`, `auth_db`, and related per-service databases)  
**Section:** 3.5.3 Third Normal Form (3NF)

This document illustrates how the Shedulex relational schema was derived through progressive normalization from an unnormalized manual timetable record (similar to spreadsheets used at KIUT) to Third Normal Form (3NF).

---

## 1. Introduction

Normalization is the process of organizing database tables to reduce redundancy and improve data integrity. For Shedulex, normalization ensures that:

- A lecturer's details are stored once and referenced by ID
- A room's capacity is not duplicated on every timetable row
- Course, department, and university data can be updated in one place
- The Genetic Algorithm reads consistent, non-contradictory scheduling data

The examples below use sample KIUT-style data. The **final tables match the implemented Shedulex schema** in `Backend/timetable-engine/app/models/domain.py`.

---

## 2. Starting Point — Unnormalized Relation

Before automation, timetable data at KIUT was often kept in a single spreadsheet row per scheduled session, repeating lecturer, room, and department details.

### Table: `UNNORMALIZED_TIMETABLE` ❌

| session_id | course_code | course_name | credit_hours | lecturer_name | lecturer_email | lecturer_dept | lecturer_max_hrs | room_name | room_capacity | room_building | room_type | dept_name | dept_code | university_name | day | start_time | end_time | student_group |
|------------|-------------|-------------|--------------|---------------|----------------|---------------|------------------|-----------|---------------|---------------|-----------|-----------|-----------|-----------------|-----|------------|----------|---------------|
| 1 | BIT201 | Database Systems | 3 | Dr. Amina Juma | amina@kiut.ac.tz | Computing | 20 | Lab-2 | 40 | Block C | lab | CIT | CIT | KIUT | Monday | 08:00 | 10:00 | BIT-Y2-A |
| 2 | BIT201 | Database Systems | 3 | Dr. Amina Juma | amina@kiut.ac.tz | Computing | 20 | Lab-2 | 40 | Block C | lab | CIT | CIT | KIUT | Wednesday | 08:00 | 10:00 | BIT-Y2-B |
| 3 | BIT301 | Software Eng. | 3 | Dr. Peter Mushi | peter@kiut.ac.tz | Computing | 18 | Hall-A | 120 | Block A | lecture | CIT | CIT | KIUT | Tuesday | 10:00 | 12:00 | BIT-Y3-A |

### Problems with this design

| Problem | Example |
|---------|---------|
| **Update anomaly** | Changing Dr. Amina's email requires updating every row she teaches |
| **Insert anomaly** | Cannot add a new room until it is assigned to a session |
| **Delete anomaly** | Deleting the last session in Hall-A removes all room information |
| **Redundancy** | `KIUT`, `CIT`, `Lab-2`, `Block C` repeated on every row |
| **Repeating groups** | One lecturer teaches multiple groups (BIT-Y2-A, BIT-Y2-B) in separate rows with duplicated lecturer data |

---

## 3. First Normal Form (1NF)

**Rule:** Eliminate repeating groups; ensure all columns contain atomic (indivisible) values; each row is unique.

### Violation — multi-valued student groups in one cell

| session_id | course_code | lecturer_name | room_name | day | start_time | student_groups |
|------------|-------------|---------------|-----------|-----|------------|----------------|
| 1 | BIT201 | Dr. Amina Juma | Lab-2 | Monday | 08:00 | BIT-Y2-A, BIT-Y2-B |

The column `student_groups` is **not atomic** — it stores multiple values in one field.

### Correction — one row per session–group assignment (1NF)

Split repeating groups into separate rows (or a separate link table in later steps):

| session_id | course_code | lecturer_name | room_name | day | start_time | end_time | student_group |
|------------|-------------|---------------|-----------|-----|------------|----------|---------------|
| 1 | BIT201 | Dr. Amina Juma | Lab-2 | Monday | 08:00 | 10:00 | BIT-Y2-A |
| 2 | BIT201 | Dr. Amina Juma | Lab-2 | Wednesday | 08:00 | 10:00 | BIT-Y2-B |
| 3 | BIT301 | Dr. Peter Mushi | Hall-A | Tuesday | 10:00 | 12:00 | BIT-Y3-A |

**1NF achieved:** Every column holds a single value; no repeating groups in cells.

---

## 4. Second Normal Form (2NF)

**Rule:** Be in 1NF, and every non-key attribute must depend on the **whole** primary key (no partial dependencies).

*Applicable when the primary key is composite.*

### Violation — partial dependency on composite key

Suppose the primary key is `(session_id, student_group)`:

| session_id | student_group | course_code | course_name | credit_hours | lecturer_name | room_capacity |
|------------|---------------|-------------|-------------|--------------|---------------|---------------|
| 1 | BIT-Y2-A | BIT201 | Database Systems | 3 | Dr. Amina Juma | 40 |
| 2 | BIT-Y2-B | BIT201 | Database Systems | 3 | Dr. Amina Juma | 40 |

- `course_name` and `credit_hours` depend only on `course_code`, not on `student_group`
- `room_capacity` depends only on the room, not on the full composite key

This creates **partial dependencies**.

### Correction — extract entity tables (2NF)

**Table: `courses`**

| id | code | name | credit_hours | department_id |
|----|------|------|--------------|---------------|
| c-001 | BIT201 | Database Systems | 3 | d-001 |
| c-002 | BIT301 | Software Engineering | 3 | d-001 |

**Table: `lecturers`**

| id | name | email | department_id | max_hours_per_week |
|----|------|-------|---------------|-------------------|
| l-001 | Dr. Amina Juma | amina@kiut.ac.tz | d-001 | 20 |
| l-002 | Dr. Peter Mushi | peter@kiut.ac.tz | d-001 | 18 |

**Table: `rooms`**

| id | code | name | capacity | building | room_type |
|----|------|------|----------|----------|-----------|
| r-001 | LAB-2 | Lab-2 | 40 | Block C | lab |
| r-002 | HALL-A | Hall-A | 120 | Block A | lecture |

**Table: `timetable_entries`** *(composite facts only)*

| id | timetable_id | course_id | lecturer_id | room_id | time_slot_id | student_group_id |
|----|--------------|-----------|-------------|---------|--------------|------------------|
| e-001 | tt-001 | c-001 | l-001 | r-001 | ts-01 | sg-001 |
| e-002 | tt-001 | c-001 | l-001 | r-001 | ts-03 | sg-002 |
| e-003 | tt-001 | c-002 | l-002 | r-002 | ts-05 | sg-003 |

**2NF achieved:** Course, lecturer, and room attributes moved to tables where the primary key fully determines them.

---

## 5. Third Normal Form (3NF)

**Rule:** Be in 2NF, and no non-key attribute depends on another non-key attribute (**no transitive dependencies**).

### Violation — transitive dependency

| room_id | room_name | building_name | building_address |
|---------|-----------|---------------|------------------|
| r-001 | Lab-2 | Block C | KIUT Main Campus, Dar es Salaam |
| r-002 | Hall-A | Block A | KIUT Main Campus, Dar es Salaam |

Here `building_address` depends on `building_name`, not directly on `room_id`:

```
room_id → building_name → building_address   (transitive)
```

Similarly, storing `university_name` inside `departments` while also storing `university_id` creates transitive dependency:

```
department_id → university_id → university_name, university_code
```

### Correction — separate lookup tables (3NF)

**Table: `universities`**

| id | name | code | address |
|----|------|------|---------|
| u-001 | Kampala International University in Tanzania | KIUT | Dar es Salaam, Tanzania |

**Table: `departments`**

| id | name | code | faculty | university_id |
|----|------|------|---------|---------------|
| d-001 | Computing & Information Technology | CIT | Science & Technology | u-001 |

**Table: `programs`**

| id | name | code | department_id | academic_level |
|----|------|------|---------------|----------------|
| p-001 | Bachelor of Information Technology | BIT | d-001 | Bachelor |

**Table: `student_groups`**

| id | name | code | program_id | year_of_study | semester | student_count |
|----|------|------|------------|---------------|----------|---------------|
| sg-001 | BIT Year 2 Group A | BIT-Y2-A | p-001 | 2 | 1 | 45 |
| sg-002 | BIT Year 2 Group B | BIT-Y2-B | p-001 | 2 | 1 | 42 |
| sg-003 | BIT Year 3 Group A | BIT-Y3-A | p-001 | 3 | 1 | 38 |

**Table: `rooms`** *(building kept as attribute; optional `buildings` table if campus grows)*

| id | code | name | capacity | building | room_type | university_id |
|----|------|------|----------|----------|-----------|---------------|
| r-001 | LAB-2 | Lab-2 | 40 | Block C | lab | u-001 |
| r-002 | HALL-A | Hall-A | 120 | Block A | lecture | u-001 |

**Table: `time_slots`**

| id | day | start_time | end_time | slot_index | slot_type | label |
|----|-----|------------|----------|------------|-----------|-------|
| ts-01 | Monday | 08:00 | 10:00 | 1 | class | Period 1 |
| ts-03 | Wednesday | 08:00 | 10:00 | 1 | class | Period 1 |
| ts-05 | Tuesday | 10:00 | 12:00 | 2 | class | Period 2 |

**3NF achieved:** Each non-key attribute depends only on the primary key of its table.

---

## 6. Many-to-Many Relationships (Beyond 3NF)

Some relationships cannot be expressed in a single table without repeating groups. Shedulex uses **junction tables**:

### Courses ↔ Student Groups

A course may be taken by multiple groups; a group takes multiple courses.

**Table: `course_student_groups`**

| course_id | student_group_id |
|-----------|------------------|
| c-001 | sg-001 |
| c-001 | sg-002 |
| c-002 | sg-003 |

### Lecturers ↔ Programs

A lecturer may teach across multiple programmes.

**Table: `lecturer_programs`**

| lecturer_id | program_id |
|-------------|------------|
| l-001 | p-001 |
| l-002 | p-001 |

### Per-group lecturer override

**Table: `course_group_lecturers`**

| course_id | student_group_id | lecturer_id |
|-----------|------------------|-------------|
| c-001 | sg-002 | l-002 |

When BIT201 is taught by Dr. Amina for Group A but Dr. Peter for Group B, each pair is stored once without duplicating course metadata.

---

## 7. Final Normalized Schema — Shedulex `timetable_db`

The implemented schema is in **3NF** (and BCNF for most entities). Core tables:

```
universities
    └── departments
            ├── programs
            │       └── student_groups
            ├── courses ──┬── course_student_groups ── student_groups
            │             └── course_group_lecturers
            └── lecturers ── lecturer_programs ── programs

timetable_templates
    └── template_time_blocks

time_slots (may link to template)

timetables
    ├── timetable_entries → courses, lecturers, rooms, time_slots, student_groups
    └── timetable_snapshots

constraints (scoped to department / university / entity)
academic_years
```

### Table: `timetables` (header)

| id | name | semester | academic_year | department_id | program_id | status | fitness_score |
|----|------|----------|---------------|---------------|------------|--------|---------------|
| tt-001 | CIT Semester 1 2025/26 | 1 | 2025-2026 | d-001 | p-001 | active | 0.96 |

### Table: `timetable_entries` (detail — 3NF)

| id | timetable_id | course_id | lecturer_id | room_id | time_slot_id | student_group_id |
|----|--------------|-----------|-------------|---------|--------------|------------------|
| e-001 | tt-001 | c-001 | l-001 | r-001 | ts-01 | sg-001 |
| e-002 | tt-001 | c-001 | l-001 | r-001 | ts-03 | sg-002 |
| e-003 | tt-001 | c-002 | l-002 | r-002 | ts-05 | sg-003 |

No course name, lecturer email, or room capacity is duplicated here — only foreign keys.

---

## 8. Auth Service Normalization (`auth_db`)

The auth microservice is also normalized to 3NF:

### Violation (unnormalized users)

| user_id | email | password_hash | role_name | role_permissions |
|---------|-------|---------------|-----------|------------------|
| 1 | admin@kiut.ac.tz | $2b$... | admin | ["users:read","users:write",...] |

`role_permissions` depends on `role_name`, not `user_id` → transitive dependency.

### Correction (3NF)

**Table: `roles`**

| id | name | permissions |
|----|------|-------------|
| r-01 | admin | ["users:read", "users:write", "audit:read"] |
| r-02 | timetable_officer | ["timetable:generate", "resources:write"] |
| r-03 | hod | ["timetable:read", "analytics:read"] |
| r-04 | lecturer | ["timetable:read", "notifications:read"] |

**Table: `users`**

| id | email | password_hash | first_name | last_name | role_id | university_id |
|----|-------|---------------|------------|-----------|---------|---------------|
| u-01 | admin@kiut.ac.tz | $2b$... | Admin | User | r-01 | u-001 |
| u-02 | officer@kiut.ac.tz | $2b$... | Officer | User | r-02 | u-001 |

---

## 9. Normalization Summary

| Normal Form | Rule Applied | Shedulex Action |
|-------------|--------------|-----------------|
| **Unnormalized** | Single spreadsheet with all data repeated | Starting point (manual KIUT records) |
| **1NF** | Atomic values; no repeating groups | Split multi-group cells; one session per row |
| **2NF** | No partial dependencies | Extract `courses`, `lecturers`, `rooms`, `time_slots` |
| **3NF** | No transitive dependencies | Extract `universities`, `departments`, `programs`, `roles` |
| **Junction tables** | Resolve M:N relationships | `course_student_groups`, `lecturer_programs`, `course_group_lecturers` |

### Benefits realized in Shedulex

1. **Data integrity** — Updating a lecturer's email in `lecturers` updates it everywhere via `lecturer_id`
2. **GA accuracy** — Fitness evaluation reads consistent room capacity and availability from single sources
3. **Scalability** — New departments, programmes, and academic years added without restructuring timetable rows
4. **Microservice autonomy** — `auth_db` and `timetable_db` each maintain 3NF independently (database-per-service pattern)

---

## 10. Figure Caption (for report)

> **Table 3.x Normalization Progression** — Transformation of KIUT manual timetable data from an unnormalized relation through 1NF, 2NF, and 3NF to the final Shedulex PostgreSQL schema implemented in `timetable_db` and `auth_db`.

---

*Aligned with Shedulex models: `Backend/timetable-engine/app/models/domain.py`, `Backend/auth-service/app/models/user.py`, and `scripts/init_databases.sql`.*
