# Shedulex Scheduling Guide
## Cross-Department Lecturers, Shared Rooms & Constraints Reference

---

## The fundamental rule to understand first

The GA sees **only what is passed into the current generation run**. It has no memory of previously generated timetables. This one fact explains everything in Parts 1 and 2 below.

---

## Part 1 — Cross-Department Lecturer Assignment

### Short answer: Yes, the lecturer's constraints are respected — but only within the current run.

When you generate a timetable for **Department A**, the engine:

1. Loads only **courses** belonging to Department A (and the selected semester).
2. Loads **all active lecturers** in the system — no department filter is applied.

```python
# timetable_service.py — exact queries used
courses   = Course.query.filter_by(department_id=department_id, semester=semester, is_active=True).all()
lecturers = Lecturer.query.filter_by(is_active=True).all()   # ← NO department filter
```

So if **CS101 (Department A)** is assigned to **Dr. Ochieng (Department B)**:

- Dr. Ochieng is loaded into the GA.
- His `availability`, `max_hours_per_day`, `max_consecutive_hours`, `preferred_days`, and `unavailable_slots` are all respected.
- Hard constraint **H1** (no double-booking) prevents him from teaching two Dept A courses at the same time.

### ⚠ The cross-timetable gap for lecturers

| Scenario | Result |
|----------|--------|
| Dr. Ochieng teaches only Dept A courses in this run | ✅ All constraints enforced perfectly |
| Dr. Ochieng has Dept B courses in a **previously generated** timetable | ⚠ GA cannot see those entries — cross-timetable double-booking is possible |

**Workarounds for shared lecturers (in order of preference):**
1. Add the lecturer's already-scheduled slots to their `unavailable_slots` profile field before generating the next department's timetable.
2. Set `availability` to only the free days/slots remaining after the first department is scheduled.
3. Use the `preferred_times` DB constraint to steer them away from already-occupied times.

---

## Part 2 — Shared Rooms Across Departments

### Short answer: No — the GA does NOT see bookings from other timetables.

Room loading uses the same pattern as lecturers:

```python
# timetable_service.py — exact query used
rooms = Room.query.filter_by(is_available=True).all()   # ← NO department filter
```

All available rooms are loaded. The GA can assign **any room to any course** in the current run, regardless of whether another department's timetable has already used that room at the same time.

### Why H2 does not protect you across timetables

Hard constraint **H2** prevents room double-booking *within the current generation run* only:

```python
# fitness.py — H2 check
rkey = f"{gene.room_id}:{gene.time_slot_id}"
room_slot_map[rkey].append(gene.course_id)      # only genes from THIS run
if len(room_slot_map[rkey]) > 1:
    penalty += HARD_PENALTY                      # never sees other timetables
```

The `room_slot_map` is built fresh from the current chromosome's genes. It never queries existing `TimetableEntry` records. So:

| Scenario | Result |
|----------|--------|
| Two Dept A courses competing for Room LH1 at the same time | ✅ H2 catches it — hard penalty applied |
| Dept B already uses Room LH1 at Monday 9 AM in its own timetable, and Dept A generates now | ⚠ GA does not know — may also place a Dept A course in LH1 at Monday 9 AM |

### Workarounds for shared rooms (pick the one that fits)

**Option A — Mark the room unavailable during generation (blunt but safe)**  
Before generating Dept A's timetable, set `is_available = false` on rooms that are fully committed to Dept B. Re-enable them after. This prevents the GA from using those rooms at all. Best when a room is exclusively owned by one department.

**Option B — Use separate time slot templates (best for structured sharing)**  
If Dept A uses the morning template (08:00–12:00) and Dept B uses the afternoon template (13:00–17:00), their generated timetables will never overlap, and shared rooms are conflict-free by design. This is the most reliable approach for shared infrastructure.

**Option C — Use the `unavailable_slots` field on rooms (not yet implemented)**  
The room model doesn't currently expose slot-level blocking. This is a known limitation.

**Option D — Post-generation conflict check + manual drag-and-drop**  
Generate both timetables, then use the **Check Conflicts** button in each timetable's detail view. The conflict endpoint (`GET /timetable/{id}/conflicts`) compares all `TimetableEntry` records across timetables for the same university. If it finds Room LH1 double-booked at the same slot across two timetables, it will flag it. Resolve manually using drag-and-drop in the timetable editor.

**Option E — Generate as one combined run (ideal, not always possible)**  
If both departments share enough courses or a programme spans both, generate a single timetable covering all courses. H2 then guarantees room uniqueness across everything in one shot.

### Recommended room-sharing workflow

```
1. Generate timetable for the largest / most constrained department first.
2. Note which rooms are used at which slots (from the timetable grid).
3. Before generating the next department, either:
   a. Switch shared rooms to is_available = false temporarily, OR
   b. Use a time-slot template that covers non-overlapping hours.
4. Generate the second department.
5. Re-enable rooms if you disabled them.
6. Run "Check Conflicts" on both timetables to catch any remaining overlap.
7. Use drag-and-drop to resolve flagged conflicts manually.
```

---

## Part 2 — How Constraints Work

The GA fitness function assigns a **penalty score** to each candidate timetable. The final fitness is:

```
fitness = 1.0 − (total_penalty / worst_case_penalty)
```

A fitness of **1.0 = perfect**, **0.0 = completely infeasible**.  
Constraints either add to that penalty or have no effect.

There are **three layers** of constraints:

---

### Layer 1 — Built-in Hard Constraints (always on, cannot be disabled)

These are coded directly in `fitness.py`. They use `HARD_PENALTY = 1000.0` per violation, which makes them nearly impossible for the GA to ignore. A timetable with any of these violations will have very low fitness and will be discarded by selection.

| Code | Name | What it checks |
|------|------|----------------|
| **H1** | Lecturer double-booking | A lecturer cannot teach two courses at the same time slot |
| **H2** | Room double-booking | A room cannot host two courses at the same time slot |
| **H3** | Room capacity | `room.capacity` must be ≥ `course.student_count` |
| **H4** | Lab requirement | If `course.requires_lab = true`, the room must have `room_type = "lab"` |
| **H5** | Lecturer availability | If a lecturer has an `availability` dict set, the slot must appear in `availability[day]` |
| **H6** | Break/lunch slots | Courses cannot be placed in `slot_type = "break"` or `"lunch"` slots |
| **H7** | Student group double-booking | A student group cannot have two courses at the same time slot |
| **H8** | Daily hour limit | A lecturer's sessions in one day cannot exceed `lecturer.max_hours_per_day` |
| **H9** | Explicitly unavailable slots | Slots listed in `lecturer.unavailable_slots` are blocked for that lecturer |

**These cannot be turned off.** They are unconditional in the fitness function.

---

### Layer 2 — Built-in Soft Constraints (always on, weighted penalties)

These use lower penalty values (`SOFT_WEIGHTS`) so the GA tries to satisfy them but can sacrifice them when necessary.

| Code | Name | Penalty weight | What it checks |
|------|------|---------------|----------------|
| **S1** | Consecutive lectures | 60.0 × overrun | Penalises runs longer than `lecturer.max_consecutive_hours` back-to-back |
| **S2** | Day distribution | 30.0 × variance | Penalises bunching all courses on the same day for a department |
| **S4** | Student-group gaps | 45.0 × gap count | Penalises gaps/holes in a student group's daily schedule |
| **S5** | Room utilisation balance | 15.0 × variance | Tries to spread usage evenly across rooms |
| **S6** | Lecturer preferred days | 20.0 per violation | If `lecturer.preferred_days` is set, penalises scheduling on other days |
| **S-weekly** | Weekly hour limit | 80.0 × overrun | Penalises exceeding `lecturer.max_hours_per_week` (soft, not hard) |

---

### Layer 3 — Database Constraints (configurable in the UI)

These are created through **Resources → Constraints** and stored in the `constraints` table. The GA loads all **active** constraints at generation time and routes them through a `rule_type` dispatcher in `fitness.py`.

#### Constraint fields explained

| Field | Type | Description |
|-------|------|-------------|
| `name` | text | Human-readable description (e.g. "Dr. Ali no mornings") |
| `constraint_type` | `hard` \| `soft` | Intended severity (see note below) |
| `category` | `lecturer` \| `room` \| `student` \| `academic` \| `system` | Grouping/display only |
| `rule_type` | string | The **routing key** — tells fitness.py which logic to run |
| `entity_type` | `lecturer` \| `room` \| `student_group` \| `program` \| `department` | What the constraint targets |
| `entity_id` | UUID | The specific entity ID (the lecturer, room, etc.) |
| `department_id` | UUID | Scope to one department (null = university-wide) |
| `weight` | float | Penalty multiplier. Default `1.0`. `2.0` = twice as strong |
| `config` | JSON | Rule-specific parameters (see each rule below) |
| `is_active` | bool | Toggle without deleting |

> **Note on `constraint_type`:** The field records your intent (`hard`/`soft`) but the actual enforcement hardness depends on the `rule_type` handler. Some handlers always use a hard-penalty regardless of this field.

---

#### Implemented `rule_type` values (actively evaluated by the GA)

Only these four are fully wired into `fitness.py`. Others are defined in the schema but not yet evaluated.

---

##### `max_consecutive` — Limit back-to-back teaching hours
**entity_type:** `lecturer`  
**category:** `lecturer`  
**config:** `{ "limit": <integer> }`

Penalises a lecturer for having more than `limit` consecutive time slots in one day.

```json
{
  "name": "Dr. Kamau max 2 consecutive",
  "constraint_type": "soft",
  "category": "lecturer",
  "rule_type": "max_consecutive",
  "entity_type": "lecturer",
  "entity_id": "<dr-kamau-uuid>",
  "weight": 1.5,
  "config": { "limit": 2 }
}
```

**Effect:** Each consecutive run beyond 2 adds `weight × 50 × (run − limit)` to the penalty.  
**Tip:** This overrides the built-in S1 soft constraint for this specific lecturer with your custom limit.

---

##### `max_daily_hours` — Hard cap on a lecturer's daily sessions
**entity_type:** `lecturer`  
**category:** `lecturer`  
**config:** `{ "limit": <integer> }`

Hard-penalises a lecturer for teaching more than `limit` hours in any single day.

```json
{
  "name": "Dr. Otieno 4-hour day cap",
  "constraint_type": "hard",
  "category": "lecturer",
  "rule_type": "max_daily_hours",
  "entity_type": "lecturer",
  "entity_id": "<dr-otieno-uuid>",
  "weight": 1.0,
  "config": { "limit": 4 }
}
```

**Effect:** Uses `HARD_PENALTY × (hours − limit)` per excess hour — effectively treated as a hard constraint. A lecturer with `max_hours_per_day = 6` on their profile (H8) and this constraint set to `limit: 4` will be hard-penalised at 4 hours per day, not 6.

**Tip:** Set a lower limit than the lecturer's profile default to create a tighter per-lecturer rule.

---

##### `preferred_times` — Steer a lecturer to specific time slots
**entity_type:** `lecturer`  
**category:** `lecturer`  
**config:** `{ "slot_ids": ["<slot-uuid-1>", "<slot-uuid-2>", ...] }`

Adds a penalty for every course assigned to this lecturer that falls outside the listed slot IDs.

```json
{
  "name": "Prof. Mwangi — mornings only",
  "constraint_type": "soft",
  "category": "lecturer",
  "rule_type": "preferred_times",
  "entity_type": "lecturer",
  "entity_id": "<prof-mwangi-uuid>",
  "weight": 2.0,
  "config": {
    "slot_ids": [
      "<monday-08:00-uuid>",
      "<monday-09:00-uuid>",
      "<tuesday-08:00-uuid>",
      "<tuesday-09:00-uuid>"
    ]
  }
}
```

**Effect:** `weight × 20` penalty per course placed outside the preferred slots.  
**Tip:** Get slot UUIDs from **Resources → Time Slots**. Higher `weight` = stronger preference.  
**vs. Lecturer availability (H5):** `availability` on the lecturer profile is a **hard** constraint (HARD_PENALTY). `preferred_times` constraint is **soft** — the GA will try to comply but may violate it if no feasible alternative exists.

---

##### `exam_gap` — Keep classes away from exam periods
**entity_type:** any (applies globally to all genes)  
**category:** `academic`  
**config:** `{ "exam_slot_ids": ["<uuid>", ...], "min_gap_slots": <integer> }`

Penalises any class that is within `min_gap_slots` positions of an exam slot on the same day.

```json
{
  "name": "No classes 2 slots before exams",
  "constraint_type": "soft",
  "category": "academic",
  "rule_type": "exam_gap",
  "weight": 1.5,
  "config": {
    "exam_slot_ids": ["<friday-15:00-uuid>", "<friday-16:00-uuid>"],
    "min_gap_slots": 2
  }
}
```

**Effect:** `weight × 35` per class that falls within 2 slot positions of any exam slot on the same day.  
**Tip:** First mark your exam time slots as `slot_type = "exam"` in Time Slots, then reference their UUIDs here.

---

### Rule types — GA evaluation status

| rule_type | Status |
|-----------|--------|
| `max_daily_hours` | ✅ Lecturer & student group |
| `max_weekly_hours` | ✅ Lecturer & student group |
| `max_consecutive` | ✅ Lecturer & student group |
| `preferred_times` | ✅ Lecturer (soft) |
| `unavailable` | ✅ Lecturer & course |
| `course_preferred_times` | ✅ Course (soft) |
| `course_unavailable` | ✅ Course |
| `equipment_required` | ✅ Room |
| **`shared_room`** | ✅ **Room — department allow-list + ranked priority** |
| `fixed_session` | ✅ Course |
| `mandatory_order` | ✅ Academic |
| `semester_only` | ✅ Course |
| `exam_gap` | ✅ Academic (soft) |
| `capacity_check` | ⚙️ Automatic (built-in H3 — no DB rule needed) |
| `no_overlap` | ⚙️ Automatic (built-in H7 — no DB rule needed) |
| `timezone_aware` | ❌ Not implemented |
| `holiday_aware` | ❌ Not implemented |

#### `shared_room` — Department room access & priority

Attach to a **specific room** (`entity_type: room`). Config:

```json
{
  "allowed_department_ids": ["<cs-dept-uuid>", "<it-dept-uuid>"],
  "priority_order": ["<cs-dept-uuid>", "<it-dept-uuid>"],
  "department_weights": { "<cs-dept-uuid>": 1.0, "<it-dept-uuid>": 0.65 }
}
```

- **One allowed department** + **Hard** → exclusive room for that department
- **Multiple allowed** → shared room; departments not listed are blocked (when Hard)
- **`priority_order`** → index 0 is highest priority; lower-priority depts get soft penalties
- **`department_weights`** → optional fine-grained preference (0.1–1.0)

Configure under **Resources → Constraints → Room → Department room access & priority**.

---

## Part 3 — Lecturer Profile Fields vs. Constraints

The `Lecturer` model has several scheduling fields. These interact with constraints:

| Lecturer field | Built-in constraint it feeds | Can DB constraint override? |
|---------------|-----------------------------|-----------------------------|
| `availability` | **H5** (hard) — must teach only in these slots | Yes — `preferred_times` (soft) is different; add unavailable_slots too |
| `unavailable_slots` | **H9** (hard) — blocked slots | No override; this is always hard |
| `max_hours_per_day` | **H8** (hard), S-weekly (soft) | Yes — `max_daily_hours` constraint adds per-constraint limit |
| `max_hours_per_week` | S-weekly (soft, weight 80) | No DB rule yet |
| `max_consecutive_hours` | **S1** (soft, weight 60) | Yes — `max_consecutive` DB constraint overrides per-lecturer |
| `preferred_days` | **S6** (soft, weight 20) | No DB rule yet; set field instead |

---

## Part 4 — Effective Setup Workflow

### Setting up a new lecturer

1. **Resources → Lecturers → Create/Edit**
2. Set `max_hours_per_week` (e.g., 18 for part-time, 20 for full-time)
3. Set `max_hours_per_day` (typically 4–6)
4. Set `max_consecutive_hours` (typically 2–3)
5. Set `preferred_days` if the lecturer has preferred teaching days (e.g., `["Monday", "Wednesday", "Friday"]`)
6. Set `unavailable_slots` to block specific slot IDs the lecturer absolutely cannot teach (hard block — treated like H9)
7. Set `availability` only if the lecturer can teach in a **limited set** of slots (e.g., visiting lecturer available only Mon 9–12). Leave empty to allow all non-break slots.

### Setting up database constraints

**Common scenarios:**

#### "Dr. X should never teach more than 3 hours in a day"
→ Use `max_daily_hours` with `config: { "limit": 3 }` + `entity_id = Dr. X`

#### "Dr. Y prefers to teach Tuesday and Thursday mornings"
→ Use `preferred_times` with `slot_ids = [tuesday 08:00 uuid, tuesday 09:00 uuid, thursday 08:00 uuid, thursday 09:00 uuid]`  
→ Set `weight: 1.5` to make it a stronger preference

#### "No classes should be scheduled in the last 2 slots before the Friday afternoon exam"
→ Use `exam_gap` with `exam_slot_ids = [friday 15:00, friday 16:00]` and `min_gap_slots: 2`

#### "Dr. Z must never teach more than 2 back-to-back hours"
→ Use `max_consecutive` with `config: { "limit": 2 }` + `entity_id = Dr. Z`  
→ Set `weight: 2.0` for stronger enforcement

---

## Part 5 — Fitness Score Interpretation

| Score | Meaning | Action |
|-------|---------|--------|
| 0.95–1.00 | Excellent — all hard constraints satisfied, most soft met | Ready to publish |
| 0.80–0.94 | Good — no hard violations but some soft preferences unmet | Review violation report |
| 0.60–0.79 | Moderate — possible hard violations | Check conflicts report, adjust constraints or room/slot count |
| < 0.60 | Poor — many hard violations | Add more rooms, reduce course load, increase time slots, or loosen constraints |

**Violation report** (in timetable detail view → "Violation Report"):
- 🔴 High severity = hard constraint violated (H1–H9)
- 🟡 Medium severity = soft constraint exceeded significantly
- ℹ️ Info = minor soft preference not met

If the fitness score is below 0.80, the most common causes are:
1. Too few rooms for the number of courses (H2/H3)
2. Lab courses but no lab rooms (H4)
3. Lecturer availability too restrictive for the course load (H5)
4. Too many courses for the available time slots
