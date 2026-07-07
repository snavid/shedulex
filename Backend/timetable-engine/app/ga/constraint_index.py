"""
Pre-index active DB constraints for fast lookup during GA init, mutation, and fitness.

Room shared_room rules:
  - allowed_department_ids: hard allow-list when constraint_type is hard
  - priority_order: graduated soft penalty by rank (0 = highest priority)
  - department_weights: optional explicit weights (overrides rank when set)
"""
from __future__ import annotations


def _normalize_allowed_ids(cfg: dict) -> list[str]:
    """Extract allowed department IDs from config (new or legacy format)."""
    allowed = cfg.get("allowed_department_ids") or cfg.get("departments") or []
    return [str(x) for x in allowed if x]


def filter_constraints_for_generation(
    constraints: list[dict],
    *,
    university_id: str | None = None,
    generating_department_id: str | None = None,
) -> list[dict]:
    """Return constraints applicable to this timetable generation run."""
    result: list[dict] = []
    for c in constraints:
        if not c.get("is_active", True):
            continue
        c_uni = c.get("university_id")
        if university_id and c_uni and c_uni != university_id:
            continue
        c_dept = c.get("department_id")
        if c_dept and generating_department_id and c_dept != generating_department_id:
            continue
        result.append(c)
    return result


class ConstraintIndex:
    """Indexed view of DB constraints for GA operators."""

    PRIORITY_SOFT_FACTOR = 25.0

    def __init__(self, constraints: list[dict] | None = None):
        constraints = constraints or []
        self._shared_room: dict[str, dict] = {}
        self._lec_blocked: dict[str, set[str]] = {}
        self._course_blocked: dict[str, set[str]] = {}
        self._fixed_sessions: dict[str, str] = {}

        for c in constraints:
            if not c.get("is_active", True):
                continue
            rule = c.get("rule_type", "")
            cfg = c.get("config") or {}
            eid = c.get("entity_id")
            etype = c.get("entity_type", "")

            if rule == "shared_room" and etype == "room" and eid:
                allowed = _normalize_allowed_ids(cfg)
                self._shared_room[eid] = {
                    "constraint": c,
                    "allowed": set(allowed),
                    "priority_order": [str(x) for x in (cfg.get("priority_order") or []) if x],
                    "department_weights": {
                        str(k): float(v)
                        for k, v in (cfg.get("department_weights") or {}).items()
                    },
                }

            elif rule == "unavailable" and etype == "lecturer" and eid:
                blocked = set(cfg.get("slot_ids") or [])
                self._lec_blocked.setdefault(eid, set()).update(blocked)

            elif rule in ("course_unavailable", "unavailable") and etype == "course" and eid:
                blocked = set(cfg.get("slot_ids") or [])
                self._course_blocked.setdefault(eid, set()).update(blocked)

            elif rule == "fixed_session":
                target_course = cfg.get("course_id") or (eid if etype == "course" else None)
                target_slot = cfg.get("slot_id")
                if target_course and target_slot:
                    self._fixed_sessions[target_course] = target_slot

    def has_room_rules(self) -> bool:
        return bool(self._shared_room)

    def room_allowed(self, room_id: str, department_id: str) -> bool:
        """True if department may use this room (no rule = allowed for all)."""
        rule = self._shared_room.get(room_id)
        if not rule or not rule["allowed"]:
            return True
        if not department_id:
            return True
        return department_id in rule["allowed"]

    def room_priority_penalty(self, room_id: str, department_id: str) -> float:
        """Soft penalty for using a shared room below top priority (0 = no penalty)."""
        rule = self._shared_room.get(room_id)
        if not rule or not department_id:
            return 0.0
        if rule["allowed"] and department_id not in rule["allowed"]:
            return 0.0  # hard violation handled separately

        c = rule["constraint"]
        weight = float(c.get("weight", 1.0))
        weights = rule.get("department_weights") or {}
        if weights and department_id in weights:
            max_w = max(weights.values()) if weights else 1.0
            if max_w <= 0:
                return 0.0
            dept_w = weights.get(department_id, 0.0)
            return weight * self.PRIORITY_SOFT_FACTOR * (1.0 - dept_w / max_w)

        order = rule.get("priority_order") or []
        if order and department_id in order:
            rank = order.index(department_id)
            return weight * self.PRIORITY_SOFT_FACTOR * rank

        return 0.0

    def rooms_for_department(self, all_rooms: list[dict], department_id: str) -> list[dict]:
        """Filter rooms to those allowed for the generating department."""
        if not department_id or not self._shared_room:
            return list(all_rooms)
        return [r for r in all_rooms if self.room_allowed(r["id"], department_id)]

    def eligible_room_ids_for_gene(
        self,
        all_rooms: list[dict],
        department_id: str,
        *,
        requires_lab: bool = False,
        required_room_type: str | None = None,
        fixed_room_id: str | None = None,
        building_id: str | None = None,
        slot_id: str | None = None,
        room_busy_slots: dict[str, set[str]] | None = None,
    ) -> list[str]:
        """Return room IDs eligible for mutation/init for one gene.

        Priority (highest first):
          1. fixed_room_id set -> always exactly that room (bypasses dept/building/
             type/slot filtering entirely — the generator must obey this).
          2. required_room_type == 'lab' (mandatory computer lab) -> exempt from
             building_id scoping, since not every building has a computer lab.
          3. otherwise -> hard-scoped to building_id if given.
        """
        if fixed_room_id:
            return [fixed_room_id]

        room_busy_slots = room_busy_slots or {}
        pool = self.rooms_for_department(all_rooms, department_id)

        effective_type = required_room_type or ("lab" if requires_lab else None)
        is_mandatory_lab = effective_type == "lab"

        if building_id and not is_mandatory_lab:
            scoped = [r for r in pool if r.get("building_id") == building_id]
            if scoped:
                pool = scoped

        if effective_type:
            typed = [r for r in pool if r.get("room_type") == effective_type]
            if typed:
                pool = typed
        else:
            non_lab = [r for r in pool if r.get("room_type") != "lab"]
            if non_lab:
                pool = non_lab

        if slot_id:
            free = [
                r for r in pool
                if slot_id not in room_busy_slots.get(r["id"], set())
            ]
            if free:
                pool = free
        return [r["id"] for r in pool] if pool else [r["id"] for r in all_rooms]

    def blocked_slots_for_lecturer(self, lecturer_id: str) -> set[str]:
        return set(self._lec_blocked.get(lecturer_id, set()))

    def blocked_slots_for_course(self, course_id: str) -> set[str]:
        return set(self._course_blocked.get(course_id, set()))

    def fixed_session(self, course_id: str) -> str | None:
        return self._fixed_sessions.get(course_id)

    def shared_room_constraints(self) -> dict[str, dict]:
        return self._shared_room

    @classmethod
    def from_constraints(
        cls,
        constraints: list[dict],
        *,
        university_id: str | None = None,
        generating_department_id: str | None = None,
    ) -> "ConstraintIndex":
        filtered = filter_constraints_for_generation(
            constraints,
            university_id=university_id,
            generating_department_id=generating_department_id,
        )
        return cls(filtered)


def shared_room_allow_violation(
    constraint: dict,
    room_id: str,
    department_id: str,
) -> bool:
    """True if department is not on the allow-list for this room constraint."""
    cfg = constraint.get("config") or {}
    allowed = set(_normalize_allowed_ids(cfg))
    if not allowed:
        return False
    return bool(department_id and department_id not in allowed)


def shared_room_priority_penalty(constraint: dict, room_id: str, department_id: str) -> float:
    """Compute soft priority penalty for evaluate() — mirrors ConstraintIndex logic."""
    idx = ConstraintIndex([constraint])
    return idx.room_priority_penalty(room_id, department_id)
