<script setup>
import { onMounted, ref } from "vue"
import { resourcesApi, getErrorMessage } from "@/api/client"
import { useToast } from "vue-toastification"

const toast = useToast()
const loading = ref(true)
const saving = ref(false)
const universities = ref([])
const showForm = ref(false)
const editTarget = ref(null)
const deleteTarget = ref(null)

const blank = () => ({ name: "", code: "", address: "", website: "" })
const form = ref(blank())

async function load() {
  loading.value = true
  try {
    const { data } = await resourcesApi.universities()
    universities.value = data.data || []
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to load universities."))
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

function openEdit(u) {
  editTarget.value = u
  form.value = { name: u.name, code: u.code, address: u.address || "", website: u.website || "" }
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
      await resourcesApi.updateUniversity(editTarget.value.id, form.value)
      toast.success("University updated.")
    } else {
      await resourcesApi.createUniversity(form.value)
      toast.success("University created.")
    }
    showForm.value = false
    editTarget.value = null
    await load()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to save university."))
  } finally {
    saving.value = false
  }
}

async function confirmDelete() {
  if (!deleteTarget.value) return
  try {
    await resourcesApi.deleteUniversity(deleteTarget.value.id)
    toast.success("University removed.")
    deleteTarget.value = null
    await load()
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to remove university."))
  }
}

function initials(name) {
  return name
    .split(" ")
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase())
    .join("")
}

const BG_PALETTE = ["bg-blue-500", "bg-indigo-500", "bg-purple-500", "bg-teal-500", "bg-rose-500", "bg-orange-500"]
function avatarBg(idx) {
  return BG_PALETTE[idx % BG_PALETTE.length]
}

onMounted(load)
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">Universities</h1>
        <p class="text-sm text-gray-500 mt-1">
          Institutions registered on the platform
          <span v-if="!loading" class="ml-1 text-gray-400">({{ universities.length }})</span>
        </p>
      </div>
      <button class="btn-primary flex items-center gap-2" @click="openCreate">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
        </svg>
        Add University
      </button>
    </div>

    <!-- Create / Edit form -->
    <div v-if="showForm" class="card space-y-4 border-blue-100 bg-blue-50/40">
      <div class="flex items-center justify-between">
        <h2 class="font-semibold text-gray-900">{{ editTarget ? "Edit University" : "New University" }}</h2>
        <button @click="showForm = false" class="text-gray-400 hover:text-gray-600">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
      <div class="grid md:grid-cols-2 gap-3">
        <div>
          <label class="label">University Name *</label>
          <input v-model="form.name" class="input" placeholder="University of Nairobi" />
        </div>
        <div>
          <label class="label">Short Code *</label>
          <input v-model="form.code" class="input" placeholder="UON" style="text-transform: uppercase" />
        </div>
        <div>
          <label class="label">Address</label>
          <input v-model="form.address" class="input" placeholder="P.O. Box 30197, Nairobi" />
        </div>
        <div>
          <label class="label">Website</label>
          <input v-model="form.website" class="input" placeholder="https://www.uonbi.ac.ke" type="url" />
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
      <p class="text-sm text-red-800 font-medium">Remove <strong>{{ deleteTarget.name }}</strong>?</p>
      <p class="text-xs text-red-600">This will fail if departments or users are linked to this university.</p>
      <div class="flex gap-2">
        <button class="btn-danger text-sm" @click="confirmDelete">Yes, remove</button>
        <button class="btn-secondary text-sm" @click="deleteTarget = null">Cancel</button>
      </div>
    </div>

    <!-- Loading skeleton -->
    <div v-if="loading" class="grid sm:grid-cols-2 gap-4">
      <div v-for="i in 4" :key="i" class="card animate-pulse flex items-center gap-4">
        <div class="w-14 h-14 bg-gray-200 rounded-2xl flex-shrink-0"></div>
        <div class="flex-1 space-y-2">
          <div class="h-4 bg-gray-200 rounded w-3/4"></div>
          <div class="h-3 bg-gray-200 rounded w-1/2"></div>
          <div class="h-3 bg-gray-200 rounded w-1/3"></div>
        </div>
      </div>
    </div>

    <!-- Empty state -->
    <div v-else-if="!universities.length" class="card text-center py-14">
      <div class="w-14 h-14 mx-auto bg-blue-50 rounded-2xl flex items-center justify-center mb-3">
        <svg class="w-7 h-7 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 14l9-5-9-5-9 5 9 5zm0 0l6.16-3.422a12.083 12.083 0 01.665 6.479A11.952 11.952 0 0012 20.055a11.952 11.952 0 00-6.824-2.998 12.078 12.078 0 01.665-6.479L12 14zm-4 6v-7.5l4-2.222" />
        </svg>
      </div>
      <h3 class="font-semibold text-gray-900 mb-1">No universities yet</h3>
      <p class="text-sm text-gray-500 mb-5">Add your first institution to start configuring departments and programs.</p>
      <button class="btn-primary" @click="openCreate">Add University</button>
    </div>

    <!-- University cards -->
    <div v-else class="grid sm:grid-cols-2 gap-4">
      <div
        v-for="(u, idx) in universities"
        :key="u.id"
        class="card hover:shadow-md transition-shadow"
        :class="deleteTarget?.id === u.id ? 'border-red-300' : ''"
      >
        <div class="flex items-start gap-4">
          <div class="w-14 h-14 rounded-2xl flex-shrink-0 flex items-center justify-center text-white font-bold text-lg"
            :class="avatarBg(idx)">
            {{ initials(u.name) }}
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex items-start justify-between gap-2">
              <div class="min-w-0">
                <h3 class="font-semibold text-gray-900 truncate">{{ u.name }}</h3>
                <span class="inline-block mt-0.5 px-2 py-0.5 rounded-md bg-gray-100 text-gray-700 text-xs font-semibold">{{ u.code }}</span>
              </div>
              <div class="flex gap-1 flex-shrink-0">
                <button class="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg" @click="openEdit(u)">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                </button>
                <button class="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg" @click="deleteTarget = u; showForm = false">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            </div>

            <div class="mt-3 space-y-1.5 text-sm">
              <div v-if="u.address" class="flex items-center gap-2 text-gray-500">
                <svg class="w-3.5 h-3.5 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                  <path stroke-linecap="round" stroke-linejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                <span class="truncate">{{ u.address }}</span>
              </div>
              <div v-if="u.website" class="flex items-center gap-2">
                <svg class="w-3.5 h-3.5 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9" />
                </svg>
                <a :href="u.website" target="_blank" class="text-blue-600 hover:underline truncate">{{ u.website }}</a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
