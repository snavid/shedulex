<script setup>
import { ref, onMounted, computed } from "vue"
import { resourcesApi, getErrorMessage } from "@/api/client"
import { useAuthStore } from "@/stores/auth"
import { useToast } from "vue-toastification"

const toast = useToast()
const auth = useAuthStore()
const loading = ref(true)
const saving = ref(false)
const generating = ref(false)
const templates = ref([])
const slots = ref([])
const selectedTemplateId = ref("")
const showTemplateForm = ref(false)
const showBlockForm = ref(false)
const editBlock = ref(null)
const deleteBlockTarget = ref(null)
const showSlotForm = ref(false)

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
const BLOCK_TYPES = [
  { value: "class",  label: "Class Period",   color: "bg-blue-100 text-blue-800 border-blue-300" },
  { value: "lab",    label: "Lab Session",     color: "bg-purple-100 text-purple-800 border-purple-300" },
  { value: "break",  label: "Break",           color: "bg-orange-100 text-orange-800 border-orange-300" },
  { value: "lunch",  label: "Lunch Break",     color: "bg-green-100 text-green-800 border-green-300" },
  { value: "exam",   label: "Exam Block",      color: "bg-red-100 text-red-800 border-red-300" },
]
function blockStyle(type) {
  return BLOCK_TYPES.find(b => b.value === type)?.color || "bg-gray-100 text-gray-700 border-gray-300"
}

const templateForm = ref({ name: "", description: "", is_default: false,
  days_of_week: ["Monday","Tuesday","Wednesday","Thursday","Friday"] })
const blockForm = ref({ label: "", start_time: "08:00", end_time: "09:00", block_type: "class", sort_order: 0 })
const manualSlotForm = ref({ day: "Monday", start_time: "08:00", end_time: "09:00",
  slot_type: "class", label: "", is_break: false })

const selectedTemplate = computed(() => templates.value.find(t => t.id === selectedTemplateId.value))

const filteredSlots = computed(() => {
  if (!selectedTemplateId.value) return slots.value
  return slots.value.filter(s => s.template_id === selectedTemplateId.value)
})
const slotsByDay = computed(() => {
  const map = {}
  for (const day of DAYS) {
    map[day] = filteredSlots.value.filter(s => s.day === day)
      .sort((a, b) => a.slot_index - b.slot_index)
  }
  return map
})

async function load() {
  loading.value = true
  try {
    const [tr, sr] = await Promise.all([
      resourcesApi.templates(),
      resourcesApi.timeSlots(),
    ])
    templates.value = tr.data.data || []
    slots.value = sr.data.data || []
    if (templates.value.length && !selectedTemplateId.value) {
      selectedTemplateId.value = templates.value[0].id
    }
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to load time slots."))
  } finally {
    loading.value = false
  }
}

async function createTemplate() {
  if (!templateForm.value.name) { toast.error("Template name is required."); return }
  saving.value = true
  try {
    const { data } = await resourcesApi.createTemplate({
      ...templateForm.value,
      university_id: auth.user?.university_id,
      blocks: [],
    })
    templates.value.push(data.data)
    selectedTemplateId.value = data.data.id
    templateForm.value = { name: "", description: "", is_default: false,
      days_of_week: ["Monday","Tuesday","Wednesday","Thursday","Friday"] }
    showTemplateForm.value = false
    toast.success("Template created.")
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to create template."))
  } finally {
    saving.value = false
  }
}

async function addBlock() {
  if (!selectedTemplateId.value) return
  if (!blockForm.value.label || !blockForm.value.start_time || !blockForm.value.end_time) {
    toast.error("Label, start time, and end time are required.")
    return
  }
  saving.value = true
  try {
    if (editBlock.value) {
      await resourcesApi.updateTemplateBlock(selectedTemplateId.value, editBlock.value.id, blockForm.value)
      toast.success("Block updated.")
    } else {
      await resourcesApi.createTemplateBlock(selectedTemplateId.value, blockForm.value)
      toast.success("Block added.")
    }
    editBlock.value = null
    blockForm.value = { label: "", start_time: "08:00", end_time: "09:00", block_type: "class", sort_order: 0 }
    showBlockForm.value = false
    await load()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to save block."))
  } finally {
    saving.value = false
  }
}

async function deleteBlock(block) {
  if (!confirm(`Delete block "${block.label}"?`)) return
  try {
    await resourcesApi.deleteTemplateBlock(selectedTemplateId.value, block.id)
    toast.success("Block deleted.")
    await load()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to delete block."))
  }
}

function startEditBlock(block) {
  editBlock.value = block
  blockForm.value = { label: block.label, start_time: block.start_time,
    end_time: block.end_time, block_type: block.block_type, sort_order: block.sort_order }
  showBlockForm.value = true
}

async function generateSlots() {
  if (!selectedTemplateId.value) return
  if (!selectedTemplate.value?.blocks?.length) {
    toast.error("Add at least one time block to the template first.")
    return
  }
  if (!confirm(`Generate time slots from template "${selectedTemplate.value.name}"? Existing slots for this template will be replaced.`)) return
  generating.value = true
  try {
    const { data } = await resourcesApi.generateSlotsFromTemplate(selectedTemplateId.value)
    toast.success(`Generated ${data.extra?.generated || 0} time slots.`)
    await load()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to generate slots."))
  } finally {
    generating.value = false
  }
}

async function addManualSlot() {
  if (!manualSlotForm.value.day || !manualSlotForm.value.start_time) {
    toast.error("Day and start time are required.")
    return
  }
  saving.value = true
  try {
    const payload = {
      ...manualSlotForm.value,
      is_break: manualSlotForm.value.slot_type === "break" || manualSlotForm.value.slot_type === "lunch",
      template_id: selectedTemplateId.value || null,
      slot_index: slots.value.length,
    }
    await resourcesApi.createTimeSlot(payload)
    toast.success("Slot added.")
    showSlotForm.value = false
    manualSlotForm.value = { day: "Monday", start_time: "08:00", end_time: "09:00",
      slot_type: "class", label: "", is_break: false }
    await load()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to add slot."))
  } finally {
    saving.value = false
  }
}

async function deleteSlot(slot) {
  if (!confirm(`Delete slot "${slot.label || slot.day + ' ' + slot.start_time}"?`)) return
  try {
    await resourcesApi.deleteTimeSlot(slot.id)
    slots.value = slots.value.filter(s => s.id !== slot.id)
    toast.success("Slot deleted.")
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to delete slot."))
  }
}

onMounted(load)
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between flex-wrap gap-3">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Timetable Templates & Time Slots</h1>
        <p class="text-sm text-gray-500 mt-1">Define academic daily schedules. Templates generate slot grids for the GA engine.</p>
      </div>
      <div class="flex gap-2">
        <button class="btn-secondary text-sm" @click="showTemplateForm = !showTemplateForm">+ New Template</button>
        <button class="btn-secondary text-sm" @click="showSlotForm = !showSlotForm">+ Add Slot Manually</button>
      </div>
    </div>

    <!-- New template form -->
    <div v-if="showTemplateForm" class="card space-y-4 border-blue-100 bg-blue-50/30">
      <h3 class="font-semibold text-gray-900">New Schedule Template</h3>
      <div class="grid md:grid-cols-2 gap-4">
        <div>
          <label class="label">Template Name *</label>
          <input v-model="templateForm.name" class="input" placeholder="e.g. Standard 8–5 Weekday"/>
        </div>
        <div>
          <label class="label">Description</label>
          <input v-model="templateForm.description" class="input" placeholder="Brief description…"/>
        </div>
      </div>
      <div>
        <label class="label">Days of Week</label>
        <div class="flex gap-2 flex-wrap">
          <label v-for="d in DAYS" :key="d" class="flex items-center gap-1.5 text-sm cursor-pointer">
            <input type="checkbox" :value="d" v-model="templateForm.days_of_week" class="rounded"/>
            {{ d.slice(0,3) }}
          </label>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <input type="checkbox" v-model="templateForm.is_default" id="is_default" class="rounded"/>
        <label for="is_default" class="text-sm text-gray-700">Set as default template</label>
      </div>
      <div class="flex gap-2">
        <button class="btn-primary text-sm" :disabled="saving" @click="createTemplate">
          {{ saving ? "Creating…" : "Create Template" }}
        </button>
        <button class="btn-secondary text-sm" @click="showTemplateForm = false">Cancel</button>
      </div>
    </div>

    <!-- Template selector -->
    <div v-if="templates.length" class="flex gap-2 flex-wrap items-center">
      <span class="text-sm text-gray-500 mr-1">Template:</span>
      <button v-for="t in templates" :key="t.id" @click="selectedTemplateId = t.id"
        :class="['px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors',
          selectedTemplateId === t.id
            ? 'bg-blue-600 text-white border-blue-600'
            : 'bg-white text-gray-700 border-gray-200 hover:border-blue-300']">
        {{ t.name }}
        <span v-if="t.is_default" class="ml-1 text-xs opacity-75">(default)</span>
      </button>
      <span v-if="!templates.length" class="text-sm text-gray-400">No templates yet</span>
    </div>

    <!-- Template blocks editor -->
    <div v-if="selectedTemplate" class="card space-y-4">
      <div class="flex items-center justify-between">
        <div>
          <h2 class="font-semibold text-gray-900">{{ selectedTemplate.name }} — Time Blocks</h2>
          <p class="text-xs text-gray-500 mt-0.5">
            {{ selectedTemplate.days_of_week?.join(", ") }} ·
            {{ selectedTemplate.blocks?.length || 0 }} blocks defined
          </p>
        </div>
        <div class="flex gap-2">
          <button class="btn-secondary text-sm" @click="showBlockForm = !showBlockForm; editBlock = null">+ Add Block</button>
          <button class="btn-primary text-sm" :disabled="generating" @click="generateSlots">
            {{ generating ? "Generating…" : "Generate Slots" }}
          </button>
        </div>
      </div>

      <!-- Block form -->
      <div v-if="showBlockForm" class="border border-blue-200 rounded-xl p-4 bg-blue-50/30 space-y-3">
        <h4 class="text-sm font-semibold text-gray-800">{{ editBlock ? "Edit Block" : "Add Time Block" }}</h4>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div class="col-span-2 md:col-span-1">
            <label class="label text-xs">Label *</label>
            <input v-model="blockForm.label" class="input text-sm" placeholder="Period 1"/>
          </div>
          <div>
            <label class="label text-xs">Start</label>
            <input v-model="blockForm.start_time" type="time" class="input text-sm"/>
          </div>
          <div>
            <label class="label text-xs">End</label>
            <input v-model="blockForm.end_time" type="time" class="input text-sm"/>
          </div>
          <div>
            <label class="label text-xs">Type</label>
            <select v-model="blockForm.block_type" class="input text-sm">
              <option v-for="bt in BLOCK_TYPES" :key="bt.value" :value="bt.value">{{ bt.label }}</option>
            </select>
          </div>
          <div>
            <label class="label text-xs">Sort Order</label>
            <input v-model.number="blockForm.sort_order" type="number" class="input text-sm"/>
          </div>
        </div>
        <div class="flex gap-2">
          <button class="btn-primary text-sm" :disabled="saving" @click="addBlock">
            {{ saving ? "Saving…" : (editBlock ? "Update" : "Add Block") }}
          </button>
          <button class="btn-secondary text-sm" @click="showBlockForm = false; editBlock = null">Cancel</button>
        </div>
      </div>

      <!-- Blocks visual strip -->
      <div v-if="selectedTemplate.blocks?.length" class="space-y-2">
        <p class="text-xs font-medium text-gray-500 uppercase tracking-wide">Daily Schedule Preview</p>
        <div class="flex gap-1 flex-wrap">
          <div v-for="block in selectedTemplate.blocks" :key="block.id"
            class="flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-medium"
            :class="blockStyle(block.block_type)">
            <span>{{ block.start_time }}</span>
            <span class="opacity-50">→</span>
            <span>{{ block.end_time }}</span>
            <span class="font-bold">{{ block.label }}</span>
            <div class="flex gap-0.5 ml-1">
              <button class="opacity-60 hover:opacity-100" @click="startEditBlock(block)" title="Edit">
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/>
                </svg>
              </button>
              <button class="opacity-60 hover:opacity-100 hover:text-red-600" @click="deleteBlock(block)" title="Delete">
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>
      <div v-else class="text-sm text-gray-400 text-center py-4 border border-dashed border-gray-200 rounded-xl">
        No blocks defined. Add time blocks then click "Generate Slots".
      </div>
    </div>

    <!-- Manual slot add form -->
    <div v-if="showSlotForm" class="card space-y-4 border-indigo-100 bg-indigo-50/20">
      <h3 class="font-semibold text-gray-900">Add Manual Time Slot</h3>
      <div class="grid grid-cols-2 md:grid-cols-3 gap-3">
        <div>
          <label class="label text-xs">Day *</label>
          <select v-model="manualSlotForm.day" class="input text-sm">
            <option v-for="d in DAYS" :key="d">{{ d }}</option>
          </select>
        </div>
        <div>
          <label class="label text-xs">Start Time *</label>
          <input v-model="manualSlotForm.start_time" type="time" class="input text-sm"/>
        </div>
        <div>
          <label class="label text-xs">End Time</label>
          <input v-model="manualSlotForm.end_time" type="time" class="input text-sm"/>
        </div>
        <div>
          <label class="label text-xs">Type</label>
          <select v-model="manualSlotForm.slot_type" class="input text-sm">
            <option v-for="bt in BLOCK_TYPES" :key="bt.value" :value="bt.value">{{ bt.label }}</option>
          </select>
        </div>
        <div>
          <label class="label text-xs">Label</label>
          <input v-model="manualSlotForm.label" class="input text-sm" placeholder="Period 1"/>
        </div>
      </div>
      <div class="flex gap-2">
        <button class="btn-primary text-sm" :disabled="saving" @click="addManualSlot">
          {{ saving ? "Adding…" : "Add Slot" }}
        </button>
        <button class="btn-secondary text-sm" @click="showSlotForm = false">Cancel</button>
      </div>
    </div>

    <!-- Time slot grid view -->
    <div v-if="!loading" class="space-y-4">
      <div class="flex items-center justify-between">
        <h2 class="font-semibold text-gray-900">
          Generated Slots
          <span class="text-gray-400 font-normal text-sm ml-1">({{ filteredSlots.length }})</span>
        </h2>
        <div class="flex gap-2 text-xs">
          <span v-for="bt in BLOCK_TYPES" :key="bt.value"
            class="px-2 py-0.5 rounded border" :class="blockStyle(bt.value)">
            {{ bt.label }}
          </span>
        </div>
      </div>

      <div v-if="filteredSlots.length" class="grid gap-3" style="grid-template-columns: repeat(auto-fit, minmax(200px, 1fr))">
        <div v-for="day in DAYS" :key="day" v-show="slotsByDay[day]?.length">
          <h4 class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">{{ day }}</h4>
          <div class="space-y-1">
            <div v-for="slot in slotsByDay[day]" :key="slot.id"
              class="flex items-center justify-between px-2.5 py-1.5 rounded-lg border text-xs"
              :class="blockStyle(slot.slot_type || (slot.is_break ? 'break' : 'class'))">
              <div>
                <span class="font-medium">{{ slot.label || `${slot.start_time}–${slot.end_time}` }}</span>
                <span class="opacity-60 ml-1">{{ slot.start_time }}–{{ slot.end_time }}</span>
              </div>
              <button class="opacity-50 hover:opacity-100 hover:text-red-600 ml-1" @click="deleteSlot(slot)">
                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>
      <div v-else class="card text-center py-12 text-gray-400">
        <p>No time slots yet. Create a template, add blocks, then click "Generate Slots".</p>
      </div>
    </div>
    <div v-else class="card text-center py-10 text-gray-400 animate-pulse">Loading…</div>
  </div>
</template>
