<script setup>
import { onMounted, ref, computed } from "vue"
import { getErrorMessage, resourcesApi } from "@/api/client"
import { useToast } from "vue-toastification"

const toast = useToast()
const loading = ref(true)
const saving = ref(false)
const buildings = ref([])
const showForm = ref(false)
const editTarget = ref(null)
const deleteTarget = ref(null)
const search = ref("")
const error = ref("")

const blank = () => ({ name: "", code: "", address: "" })
const form = ref(blank())

const filtered = computed(() => {
  const q = search.value.toLowerCase()
  return q
    ? buildings.value.filter(
        (b) =>
          b.name.toLowerCase().includes(q) ||
          (b.code || "").toLowerCase().includes(q) ||
          (b.address || "").toLowerCase().includes(q),
      )
    : buildings.value
})

async function load() {
  loading.value = true
  error.value = ""
  try {
    const { data } = await resourcesApi.buildings()
    buildings.value = data.data || []
  } catch (e) {
    error.value = getErrorMessage(e, "Failed to load buildings.")
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editTarget.value = null
  form.value = blank()
  showForm.value = true
}

function openEdit(b) {
  editTarget.value = b
  form.value = { name: b.name, code: b.code || "", address: b.address || "" }
  showForm.value = true
  deleteTarget.value = null
}

async function save() {
  if (!form.value.name) {
    toast.error("Name is required.")
    return
  }
  saving.value = true
  try {
    if (editTarget.value) {
      await resourcesApi.updateBuilding(editTarget.value.id, form.value)
      toast.success("Building updated.")
    } else {
      await resourcesApi.createBuilding(form.value)
      toast.success("Building created.")
    }
    showForm.value = false
    editTarget.value = null
    await load()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to save building."))
  } finally {
    saving.value = false
  }
}

async function confirmDelete() {
  if (!deleteTarget.value) return
  try {
    await resourcesApi.deleteBuilding(deleteTarget.value.id)
    toast.success("Building deleted.")
    deleteTarget.value = null
    await load()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to delete building."))
  }
}

onMounted(load)
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Buildings</h1>
        <p class="text-sm text-gray-500 mt-1">
          Manage campus buildings / blocks that contain rooms
          <span v-if="!loading" class="ml-1 text-gray-400">({{ buildings.length }})</span>
        </p>
      </div>
      <button class="btn-primary flex items-center gap-2" @click="openCreate">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
        </svg>
        Add Building
      </button>
    </div>

    <!-- Create / Edit form -->
    <div v-if="showForm" class="card space-y-4 border-blue-100 bg-blue-50/40">
      <div class="flex items-center justify-between">
        <h2 class="font-semibold text-gray-900">{{ editTarget ? "Edit Building" : "New Building" }}</h2>
        <button @click="showForm = false" class="text-gray-400 hover:text-gray-600">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
      <div class="grid md:grid-cols-2 gap-3">
        <div>
          <label class="label">Name *</label>
          <input v-model="form.name" class="input" placeholder="ICT Building" />
        </div>
        <div>
          <label class="label">Code</label>
          <input v-model="form.code" class="input" placeholder="ICT" />
        </div>
        <div class="md:col-span-2">
          <label class="label">Address</label>
          <input v-model="form.address" class="input" placeholder="Block C, Main Campus" />
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
      <p class="text-xs text-red-600">Rooms in this building will keep their legacy building name but lose the building link.</p>
      <div class="flex gap-2">
        <button class="btn-danger text-sm" @click="confirmDelete">Yes, delete</button>
        <button class="btn-secondary text-sm" @click="deleteTarget = null">Cancel</button>
      </div>
    </div>

    <!-- Search -->
    <div class="flex gap-3">
      <input v-model="search" class="input flex-1 max-w-sm" placeholder="Search buildings…" />
    </div>

    <!-- Error -->
    <div v-if="error" class="card border-red-200 bg-red-50 text-red-700 text-sm">{{ error }}</div>

    <!-- Loading skeleton -->
    <div v-if="loading" class="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <div v-for="i in 6" :key="i" class="card animate-pulse space-y-3">
        <div class="h-4 bg-gray-200 rounded w-2/3"></div>
        <div class="h-3 bg-gray-200 rounded w-1/3"></div>
      </div>
    </div>

    <!-- Empty state -->
    <div v-else-if="!buildings.length" class="card text-center py-14">
      <div class="w-14 h-14 mx-auto bg-indigo-50 rounded-2xl flex items-center justify-center mb-3">
        <svg class="w-7 h-7 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M3 21h18M5 21V7l8-4v18M13 21V11l6 3v7M9 9h.01M9 13h.01M9 17h.01" />
        </svg>
      </div>
      <h3 class="font-semibold text-gray-900 mb-1">No buildings yet</h3>
      <p class="text-sm text-gray-500 mb-5">Add your first building, then assign rooms to it.</p>
      <button class="btn-primary" @click="openCreate">Add Building</button>
    </div>

    <!-- No filter results -->
    <div v-else-if="!filtered.length" class="card text-center py-8 text-sm text-gray-500">
      No buildings match "<strong>{{ search }}</strong>".
      <button class="text-blue-600 hover:underline ml-1" @click="search = ''">Clear</button>
    </div>

    <!-- Building cards -->
    <div v-else class="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <div
        v-for="b in filtered"
        :key="b.id"
        class="card hover:shadow-md transition-shadow space-y-3"
        :class="deleteTarget?.id === b.id ? 'border-red-300' : ''"
      >
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0">
            <h3 class="font-semibold text-gray-900 truncate">{{ b.name }}</h3>
            <span v-if="b.code" class="inline-block mt-1 px-2 py-0.5 rounded-md bg-blue-100 text-blue-700 text-xs font-semibold">{{ b.code }}</span>
          </div>
          <div class="flex gap-1 flex-shrink-0">
            <button
              class="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
              title="Edit"
              @click="openEdit(b)"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
            </button>
            <button
              class="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
              title="Delete"
              @click="deleteTarget = b; showForm = false"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>
        </div>
        <div class="text-sm text-gray-600 space-y-1">
          <div class="flex items-center gap-2">
            <svg class="w-3.5 h-3.5 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
              <path stroke-linecap="round" stroke-linejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <span class="text-gray-500">{{ b.address || "No address set" }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
