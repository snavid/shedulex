<script setup>
import { onMounted, ref, computed, watch } from "vue"
import { resourcesApi, getErrorMessage } from "@/api/client"
import { useToast } from "vue-toastification"

const toast = useToast()
const loading = ref(true)
const saving = ref(false)
const constraints = ref([])
const lecturers = ref([])
const rooms = ref([])
const showForm = ref(false)
const editTarget = ref(null)
const deleteTarget = ref(null)
const typeFilter = ref("")
const categoryFilter = ref("")

// ── Rule type catalogue ────────────────────────────────────────────────────
const RULE_CATALOGUE = {
  lecturer: [
    { value: "max_daily_hours",  label: "Max daily teaching hours",    config_hint: '{"limit": 6}' },
    { value: "max_weekly_hours", label: "Max weekly teaching hours",   config_hint: '{"limit": 20}' },
    { value: "max_consecutive",  label: "Max consecutive periods",     config_hint: '{"limit": 3}' },
    { value: "preferred_times",  label: "Preferred time slots",        config_hint: '{"slot_ids": []}' },
    { value: "unavailable",      label: "Unavailable periods",         config_hint: '{"slot_ids": []}' },
  ],
  room: [
    { value: "capacity_check",    label: "Room capacity enforcement",  config_hint: '{}' },
    { value: "equipment_required",label: "Required equipment",         config_hint: '{"equipment": ["projector"]}' },
    { value: "shared_room",       label: "Shared-room booking rules",  config_hint: '{"departments": []}' },
  ],
  student: [
    { value: "no_overlap",       label: "No student group overlap",    config_hint: '{}' },
    { value: "max_consecutive",  label: "Max consecutive classes",     config_hint: '{"limit": 4}' },
    { value: "exam_gap",         label: "Exam preparation gap",        config_hint: '{"min_gap_slots": 2, "exam_slot_ids": []}' },
  ],
  academic: [
    { value: "semester_only",    label: "Semester-only module",        config_hint: '{"semester": 1}' },
    { value: "fixed_session",    label: "Fixed session time",          config_hint: '{"slot_id": ""}' },
    { value: "mandatory_order",  label: "Mandatory ordering",          config_hint: '{"before_course_id": "", "after_course_id": ""}' },
  ],
  system: [
    { value: "timezone_aware",   label: "Timezone-aware scheduling",   config_hint: '{"timezone": "UTC"}' },
    { value: "holiday_aware",    label: "Skip public holidays",        config_hint: '{}' },
  ],
}

const CATEGORY_LABELS = {
  lecturer: "Lecturer", room: "Room", student: "Student",
  academic: "Academic", system: "System",
}

const blank = () => ({
  name: "", constraint_type: "soft", category: "lecturer",
  rule_type: "", entity_type: "", entity_id: "",
  weight: 1.0, config: "{}",
})
const form = ref(blank())
const configError = ref("")

const rulesForCategory = computed(() =>
  RULE_CATALOGUE[form.value.category] || [],
)
watch(() => form.value.category, () => {
  form.value.rule_type = ""
  form.value.entity_type = ""
  form.value.entity_id = ""
  form.value.config = "{}"
})
watch(() => form.value.rule_type, (v) => {
  const rule = rulesForCategory.value.find(r => r.value === v)
  if (rule) form.value.config = rule.config_hint || "{}"
  // Auto-set entity_type
  if (form.value.category === "lecturer") form.value.entity_type = "lecturer"
  else if (form.value.category === "room") form.value.entity_type = "room"
  else if (form.value.category === "student") form.value.entity_type = "student_group"
  else form.value.entity_type = ""
})

const TYPE_STYLES = {
  hard: { bg: "bg-red-100", text: "text-red-700", badge: "Hard" },
  soft: { bg: "bg-amber-100", text: "text-amber-700", badge: "Soft" },
}
const CAT_COLORS = {
  lecturer: "bg-purple-100 text-purple-700",
  room:     "bg-blue-100  text-blue-700",
  student:  "bg-green-100 text-green-700",
  academic: "bg-indigo-100 text-indigo-700",
  system:   "bg-gray-100  text-gray-600",
}

const SEV_ICONS = {
  hard: "M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z",
  soft: "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z",
}

const filtered = computed(() => {
  let list = constraints.value
  if (typeFilter.value) list = list.filter(c => c.constraint_type === typeFilter.value)
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

function validateConfig() {
  try {
    JSON.parse(form.value.config || "{}")
    configError.value = ""
    return true
  } catch {
    configError.value = "Config must be valid JSON."
    return false
  }
}

async function load() {
  loading.value = true
  try {
    const [cr, lr, rr] = await Promise.all([
      resourcesApi.constraints(),
      resourcesApi.lecturers(),
      resourcesApi.rooms(),
    ])
    constraints.value = cr.data.data || []
    lecturers.value = lr.data.data || []
    rooms.value = rr.data.data || []
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to load constraints."))
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editTarget.value = null
  form.value = blank()
  showForm.value = true
}

function openEdit(c) {
  editTarget.value = c
  form.value = {
    name: c.name,
    constraint_type: c.constraint_type,
    category: c.category || "lecturer",
    rule_type: c.rule_type || "",
    entity_type: c.entity_type || "",
    entity_id: c.entity_id || "",
    weight: c.weight,
    config: JSON.stringify(c.config || {}),
  }
  showForm.value = true
  deleteTarget.value = null
}

async function save() {
  if (!form.value.name) { toast.error("Name is required."); return }
  if (!validateConfig()) return
  saving.value = true
  const payload = {
    name: form.value.name,
    constraint_type: form.value.constraint_type,
    category: form.value.category,
    rule_type: form.value.rule_type || null,
    entity_type: form.value.entity_type || null,
    entity_id: form.value.entity_id || null,
    weight: Number(form.value.weight),
    config: JSON.parse(form.value.config || "{}"),
  }
  try {
    if (editTarget.value) {
      await resourcesApi.updateConstraint(editTarget.value.id, payload)
      toast.success("Constraint updated.")
    } else {
      await resourcesApi.createConstraint(payload)
      toast.success("Constraint created.")
    }
    form.value = blank()
    showForm.value = false
    editTarget.value = null
    await load()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to save constraint."))
  } finally {
    saving.value = false
  }
}

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
    <!-- Header -->
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

    <!-- Info banner -->
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

    <!-- Create / Edit form -->
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
        <div class="md:col-span-2">
          <label class="label">Constraint Name *</label>
          <input v-model="form.name" class="input" placeholder="e.g. Dr. Omondi max 3 consecutive lectures"/>
        </div>

        <div>
          <label class="label">Category</label>
          <select v-model="form.category" class="input">
            <option v-for="(label, key) in CATEGORY_LABELS" :key="key" :value="key">{{ label }}</option>
          </select>
        </div>

        <div>
          <label class="label">Rule Type</label>
          <select v-model="form.rule_type" class="input">
            <option value="">— None / Custom —</option>
            <option v-for="r in rulesForCategory" :key="r.value" :value="r.value">{{ r.label }}</option>
          </select>
          <p v-if="form.rule_type" class="text-xs text-gray-400 mt-1">
            Routes to dedicated evaluator logic in the fitness function.
          </p>
        </div>

        <div>
          <label class="label">Constraint Type</label>
          <select v-model="form.constraint_type" class="input">
            <option value="hard">Hard — must not be violated</option>
            <option value="soft">Soft — penalised by weight</option>
          </select>
        </div>

        <div>
          <label class="label">Weight <span class="text-gray-400 font-normal text-xs">(soft only)</span></label>
          <input v-model.number="form.weight" type="number" step="0.1" min="0" max="100"
            class="input" :disabled="form.constraint_type === 'hard'"/>
        </div>

        <!-- Entity scoping for lecturer/room rules -->
        <template v-if="['lecturer', 'room'].includes(form.category)">
          <div>
            <label class="label">Entity Type <span class="text-gray-400 font-normal text-xs">(optional scope)</span></label>
            <select v-model="form.entity_type" class="input">
              <option value="">— Global (all) —</option>
              <option value="lecturer">Specific Lecturer</option>
              <option value="room">Specific Room</option>
              <option value="student_group">Specific Student Group</option>
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

      <div>
        <label class="label">Config JSON</label>
        <textarea v-model="form.config" rows="3" class="input font-mono text-xs"
          :class="configError ? 'border-red-400 focus:ring-red-400' : ''"
          placeholder='{"limit": 3}' @blur="validateConfig"/>
        <p v-if="configError" class="text-xs text-red-600 mt-1">{{ configError }}</p>
        <p v-else class="text-xs text-gray-400 mt-1">
          Rule-specific parameters passed to the GA evaluator.
          <span v-if="rulesForCategory.find(r => r.value === form.rule_type)?.config_hint" class="text-blue-500 cursor-pointer"
            @click="form.config = rulesForCategory.find(r => r.value === form.rule_type).config_hint">
            Use template
          </span>
        </p>
      </div>

      <div class="flex gap-2">
        <button class="btn-primary" :disabled="saving" @click="save">
          {{ saving ? "Saving…" : (editTarget ? "Update" : "Create Constraint") }}
        </button>
        <button class="btn-secondary" @click="showForm = false; editTarget = null">Cancel</button>
      </div>
    </div>

    <!-- Delete confirmation -->
    <div v-if="deleteTarget" class="card border-red-200 bg-red-50 space-y-3">
      <p class="text-sm text-red-800 font-medium">Delete constraint <strong>"{{ deleteTarget.name }}"</strong>? This will disable its rule in the GA engine.</p>
      <div class="flex gap-2">
        <button class="btn-danger text-sm" @click="confirmDelete">Yes, delete</button>
        <button class="btn-secondary text-sm" @click="deleteTarget = null">Cancel</button>
      </div>
    </div>

    <!-- Filters -->
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

    <!-- Loading -->
    <div v-if="loading" class="space-y-3">
      <div v-for="i in 5" :key="i" class="card animate-pulse flex items-center gap-4">
        <div class="w-10 h-10 bg-gray-200 rounded-lg flex-shrink-0"></div>
        <div class="flex-1 space-y-2">
          <div class="h-4 bg-gray-200 rounded w-1/3"></div>
          <div class="h-3 bg-gray-200 rounded w-1/4"></div>
        </div>
      </div>
    </div>

    <!-- Empty state -->
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

    <!-- No filter results -->
    <div v-else-if="!filtered.length" class="card text-center py-8 text-sm text-gray-500">
      No matching constraints. <button class="text-blue-600 underline" @click="typeFilter=''; categoryFilter=''">Clear filters</button>
    </div>

    <!-- List -->
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
</template>
