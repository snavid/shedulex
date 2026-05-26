<script setup>
import { ref, computed, onMounted } from "vue"
import { useAuthStore } from "@/stores/auth"
import { resourcesApi, getErrorMessage } from "@/api/client"
import { useToast } from "vue-toastification"

const auth = useAuthStore()
const toast = useToast()

const loading = ref(true)
const saving = ref(false)
const university = ref(null)
const departments = ref([])
const editing = ref(false)

const form = ref({ name: "", code: "", address: "", website: "" })

const isAdmin = computed(() => auth.userRole === "admin")

async function load() {
  loading.value = true
  try {
    const [uniRes, deptRes] = await Promise.all([
      resourcesApi.universities(),
      resourcesApi.departments(),
    ])
    const unis = uniRes.data.data || []
    const uniId = auth.user?.university_id
    university.value = uniId ? (unis.find(u => u.id === uniId) || null) : (unis[0] || null)
    departments.value = deptRes.data.data || []
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to load university details."))
  } finally {
    loading.value = false
  }
}

function openEdit() {
  if (!university.value) return
  form.value = {
    name: university.value.name,
    code: university.value.code,
    address: university.value.address || "",
    website: university.value.website || "",
  }
  editing.value = true
}

async function save() {
  if (!form.value.name || !form.value.code) {
    toast.error("Name and code are required.")
    return
  }
  saving.value = true
  try {
    const { data } = await resourcesApi.updateUniversity(university.value.id, form.value)
    university.value = data.data
    editing.value = false
    toast.success("University details updated.")
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to update university."))
  } finally {
    saving.value = false
  }
}

function initials(name) {
  return (name || "").split(" ").slice(0, 2).map(w => w[0]?.toUpperCase()).join("")
}

onMounted(load)
</script>

<template>
  <div class="space-y-6 max-w-3xl">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-900">My University</h1>
        <p class="text-sm text-gray-500 mt-1">Your institution's profile and details</p>
      </div>
      <button v-if="isAdmin && university && !editing" class="btn-primary flex items-center gap-2" @click="openEdit">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
        </svg>
        Edit Details
      </button>
    </div>

    <!-- Loading skeleton -->
    <div v-if="loading" class="card animate-pulse">
      <div class="flex items-center gap-5 mb-6">
        <div class="w-20 h-20 bg-gray-200 rounded-2xl flex-shrink-0"></div>
        <div class="flex-1 space-y-3">
          <div class="h-6 bg-gray-200 rounded w-2/3"></div>
          <div class="h-4 bg-gray-200 rounded w-1/3"></div>
        </div>
      </div>
      <div class="space-y-3">
        <div class="h-4 bg-gray-200 rounded w-1/2"></div>
        <div class="h-4 bg-gray-200 rounded w-1/3"></div>
      </div>
    </div>

    <!-- No university found -->
    <div v-else-if="!university" class="card text-center py-14">
      <div class="w-14 h-14 mx-auto bg-amber-50 rounded-2xl flex items-center justify-center mb-3">
        <svg class="w-7 h-7 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
      </div>
      <h3 class="font-semibold text-gray-900 mb-1">No university linked</h3>
      <p class="text-sm text-gray-500">Your account is not associated with a university. Contact your administrator.</p>
    </div>

    <!-- Edit form (admin only) -->
    <div v-else-if="editing" class="card space-y-4 border-blue-100 bg-blue-50/40">
      <div class="flex items-center justify-between">
        <h2 class="font-semibold text-gray-900">Edit University Details</h2>
        <button @click="editing = false" class="text-gray-400 hover:text-gray-600">
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
          <input v-model="form.code" class="input" placeholder="UON" />
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
          {{ saving ? "Saving…" : "Save Changes" }}
        </button>
        <button class="btn-secondary" @click="editing = false">Cancel</button>
      </div>
    </div>

    <!-- University profile card -->
    <div v-else class="space-y-5">
      <div class="card">
        <div class="flex items-start gap-5">
          <div class="w-20 h-20 rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white font-bold text-2xl flex-shrink-0">
            {{ initials(university.name) }}
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex items-start justify-between gap-2">
              <div>
                <h2 class="text-xl font-bold text-gray-900 leading-tight">{{ university.name }}</h2>
                <span class="inline-block mt-1 px-2.5 py-0.5 rounded-lg bg-blue-100 text-blue-700 text-sm font-bold">{{ university.code }}</span>
              </div>
              <span
                :class="university.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'"
                class="text-xs font-semibold px-2 py-0.5 rounded-full flex-shrink-0"
              >
                {{ university.is_active ? "Active" : "Inactive" }}
              </span>
            </div>

            <div class="mt-4 space-y-2">
              <div v-if="university.address" class="flex items-center gap-2 text-sm text-gray-600">
                <svg class="w-4 h-4 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                  <path stroke-linecap="round" stroke-linejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                <span>{{ university.address }}</span>
              </div>
              <div v-if="university.website" class="flex items-center gap-2 text-sm">
                <svg class="w-4 h-4 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9" />
                </svg>
                <a :href="university.website" target="_blank" class="text-blue-600 hover:underline">{{ university.website }}</a>
              </div>
              <div v-if="!university.address && !university.website && isAdmin" class="text-sm text-gray-400 italic">
                No address or website set. <button class="text-blue-500 hover:underline" @click="openEdit">Add details</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Stats row -->
      <div class="grid grid-cols-2 sm:grid-cols-3 gap-4">
        <div class="card text-center py-5">
          <p class="text-3xl font-bold text-blue-600">{{ departments.length }}</p>
          <p class="text-sm text-gray-500 mt-1">Departments</p>
        </div>
        <div class="card text-center py-5">
          <p class="text-3xl font-bold text-indigo-600">{{ university.id?.slice(0, 4).toUpperCase() }}</p>
          <p class="text-sm text-gray-500 mt-1">Institution ID</p>
        </div>
        <div class="card text-center py-5 col-span-2 sm:col-span-1">
          <p class="text-sm font-semibold text-gray-700 mb-1">Your Role</p>
          <span class="inline-block px-3 py-1 rounded-full text-sm font-bold bg-blue-50 text-blue-700 capitalize">
            {{ (auth.userRole || "").replace(/_/g, " ") }}
          </span>
        </div>
      </div>

      <!-- Departments list -->
      <div v-if="departments.length" class="card">
        <h3 class="font-semibold text-gray-900 mb-4">Departments</h3>
        <div class="grid sm:grid-cols-2 gap-2">
          <div
            v-for="dept in departments"
            :key="dept.id"
            class="flex items-center gap-3 p-3 rounded-xl bg-gray-50 hover:bg-gray-100 transition-colors"
          >
            <div class="w-8 h-8 rounded-lg bg-blue-100 flex items-center justify-center flex-shrink-0">
              <svg class="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="1.75">
                <path stroke-linecap="round" stroke-linejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-2 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
              </svg>
            </div>
            <div class="min-w-0">
              <p class="text-sm font-medium text-gray-900 truncate">{{ dept.name }}</p>
              <p v-if="dept.code" class="text-xs text-gray-500">{{ dept.code }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
