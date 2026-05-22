<script setup>
import { onMounted, ref, computed } from "vue"
import { resourcesApi, getErrorMessage } from "@/api/client"
import { useToast } from "vue-toastification"

const toast = useToast()
const loading = ref(true)
const saving = ref(false)
const rooms = ref([])
const showForm = ref(false)
const editTarget = ref(null)
const deleteTarget = ref(null)
const search = ref("")
const typeFilter = ref("")

const blank = () => ({ name: "", code: "", capacity: 40, room_type: "lecture", building: "", floor: 1 })
const form = ref(blank())

const TYPE_COLORS = {
  lecture: { bg: "bg-blue-100", text: "text-blue-700", label: "Lecture" },
  lab: { bg: "bg-purple-100", text: "text-purple-700", label: "Lab" },
  seminar: { bg: "bg-teal-100", text: "text-teal-700", label: "Seminar" },
  auditorium: { bg: "bg-orange-100", text: "text-orange-700", label: "Auditorium" },
}

const filtered = computed(() => {
  let list = rooms.value
  if (typeFilter.value) list = list.filter((r) => r.room_type === typeFilter.value)
  const q = search.value.toLowerCase()
  if (q) list = list.filter((r) => r.name.toLowerCase().includes(q) || r.code.toLowerCase().includes(q) || (r.building || "").toLowerCase().includes(q))
  return list
})

async function load() {
  loading.value = true
  try {
    const { data } = await resourcesApi.rooms()
    rooms.value = data.data || []
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to load rooms."))
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editTarget.value = null
  form.value = blank()
  showForm.value = true
  deleteTarget.value = null
}

function openEdit(r) {
  editTarget.value = r
  form.value = { name: r.name, code: r.code, capacity: r.capacity, room_type: r.room_type, building: r.building || "", floor: r.floor || 1 }
  showForm.value = true
  deleteTarget.value = null
}

async function save() {
  if (!form.value.name || !form.value.code) {
    toast.error("Name and code are required.")
    return
  }
  saving.value = true
  try {
    if (editTarget.value) {
      await resourcesApi.updateRoom(editTarget.value.id, form.value)
      toast.success("Room updated.")
    } else {
      await resourcesApi.createRoom(form.value)
      toast.success("Room created.")
    }
    showForm.value = false
    editTarget.value = null
    await load()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to save room."))
  } finally {
    saving.value = false
  }
}

async function confirmDelete() {
  if (!deleteTarget.value) return
  try {
    await resourcesApi.deleteRoom(deleteTarget.value.id)
    toast.success("Room deleted.")
    deleteTarget.value = null
    await load()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to delete room."))
  }
}

onMounted(load)
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Rooms</h1>
        <p class="text-sm text-gray-500 mt-1">
          Lecture halls, labs, and venue capacities
          <span v-if="!loading" class="ml-1 text-gray-400">({{ rooms.length }})</span>
        </p>
      </div>
      <button class="btn-primary flex items-center gap-2" @click="openCreate">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
        </svg>
        Add Room
      </button>
    </div>

    <!-- Create / Edit form -->
    <div v-if="showForm" class="card space-y-4 border-blue-100 bg-blue-50/40">
      <div class="flex items-center justify-between">
        <h2 class="font-semibold text-gray-900">{{ editTarget ? "Edit Room" : "New Room" }}</h2>
        <button @click="showForm = false" class="text-gray-400 hover:text-gray-600">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
      <div class="grid md:grid-cols-3 gap-3">
        <div class="md:col-span-2">
          <label class="label">Room Name *</label>
          <input v-model="form.name" class="input" placeholder="Lecture Hall A" />
        </div>
        <div>
          <label class="label">Code *</label>
          <input v-model="form.code" class="input" placeholder="LHA" />
        </div>
        <div>
          <label class="label">Type</label>
          <select v-model="form.room_type" class="input">
            <option value="lecture">Lecture Hall</option>
            <option value="lab">Computer Lab</option>
            <option value="seminar">Seminar Room</option>
            <option value="auditorium">Auditorium</option>
          </select>
        </div>
        <div>
          <label class="label">Capacity</label>
          <input v-model.number="form.capacity" type="number" min="1" class="input" placeholder="40" />
        </div>
        <div>
          <label class="label">Floor</label>
          <input v-model.number="form.floor" type="number" min="0" class="input" placeholder="1" />
        </div>
        <div class="md:col-span-3">
          <label class="label">Building</label>
          <input v-model="form.building" class="input" placeholder="Main Block" />
        </div>
      </div>
      <div class="flex gap-2">
        <button class="btn-primary" :disabled="saving" @click="save">
          {{ saving ? "Saving…" : editTarget ? "Update" : "Create" }}
        </button>
        <button class="btn-secondary" @click="showForm = false">Cancel</button>
      </div>
    </div>

    <!-- Delete confirmation -->
    <div v-if="deleteTarget" class="card border-red-200 bg-red-50 space-y-3">
      <p class="text-sm text-red-800 font-medium">Delete <strong>{{ deleteTarget.name }}</strong>?</p>
      <p class="text-xs text-red-600">This may fail if the room is used in existing timetables.</p>
      <div class="flex gap-2">
        <button class="btn-danger text-sm" @click="confirmDelete">Yes, delete</button>
        <button class="btn-secondary text-sm" @click="deleteTarget = null">Cancel</button>
      </div>
    </div>

    <!-- Filters -->
    <div class="flex flex-wrap gap-3">
      <input v-model="search" class="input flex-1 min-w-[180px] max-w-xs" placeholder="Search rooms…" />
      <select v-model="typeFilter" class="input w-auto">
        <option value="">All types</option>
        <option value="lecture">Lecture</option>
        <option value="lab">Lab</option>
        <option value="seminar">Seminar</option>
        <option value="auditorium">Auditorium</option>
      </select>
    </div>

    <!-- Loading skeleton -->
    <div v-if="loading" class="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <div v-for="i in 6" :key="i" class="card animate-pulse space-y-3">
        <div class="flex gap-3">
          <div class="w-10 h-10 bg-gray-200 rounded-lg flex-shrink-0"></div>
          <div class="flex-1 space-y-2">
            <div class="h-4 bg-gray-200 rounded w-3/4"></div>
            <div class="h-3 bg-gray-200 rounded w-1/2"></div>
          </div>
        </div>
        <div class="h-3 bg-gray-200 rounded w-1/3"></div>
      </div>
    </div>

    <!-- Empty state -->
    <div v-else-if="!rooms.length" class="card text-center py-14">
      <div class="w-14 h-14 mx-auto bg-blue-50 rounded-2xl flex items-center justify-center mb-3">
        <svg class="w-7 h-7 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
        </svg>
      </div>
      <h3 class="font-semibold text-gray-900 mb-1">No rooms yet</h3>
      <p class="text-sm text-gray-500 mb-5">Add lecture halls and labs to use in timetable generation.</p>
      <button class="btn-primary" @click="openCreate">Add Room</button>
    </div>

    <!-- No filter results -->
    <div v-else-if="!filtered.length" class="card text-center py-8 text-sm text-gray-500">
      No rooms match your filters.
      <button class="text-blue-600 hover:underline ml-1" @click="search = ''; typeFilter = ''">Clear</button>
    </div>

    <!-- Room cards -->
    <div v-else class="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <div
        v-for="r in filtered"
        :key="r.id"
        class="card hover:shadow-md transition-shadow"
        :class="deleteTarget?.id === r.id ? 'border-red-300' : ''"
      >
        <div class="flex items-start justify-between gap-2 mb-3">
          <div class="flex items-center gap-3 min-w-0">
            <div class="w-10 h-10 rounded-lg flex-shrink-0 flex items-center justify-center"
              :class="(TYPE_COLORS[r.room_type] || TYPE_COLORS.lecture).bg">
              <svg class="w-5 h-5" :class="(TYPE_COLORS[r.room_type] || TYPE_COLORS.lecture).text"
                fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.75">
                <path stroke-linecap="round" stroke-linejoin="round"
                  :d="r.room_type === 'lab' ? 'M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18' : 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5'" />
              </svg>
            </div>
            <div class="min-w-0">
              <p class="font-semibold text-gray-900 truncate">{{ r.name }}</p>
              <p class="text-xs text-gray-400">{{ r.code }}</p>
            </div>
          </div>
          <div class="flex gap-1 flex-shrink-0">
            <button class="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg" @click="openEdit(r)">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
            </button>
            <button class="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg" @click="deleteTarget = r; showForm = false">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>
        </div>

        <div class="flex items-center gap-2 flex-wrap">
          <span class="px-2 py-0.5 rounded text-xs font-medium" :class="[(TYPE_COLORS[r.room_type] || TYPE_COLORS.lecture).bg, (TYPE_COLORS[r.room_type] || TYPE_COLORS.lecture).text]">
            {{ (TYPE_COLORS[r.room_type] || TYPE_COLORS.lecture).label }}
          </span>
          <span class="text-xs text-gray-500">Cap. {{ r.capacity }}</span>
          <span v-if="r.building" class="text-xs text-gray-400">· {{ r.building }}<span v-if="r.floor">, Fl. {{ r.floor }}</span></span>
        </div>
      </div>
    </div>
  </div>
</template>
