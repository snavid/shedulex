<script setup>
import { onMounted, ref, computed, watch, nextTick } from "vue"
import { resourcesApi, getErrorMessage } from "@/api/client"
import { useToast } from "vue-toastification"

const toast = useToast()
const loading  = ref(true)
const saving   = ref(false)
const constraints = ref([])
const lecturers   = ref([])
const rooms       = ref([])
const timeSlots   = ref([])
const showForm    = ref(false)
const editTarget  = ref(null)
const deleteTarget = ref(null)
const typeFilter     = ref("")
const categoryFilter = ref("")

// ── Rule-type catalogue ────────────────────────────────────────────────────
const RULE_CATALOGUE = {
  lecturer: [
    { value: "max_daily_hours",   label: "Max daily teaching hours" },
    { value: "max_weekly_hours",  label: "Max weekly teaching hours" },
    { value: "max_consecutive",   label: "Max consecutive periods" },
    { value: "preferred_times",   label: "Preferred time slots" },
    { value: "unavailable",       label: "Unavailable periods" },
  ],
  room: [
    { value: "capacity_check",    label: "Room capacity enforcement" },
    { value: "equipment_required",label: "Required equipment" },
    { value: "shared_room",       label: "Shared-room booking rules" },
  ],
  student: [
    { value: "no_overlap",        label: "No student group overlap" },
    { value: "max_consecutive",   label: "Max consecutive classes" },
    { value: "max_daily_hours",   label: "Max daily classes" },
    { value: "max_weekly_hours",  label: "Max weekly classes" },
    { value: "exam_gap",          label: "Exam preparation gap" },
  ],
  academic: [
    { value: "semester_only",           label: "Semester-only module" },
    { value: "fixed_session",           label: "Fixed session time" },
    { value: "mandatory_order",         label: "Mandatory ordering" },
    { value: "course_preferred_times",  label: "Course preferred time slots" },
    { value: "course_unavailable",      label: "Course unavailable periods" },
  ],
  system: [
    { value: "timezone_aware",    label: "Timezone-aware scheduling" },
    { value: "holiday_aware",     label: "Skip public holidays" },
  ],
}

// Default configData shape for each rule_type
const RULE_DEFAULTS = {
  max_daily_hours:   { limit: 6 },
  max_weekly_hours:  { limit: 20 },
  max_consecutive:   { limit: 3 },
  preferred_times:   { slot_ids: [] },
  unavailable:       { slot_ids: [] },
  exam_gap:          { min_gap_slots: 2, exam_slot_ids: [] },
  fixed_session:     { slot_id: "" },
  equipment_required:{ equipment: [] },
  semester_only:     { semester: 1 },
  mandatory_order:        { before_course_id: "", after_course_id: "" },
  course_preferred_times: { slot_ids: [] },
  course_unavailable:     { slot_ids: [] },
  shared_room:            { departments: [] },
  timezone_aware:    { timezone: "Africa/Nairobi" },
  capacity_check:    {},
  no_overlap:        {},
  holiday_aware:     {},
}

const NO_CONFIG_RULES  = new Set(["capacity_check", "no_overlap", "holiday_aware"])
const LIMIT_RULES      = new Set(["max_daily_hours", "max_weekly_hours", "max_consecutive"])
const SLOT_ARRAY_RULES = new Set(["preferred_times", "unavailable", "course_preferred_times", "course_unavailable"])
const EQUIPMENT_OPTIONS = ["projector", "whiteboard", "lab_equipment", "smart_board", "av_system"]
const TIMEZONES = ["UTC", "Africa/Nairobi", "Africa/Lagos", "Africa/Cairo", "Africa/Johannesburg", "Europe/London", "Asia/Dubai"]
const DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

const CATEGORY_LABELS = {
  lecturer: "Lecturer", room: "Room", student: "Student",
  academic: "Academic", system: "System",
}

// ── Form state ─────────────────────────────────────────────────────────────
const blank = () => ({
  name: "", constraint_type: "soft", category: "lecturer",
  rule_type: "", entity_type: "", entity_id: "",
  weight: 1.0,
  configData: {},  // replaces the old `config` string
})
const form = ref(blank())

// ── Slot picker state ──────────────────────────────────────────────────────
const showSlotPicker  = ref(false)
const pickerTarget    = ref("slot_ids") // key inside configData to write
const pickerSingle    = ref(false)      // true = radio (fixed_session), false = checkboxes
const pickerSelection = ref(new Set())

// ── Raw JSON fallback state ────────────────────────────────────────────────
const showRawJson  = ref(false)
const rawJsonDraft = ref("{}")
const rawJsonError = ref("")

// ── Prevent rule_type watcher from clobbering config during openEdit ───────
let _openingEdit = false

// ── Computed ───────────────────────────────────────────────────────────────
const rulesForCategory = computed(() => RULE_CATALOGUE[form.value.category] || [])

const slotsByDay = computed(() => {
  const map = {}
  for (const s of timeSlots.value) {
    if (s.is_break || s.slot_type === "break" || s.slot_type === "lunch") continue
    ;(map[s.day] ??= []).push(s)
  }
  for (const d of Object.keys(map)) map[d].sort((a, b) => (a.slot_index ?? 0) - (b.slot_index ?? 0))
  return DAY_ORDER.filter(d => map[d]).map(d => ({ day: d, slots: map[d] }))
})

const slotLookup = computed(() => Object.fromEntries(timeSlots.value.map(s => [s.id, s])))

function slotLabel(id) {
  const s = slotLookup.value[id]
  return s ? `${s.day} ${s.start_time}–${s.end_time}` : id.slice(0, 8) + "…"
}

// Writable computed for shared_room departments (comma-separated text input)
const sharedRoomDepts = computed({
  get: () => (form.value.configData.departments || []).join(", "),
  set: (v) => {
    form.value.configData = {
      ...form.value.configData,
      departments: v.split(",").map(s => s.trim()).filter(Boolean),
    }
  },
})

// ── Watchers ───────────────────────────────────────────────────────────────
watch(() => form.value.category, () => {
  form.value.rule_type  = ""
  form.value.entity_type = ""
  form.value.entity_id   = ""
  form.value.configData  = {}
  showRawJson.value = false
  rawJsonDraft.value = "{}"
  rawJsonError.value = ""
})

watch(() => form.value.rule_type, (v) => {
  if (_openingEdit) return
  // Reset config to sensible defaults for this rule
  form.value.configData = v && RULE_DEFAULTS[v]
    ? JSON.parse(JSON.stringify(RULE_DEFAULTS[v]))
    : {}
  // Auto-set entity_type to match category
  if      (form.value.category === "lecturer") form.value.entity_type = "lecturer"
  else if (form.value.category === "room")     form.value.entity_type = "room"
  else if (form.value.category === "student")  form.value.entity_type = "student_group"
  else                                          form.value.entity_type = ""
  showRawJson.value  = false
  rawJsonError.value = ""
  rawJsonDraft.value = JSON.stringify(form.value.configData, null, 2)
})

// Keep raw-JSON textarea in sync when it's open and the visual builder changes configData
watch(() => form.value.configData, (v) => {
  if (showRawJson.value) {
    rawJsonDraft.value = JSON.stringify(v, null, 2)
    rawJsonError.value = ""
  }
}, { deep: true })

watch(showRawJson, (v) => {
  if (v) {
    rawJsonDraft.value = JSON.stringify(form.value.configData, null, 2)
    rawJsonError.value = ""
  }
})

// ── Raw JSON textarea handler ──────────────────────────────────────────────
function onRawJsonInput(e) {
  rawJsonDraft.value = e.target.value
  try {
    // Temporarily suppress the configData watcher so it doesn't re-format the textarea mid-type
    form.value.configData = JSON.parse(e.target.value)
    rawJsonError.value = ""
  } catch {
    rawJsonError.value = "Invalid JSON — fix before saving."
  }
}

// ── Slot picker helpers ────────────────────────────────────────────────────
function openSlotPicker(target = "slot_ids", single = false) {
  pickerTarget.value = target
  pickerSingle.value = single
  const existing = form.value.configData[target]
  pickerSelection.value = single
    ? new Set(existing ? [existing] : [])
    : new Set(Array.isArray(existing) ? existing : [])
  showSlotPicker.value = true
}

function togglePickerSlot(id) {
  const s = new Set(pickerSelection.value)
  if (pickerSingle.value) {
    pickerSelection.value = new Set([id])
  } else {
    s.has(id) ? s.delete(id) : s.add(id)
    pickerSelection.value = s
  }
}

function confirmSlotPicker() {
  const key = pickerTarget.value
  if (pickerSingle.value) {
    const [first] = pickerSelection.value
    form.value.configData = { ...form.value.configData, [key]: first || "" }
  } else {
    form.value.configData = { ...form.value.configData, [key]: [...pickerSelection.value] }
  }
  showSlotPicker.value = false
}

function removeSlot(target, id) {
  const current = form.value.configData[target]
  if (Array.isArray(current)) {
    form.value.configData = { ...form.value.configData, [target]: current.filter(x => x !== id) }
  }
}

// ── Equipment helper ───────────────────────────────────────────────────────
function toggleEquipment(item) {
  const list = [...(form.value.configData.equipment || [])]
  const i = list.indexOf(item)
  i >= 0 ? list.splice(i, 1) : list.push(item)
  form.value.configData = { ...form.value.configData, equipment: list }
}

// ── Display helpers ────────────────────────────────────────────────────────
const TYPE_STYLES = {
  hard: { bg: "bg-red-100",   text: "text-red-700",   badge: "Hard" },
  soft: { bg: "bg-amber-100", text: "text-amber-700", badge: "Soft" },
}
const CAT_COLORS = {
  lecturer: "bg-purple-100 text-purple-700",
  room:     "bg-blue-100 text-blue-700",
  student:  "bg-green-100 text-green-700",
  academic: "bg-indigo-100 text-indigo-700",
  system:   "bg-gray-100 text-gray-600",
}
const SEV_ICONS = {
  hard: "M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z",
  soft: "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z",
}

const filtered = computed(() => {
  let list = constraints.value
  if (typeFilter.value)     list = list.filter(c => c.constraint_type === typeFilter.value)
  if (categoryFilter.value) list = list.filter(c => c.category === categoryFilter.value)
  return list
})

function entityLabel(c) {
  if (!c.entity_type || !c.entity_id) return null
  if (c.entity_type === "lecturer") {
    const l = lecturers.value.find(x => x.id === c.entity_id)
    return l ? `Lecturer: ${l.name}` : `Lecturer ID: ${c.entity_id.slice(0, 8)}`
  }
  if (c.entity_type === "room") {
    const r = rooms.value.find(x => x.id === c.entity_id)
    return r ? `Room: ${r.name}` : `Room ID: ${c.entity_id.slice(0, 8)}`
  }
  return `${c.entity_type}: ${c.entity_id.slice(0, 8)}`
}

// ── Data loading ───────────────────────────────────────────────────────────
async function load() {
  loading.value = true
  try {
    const [cr, lr, rr, tr] = await Promise.all([
      resourcesApi.constraints(),
      resourcesApi.lecturers(),
      resourcesApi.rooms(),
      resourcesApi.timeSlots(),
    ])
    constraints.value = cr.data.data || []
    lecturers.value   = lr.data.data || []
    rooms.value       = rr.data.data || []
    timeSlots.value   = tr.data.data || []
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to load constraints."))
  } finally {
    loading.value = false
  }
}

// ── Form open/close ────────────────────────────────────────────────────────
function openCreate() {
  editTarget.value  = null
  form.value        = blank()
  rawJsonDraft.value = "{}"
  rawJsonError.value = ""
  showRawJson.value  = false
  showForm.value     = true
}

function openEdit(c) {
  _openingEdit = true
  editTarget.value = c
  form.value = {
    name:            c.name,
    constraint_type: c.constraint_type,
    category:        c.category || "lecturer",
    rule_type:       c.rule_type || "",
    entity_type:     c.entity_type || "",
    entity_id:       c.entity_id || "",
    weight:          c.weight,
    configData:      JSON.parse(JSON.stringify(c.config || {})),
  }
  rawJsonDraft.value = JSON.stringify(form.value.configData, null, 2)
  rawJsonError.value = ""
  showRawJson.value  = false
  showForm.value     = true
  deleteTarget.value = null
  nextTick(() => { _openingEdit = false })
}

// ── Save ───────────────────────────────────────────────────────────────────
async function save() {
  if (!form.value.name)  { toast.error("Name is required."); return }
  if (rawJsonError.value) { toast.error("Fix the JSON error before saving."); return }
  saving.value = true
  const payload = {
    name:            form.value.name,
    constraint_type: form.value.constraint_type,
    category:        form.value.category,
    rule_type:       form.value.rule_type  || null,
    entity_type:     form.value.entity_type || null,
    entity_id:       form.value.entity_id  || null,
    weight:          Number(form.value.weight),
    config:          form.value.configData,
  }
  try {
    if (editTarget.value) {
      await resourcesApi.updateConstraint(editTarget.value.id, payload)
      toast.success("Constraint updated.")
    } else {
      await resourcesApi.createConstraint(payload)
      toast.success("Constraint created.")
    }
    form.value        = blank()
    showForm.value    = false
    editTarget.value  = null
    showRawJson.value = false
    await load()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to save constraint."))
  } finally {
    saving.value = false
  }
}

// ── Delete ─────────────────────────────────────────────────────────────────
async function confirmDelete() {
  if (!deleteTarget.value) return
  try {
    await resourcesApi.deleteConstraint(deleteTarget.value.id)
    toast.success("Constraint removed.")
    deleteTarget.value = null
    await load()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to delete constraint."))
  }
}

onMounted(load)
</script>

<template>
  <div class="space-y-6">

    <!-- ── Header ─────────────────────────────────────────────────────────── -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Constraints</h1>
        <p class="text-sm text-gray-500 mt-1">
          Scheduling rules loaded into the GA engine
          <span v-if="!loading" class="text-gray-400 ml-1">({{ constraints.length }} total)</span>
        </p>
      </div>
      <button class="btn-primary flex items-center gap-2" @click="openCreate">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4"/>
        </svg>
        Add Constraint
      </button>
    </div>

    <!-- ── Info banner ────────────────────────────────────────────────────── -->
    <div class="card bg-blue-50 border-blue-200 flex items-start gap-3 py-3">
      <svg class="w-5 h-5 text-blue-500 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
      </svg>
      <p class="text-sm text-blue-800">
        <strong>Hard constraints</strong> are never violated — they add a heavy penalty of 1000 per breach.
        <strong>Soft constraints</strong> are weighted — higher weight = stronger scheduling preference.
        Use <strong>Rule Type</strong> to target specific GA evaluation logic.
      </p>
    </div>

    <!-- ── Create / Edit form ─────────────────────────────────────────────── -->
    <div v-if="showForm" class="card space-y-5 border-blue-100 bg-blue-50/30">
      <div class="flex items-center justify-between">
        <h2 class="font-semibold text-gray-900">{{ editTarget ? "Edit Constraint" : "New Constraint" }}</h2>
        <button @click="showForm = false; editTarget = null" class="text-gray-400 hover:text-gray-600">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
          </svg>
        </button>
      </div>

      <div class="grid md:grid-cols-2 gap-4">
        <!-- Name -->
        <div class="md:col-span-2">
          <label class="label">Constraint Name *</label>
          <input v-model="form.name" class="input" placeholder="e.g. Dr. Omondi max 3 consecutive lectures"/>
        </div>

        <!-- Category -->
        <div>
          <label class="label">Category</label>
          <select v-model="form.category" class="input">
            <option v-for="(label, key) in CATEGORY_LABELS" :key="key" :value="key">{{ label }}</option>
          </select>
        </div>

        <!-- Rule Type -->
        <div>
          <label class="label">Rule Type</label>
          <select v-model="form.rule_type" class="input">
            <option value="">— None / Custom —</option>
            <option v-for="r in rulesForCategory" :key="r.value" :value="r.value">{{ r.label }}</option>
          </select>
          <p v-if="form.rule_type" class="text-xs text-gray-400 mt-1">Routes to dedicated evaluator logic in the fitness function.</p>
        </div>

        <!-- Constraint Type -->
        <div>
          <label class="label">Constraint Type</label>
          <select v-model="form.constraint_type" class="input">
            <option value="hard">Hard — must not be violated</option>
            <option value="soft">Soft — penalised by weight</option>
          </select>
        </div>

        <!-- Weight -->
        <div>
          <label class="label">Weight <span class="text-gray-400 font-normal text-xs">(soft only)</span></label>
          <input v-model.number="form.weight" type="number" step="0.1" min="0" max="100"
            class="input" :disabled="form.constraint_type === 'hard'"/>
        </div>

        <!-- Entity scoping -->
        <template v-if="['lecturer', 'room'].includes(form.category)">
          <div>
            <label class="label">Entity Type <span class="text-gray-400 font-normal text-xs">(optional scope)</span></label>
            <select v-model="form.entity_type" class="input">
              <option value="">— Global (all) —</option>
              <option value="lecturer">Specific Lecturer</option>
              <option value="room">Specific Room</option>
              <option value="student_group">Specific Student Group</option>
              <option value="course">Specific Course</option>
              <option value="program">Specific Program</option>
              <option value="department">Specific Department</option>
            </select>
          </div>

          <div v-if="form.entity_type === 'lecturer'">
            <label class="label">Lecturer</label>
            <select v-model="form.entity_id" class="input">
              <option value="">Select lecturer…</option>
              <option v-for="l in lecturers" :key="l.id" :value="l.id">{{ l.name }}</option>
            </select>
          </div>
          <div v-else-if="form.entity_type === 'room'">
            <label class="label">Room</label>
            <select v-model="form.entity_id" class="input">
              <option value="">Select room…</option>
              <option v-for="r in rooms" :key="r.id" :value="r.id">{{ r.name }} ({{ r.code }})</option>
            </select>
          </div>
          <div v-else-if="form.entity_type" class="md:col-span-1">
            <label class="label">Entity ID</label>
            <input v-model="form.entity_id" class="input font-mono text-sm" placeholder="UUID of the entity"/>
          </div>
        </template>
      </div>

      <!-- ── Config builder ──────────────────────────────────────────────── -->
      <div>
        <div class="flex items-center justify-between mb-1.5">
          <label class="label mb-0">Configuration</label>
          <!-- Advanced toggle (only for known rules that have a visual builder) -->
          <button
            v-if="form.rule_type && !NO_CONFIG_RULES.has(form.rule_type)"
            type="button"
            @click="showRawJson = !showRawJson"
            class="text-xs text-gray-400 hover:text-gray-600 transition-colors"
          >
            {{ showRawJson ? '▲ Hide raw JSON' : '▼ Edit raw JSON' }}
          </button>
        </div>

        <!-- No rule type → raw JSON is the primary UI -->
        <template v-if="!form.rule_type">
          <p class="text-xs text-gray-500 mb-1.5">Enter custom rule parameters as JSON.</p>
          <textarea
            :value="rawJsonDraft"
            @input="onRawJsonInput"
            rows="3"
            class="input font-mono text-xs"
            :class="rawJsonError ? 'border-red-400 focus:ring-red-400' : ''"
            placeholder="{}"
          />
          <p v-if="rawJsonError" class="text-xs text-red-600 mt-0.5">{{ rawJsonError }}</p>
          <p v-else class="text-xs text-gray-400 mt-0.5">Rule-specific parameters passed to the GA evaluator.</p>
        </template>

        <!-- Rules that need no configuration -->
        <template v-else-if="NO_CONFIG_RULES.has(form.rule_type)">
          <div class="p-3 bg-gray-50 rounded-xl border border-dashed border-gray-200 flex items-center gap-2 text-sm text-gray-500">
            <svg class="w-4 h-4 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
            No additional configuration needed for this rule type.
          </div>
        </template>

        <!-- Limit rules (max_daily_hours, max_weekly_hours, max_consecutive) -->
        <template v-else-if="LIMIT_RULES.has(form.rule_type)">
          <div class="flex items-center gap-3 p-3 bg-white rounded-xl border border-gray-200">
            <label class="text-sm text-gray-700 flex-shrink-0 font-medium">Limit</label>
            <input
              v-model.number="form.configData.limit"
              type="number" min="1" max="24"
              class="input w-28 text-center font-mono"
            />
            <span class="text-xs text-gray-400">
              {{ form.rule_type === 'max_daily_hours' ? 'hours per day' :
                 form.rule_type === 'max_weekly_hours' ? 'hours per week' : 'consecutive periods' }}
            </span>
          </div>
        </template>

        <!-- Slot-array rules (preferred_times, unavailable) -->
        <template v-else-if="SLOT_ARRAY_RULES.has(form.rule_type)">
          <div class="p-3 bg-white rounded-xl border border-gray-200 space-y-2.5">
            <p class="text-xs text-gray-500">Select the time slots that apply to this rule.</p>
            <!-- Chips for selected slots -->
            <div v-if="(form.configData.slot_ids || []).length" class="flex flex-wrap gap-1.5">
              <span
                v-for="id in form.configData.slot_ids" :key="id"
                class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800"
              >
                {{ slotLabel(id) }}
                <button type="button" @click="removeSlot('slot_ids', id)" class="text-blue-500 hover:text-blue-700 leading-none">×</button>
              </span>
            </div>
            <button type="button" @click="openSlotPicker('slot_ids')"
              class="btn-secondary text-sm inline-flex items-center gap-1.5">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
              </svg>
              {{ (form.configData.slot_ids || []).length ? '+ Add more slots' : 'Pick time slots' }}
            </button>
          </div>
        </template>

        <!-- exam_gap -->
        <template v-else-if="form.rule_type === 'exam_gap'">
          <div class="p-3 bg-white rounded-xl border border-gray-200 space-y-3">
            <div class="flex items-center gap-3">
              <label class="text-sm font-medium text-gray-700 flex-shrink-0">Min gap between exams</label>
              <input v-model.number="form.configData.min_gap_slots" type="number" min="1" max="20"
                class="input w-24 text-center font-mono"/>
              <span class="text-xs text-gray-400">periods</span>
            </div>
            <div>
              <p class="text-xs text-gray-500 mb-2">Exam time slots:</p>
              <div v-if="(form.configData.exam_slot_ids || []).length" class="flex flex-wrap gap-1.5 mb-2">
                <span v-for="id in form.configData.exam_slot_ids" :key="id"
                  class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-800">
                  {{ slotLabel(id) }}
                  <button type="button" @click="removeSlot('exam_slot_ids', id)" class="text-orange-500 hover:text-orange-700 leading-none">×</button>
                </span>
              </div>
              <button type="button" @click="openSlotPicker('exam_slot_ids')"
                class="btn-secondary text-sm inline-flex items-center gap-1.5">
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
                </svg>
                {{ (form.configData.exam_slot_ids || []).length ? '+ Add exam slots' : 'Pick exam slots' }}
              </button>
            </div>
          </div>
        </template>

        <!-- fixed_session (single-select) -->
        <template v-else-if="form.rule_type === 'fixed_session'">
          <div class="p-3 bg-white rounded-xl border border-gray-200 space-y-2.5">
            <p class="text-xs text-gray-500">Choose the one time slot this session must always occupy.</p>
            <div v-if="form.configData.slot_id" class="flex items-center gap-2">
              <span class="inline-flex items-center gap-1 px-2 py-1 rounded-full text-sm font-medium bg-indigo-100 text-indigo-800">
                {{ slotLabel(form.configData.slot_id) }}
              </span>
              <button type="button" @click="form.configData = { ...form.configData, slot_id: '' }"
                class="text-xs text-red-500 hover:text-red-700">Remove</button>
            </div>
            <button type="button" @click="openSlotPicker('slot_id', true)"
              class="btn-secondary text-sm inline-flex items-center gap-1.5">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
              </svg>
              {{ form.configData.slot_id ? 'Change slot' : 'Pick a time slot' }}
            </button>
          </div>
        </template>

        <!-- equipment_required -->
        <template v-else-if="form.rule_type === 'equipment_required'">
          <div class="p-3 bg-white rounded-xl border border-gray-200">
            <p class="text-xs text-gray-500 mb-2.5">Select the equipment the room must have:</p>
            <div class="flex flex-wrap gap-3">
              <label v-for="item in EQUIPMENT_OPTIONS" :key="item"
                class="flex items-center gap-1.5 cursor-pointer group">
                <input type="checkbox"
                  :checked="(form.configData.equipment || []).includes(item)"
                  @change="toggleEquipment(item)"
                  class="rounded text-blue-600 focus:ring-blue-500"/>
                <span class="text-sm text-gray-700 capitalize group-hover:text-gray-900">{{ item.replace(/_/g, ' ') }}</span>
              </label>
            </div>
          </div>
        </template>

        <!-- semester_only -->
        <template v-else-if="form.rule_type === 'semester_only'">
          <div class="p-3 bg-white rounded-xl border border-gray-200">
            <p class="text-xs text-gray-500 mb-2.5">This module runs in:</p>
            <div class="flex gap-5">
              <label class="flex items-center gap-2 cursor-pointer">
                <input type="radio" :value="1" v-model="form.configData.semester" class="text-blue-600 focus:ring-blue-500"/>
                <span class="text-sm font-medium text-gray-700">Semester 1</span>
              </label>
              <label class="flex items-center gap-2 cursor-pointer">
                <input type="radio" :value="2" v-model="form.configData.semester" class="text-blue-600 focus:ring-blue-500"/>
                <span class="text-sm font-medium text-gray-700">Semester 2</span>
              </label>
            </div>
          </div>
        </template>

        <!-- mandatory_order -->
        <template v-else-if="form.rule_type === 'mandatory_order'">
          <div class="p-3 bg-white rounded-xl border border-gray-200 space-y-3">
            <p class="text-xs text-gray-500">Ensure one course is always scheduled before another.</p>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="text-xs font-medium text-gray-600 block mb-1">Before course ID</label>
                <input v-model="form.configData.before_course_id"
                  class="input font-mono text-xs" placeholder="UUID of first course"/>
              </div>
              <div>
                <label class="text-xs font-medium text-gray-600 block mb-1">After course ID</label>
                <input v-model="form.configData.after_course_id"
                  class="input font-mono text-xs" placeholder="UUID of second course"/>
              </div>
            </div>
          </div>
        </template>

        <!-- shared_room -->
        <template v-else-if="form.rule_type === 'shared_room'">
          <div class="p-3 bg-white rounded-xl border border-gray-200 space-y-2">
            <label class="text-xs font-medium text-gray-600 block">Departments sharing this room (comma-separated names or IDs)</label>
            <input v-model="sharedRoomDepts" class="input"
              placeholder="e.g. Faculty of IT, Faculty of Commerce"/>
            <p v-if="(form.configData.departments || []).length" class="text-xs text-gray-400">
              {{ (form.configData.departments || []).length }} department(s) listed
            </p>
          </div>
        </template>

        <!-- timezone_aware -->
        <template v-else-if="form.rule_type === 'timezone_aware'">
          <div class="p-3 bg-white rounded-xl border border-gray-200">
            <label class="text-xs font-medium text-gray-600 block mb-1.5">Timezone</label>
            <select v-model="form.configData.timezone" class="input">
              <option v-for="tz in TIMEZONES" :key="tz" :value="tz">{{ tz }}</option>
            </select>
          </div>
        </template>

        <!-- Advanced raw JSON (shown when toggle is on, for all known rules) -->
        <div v-if="form.rule_type && !NO_CONFIG_RULES.has(form.rule_type) && showRawJson" class="mt-2">
          <textarea
            :value="rawJsonDraft"
            @input="onRawJsonInput"
            rows="3"
            class="input font-mono text-xs"
            :class="rawJsonError ? 'border-red-400 focus:ring-red-400' : ''"
          />
          <p v-if="rawJsonError" class="text-xs text-red-600 mt-0.5">{{ rawJsonError }}</p>
          <p v-else class="text-xs text-gray-400 mt-0.5">Edits here are reflected in the visual builder above.</p>
        </div>
      </div>
      <!-- /config builder -->

      <div class="flex gap-2">
        <button class="btn-primary" :disabled="saving" @click="save">
          {{ saving ? "Saving…" : (editTarget ? "Update" : "Create Constraint") }}
        </button>
        <button class="btn-secondary" @click="showForm = false; editTarget = null">Cancel</button>
      </div>
    </div>

    <!-- ── Delete confirmation ─────────────────────────────────────────────── -->
    <div v-if="deleteTarget" class="card border-red-200 bg-red-50 space-y-3">
      <p class="text-sm text-red-800 font-medium">
        Delete constraint <strong>"{{ deleteTarget.name }}"</strong>?
        This will disable its rule in the GA engine.
      </p>
      <div class="flex gap-2">
        <button class="btn-danger text-sm" @click="confirmDelete">Yes, delete</button>
        <button class="btn-secondary text-sm" @click="deleteTarget = null">Cancel</button>
      </div>
    </div>

    <!-- ── Filters ─────────────────────────────────────────────────────────── -->
    <div class="flex flex-wrap gap-2 items-center">
      <div class="flex gap-1">
        <button v-for="opt in [{val:'',label:'All Types'},{val:'hard',label:'Hard'},{val:'soft',label:'Soft'}]"
          :key="opt.val" @click="typeFilter = opt.val"
          :class="['px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
            typeFilter === opt.val ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200']">
          {{ opt.label }}
        </button>
      </div>
      <div class="flex gap-1">
        <button v-for="(label, key) in { '': 'All', ...CATEGORY_LABELS }"
          :key="key" @click="categoryFilter = key"
          :class="['px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
            categoryFilter === key ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200']">
          {{ label }}
        </button>
      </div>
    </div>

    <!-- ── Loading skeleton ───────────────────────────────────────────────── -->
    <div v-if="loading" class="space-y-3">
      <div v-for="i in 5" :key="i" class="card animate-pulse flex items-center gap-4">
        <div class="w-10 h-10 bg-gray-200 rounded-lg flex-shrink-0"></div>
        <div class="flex-1 space-y-2">
          <div class="h-4 bg-gray-200 rounded w-1/3"></div>
          <div class="h-3 bg-gray-200 rounded w-1/4"></div>
        </div>
      </div>
    </div>

    <!-- ── Empty state ────────────────────────────────────────────────────── -->
    <div v-else-if="!constraints.length" class="card text-center py-14">
      <div class="w-14 h-14 mx-auto bg-amber-50 rounded-2xl flex items-center justify-center mb-3">
        <svg class="w-7 h-7 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
        </svg>
      </div>
      <h3 class="font-semibold text-gray-900 mb-1">No constraints defined</h3>
      <p class="text-sm text-gray-500 mb-5">The GA engine applies these rules when generating timetables.</p>
      <button class="btn-primary" @click="openCreate">Add First Constraint</button>
    </div>

    <!-- ── No filter results ──────────────────────────────────────────────── -->
    <div v-else-if="!filtered.length" class="card text-center py-8 text-sm text-gray-500">
      No matching constraints.
      <button class="text-blue-600 underline ml-1" @click="typeFilter=''; categoryFilter=''">Clear filters</button>
    </div>

    <!-- ── Constraint list ────────────────────────────────────────────────── -->
    <div v-else class="space-y-2">
      <div v-for="c in filtered" :key="c.id"
        class="card flex items-start gap-4 hover:shadow-sm transition-shadow"
        :class="deleteTarget?.id === c.id ? 'border-red-300 bg-red-50' : ''">

        <div class="w-10 h-10 rounded-lg flex-shrink-0 flex items-center justify-center mt-0.5"
          :class="(TYPE_STYLES[c.constraint_type] || TYPE_STYLES.soft).bg">
          <svg class="w-5 h-5" :class="(TYPE_STYLES[c.constraint_type] || TYPE_STYLES.soft).text"
            fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.75">
            <path stroke-linecap="round" stroke-linejoin="round"
              :d="SEV_ICONS[c.constraint_type] || SEV_ICONS.soft"/>
          </svg>
        </div>

        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 flex-wrap">
            <p class="font-semibold text-gray-900">{{ c.name }}</p>
            <span class="px-1.5 py-0.5 rounded text-xs font-semibold"
              :class="[(TYPE_STYLES[c.constraint_type] || TYPE_STYLES.soft).bg,
                       (TYPE_STYLES[c.constraint_type] || TYPE_STYLES.soft).text]">
              {{ (TYPE_STYLES[c.constraint_type] || TYPE_STYLES.soft).badge }}
            </span>
            <span class="px-1.5 py-0.5 rounded text-xs font-medium"
              :class="CAT_COLORS[c.category] || 'bg-gray-100 text-gray-600'">
              {{ CATEGORY_LABELS[c.category] || c.category }}
            </span>
            <span v-if="c.rule_type" class="px-1.5 py-0.5 rounded text-xs font-mono bg-indigo-50 text-indigo-700">
              {{ c.rule_type }}
            </span>
          </div>
          <p class="text-xs text-gray-400 mt-1 space-x-2">
            <span>Weight: <span class="font-mono">{{ c.weight }}</span></span>
            <span v-if="entityLabel(c)" class="text-purple-600">· {{ entityLabel(c) }}</span>
            <span v-if="c.config && Object.keys(c.config).length">
              · <span class="font-mono">{{ JSON.stringify(c.config) }}</span>
            </span>
          </p>
        </div>

        <div class="flex items-center gap-1 flex-shrink-0">
          <button class="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg" @click="openEdit(c)" title="Edit">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/>
            </svg>
          </button>
          <button class="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg" @click="deleteTarget = c" title="Delete">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
            </svg>
          </button>
        </div>
      </div>
    </div>
  </div>

  <!-- ── Slot Picker Modal ─────────────────────────────────────────────────── -->
  <teleport to="body">
    <transition name="modal-fade">
      <div v-if="showSlotPicker"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
        @click.self="showSlotPicker = false">
        <div class="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[80vh] flex flex-col">

          <!-- Modal header -->
          <div class="px-5 py-4 border-b flex items-center justify-between">
            <h3 class="font-semibold text-gray-900">
              {{ pickerSingle ? 'Pick a Time Slot' : 'Pick Time Slots' }}
            </h3>
            <button @click="showSlotPicker = false" class="text-gray-400 hover:text-gray-600">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
              </svg>
            </button>
          </div>

          <!-- Slot list -->
          <div class="overflow-y-auto flex-1 px-5 py-3">
            <div v-if="!slotsByDay.length" class="py-8 text-center text-sm text-gray-400">
              No time slots found. Make sure a timetable template is configured for this university.
            </div>
            <div v-for="group in slotsByDay" :key="group.day" class="mb-4">
              <p class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-1.5 sticky top-0 bg-white py-0.5">
                {{ group.day }}
              </p>
              <div class="space-y-0.5">
                <label v-for="slot in group.slots" :key="slot.id"
                  class="flex items-center gap-3 px-2 py-1.5 rounded-lg hover:bg-gray-50 cursor-pointer transition-colors"
                  :class="pickerSelection.has(slot.id) ? 'bg-blue-50' : ''">
                  <input
                    v-if="pickerSingle"
                    type="radio"
                    :value="slot.id"
                    :checked="pickerSelection.has(slot.id)"
                    @change="togglePickerSlot(slot.id)"
                    class="text-blue-600 focus:ring-blue-500"
                  />
                  <input
                    v-else
                    type="checkbox"
                    :checked="pickerSelection.has(slot.id)"
                    @change="togglePickerSlot(slot.id)"
                    class="rounded text-blue-600 focus:ring-blue-500"
                  />
                  <span class="flex-1 min-w-0">
                    <span class="text-sm font-mono text-gray-800">{{ slot.start_time }}–{{ slot.end_time }}</span>
                    <span v-if="slot.label || slot.name" class="text-xs text-gray-400 ml-2">{{ slot.label || slot.name }}</span>
                    <span v-if="slot.slot_index != null" class="text-xs text-gray-300 ml-1">P{{ slot.slot_index }}</span>
                  </span>
                </label>
              </div>
            </div>
          </div>

          <!-- Modal footer -->
          <div class="px-5 py-3 border-t flex items-center justify-between gap-3 bg-gray-50 rounded-b-2xl">
            <span class="text-sm text-gray-500">
              <template v-if="pickerSingle">
                {{ pickerSelection.size ? '1 slot selected' : 'None selected' }}
              </template>
              <template v-else>
                {{ pickerSelection.size }} slot{{ pickerSelection.size !== 1 ? 's' : '' }} selected
              </template>
            </span>
            <div class="flex gap-2">
              <button type="button" @click="showSlotPicker = false" class="btn-secondary text-sm">Cancel</button>
              <button type="button" @click="confirmSlotPicker" class="btn-primary text-sm">
                Confirm selection
              </button>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<style scoped>
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.15s ease;
}
.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}
.modal-fade-enter-active .bg-white,
.modal-fade-leave-active .bg-white {
  transition: transform 0.15s ease;
}
.modal-fade-enter-from .bg-white {
  transform: scale(0.96);
}
.modal-fade-leave-to .bg-white {
  transform: scale(0.96);
}
</style>
