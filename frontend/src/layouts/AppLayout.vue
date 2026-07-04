<script setup>
import { ref, computed, h, watch, reactive } from "vue"
import { RouterView, useRouter, RouterLink } from "vue-router"
import { useAuthStore } from "@/stores/auth"
import { useAcademicYearStore } from "@/stores/academicYear"
import { useToast } from "vue-toastification"
import { getErrorMessage, resourcesApi } from "@/api/client"

const auth = useAuthStore()
const yearStore = useAcademicYearStore()
const router = useRouter()
const toast = useToast()

const sidebarOpen = ref(true)
const mobileOpen = ref(false)

// ── Year dropdown ─────────────────────────────────────────────────────────────
const yearDropdownOpen = ref(false)

function openYearDropdown() { yearDropdownOpen.value = true }

function selectYear(year) {
  yearStore.setCurrentYear(year.id)
  yearDropdownOpen.value = false
}

// ── Add / Edit Year modal ─────────────────────────────────────────────────────
const showYearModal = ref(false)
const yearModalSaving = ref(false)
const editingYear = ref(null)  // null = create mode, object = edit mode
const yearForm = reactive({
  name: "",
  sem1_start: "",
  sem1_end: "",
  sem2_start: "",
  sem2_end: "",
  is_current: false,
})

function openAddYear() {
  yearDropdownOpen.value = false
  editingYear.value = null
  Object.assign(yearForm, { name: "", sem1_start: "", sem1_end: "", sem2_start: "", sem2_end: "", is_current: false })
  showYearModal.value = true
}

function openEditYear(year) {
  yearDropdownOpen.value = false
  editingYear.value = year
  Object.assign(yearForm, {
    name: year.name,
    sem1_start: year.sem1_start || "",
    sem1_end: year.sem1_end || "",
    sem2_start: year.sem2_start || "",
    sem2_end: year.sem2_end || "",
    is_current: year.is_current || false,
  })
  showYearModal.value = true
}

async function deleteYear(year) {
  yearDropdownOpen.value = false
  if (!window.confirm(`Delete academic year "${year.name}"? This cannot be undone.`)) return
  try {
    await yearStore.deleteYear(year.id)
    toast.success(`Academic year ${year.name} deleted.`)
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to delete academic year."))
  }
}

async function submitAddYear() {
  if (!yearForm.name) { toast.error("Year name is required."); return }
  yearModalSaving.value = true
  try {
    if (editingYear.value) {
      await yearStore.updateYear(editingYear.value.id, { ...yearForm })
      toast.success(`Academic year ${yearForm.name} updated.`)
    } else {
      const universityId = yearStore.universityId || auth.user?.university_id
      if (!universityId) { toast.error("No university found. Make sure a university exists first."); return }
      const created = await yearStore.createYear({ ...yearForm, university_id: universityId })
      yearStore.setCurrentYear(created.id)
      toast.success(`Academic year ${created.name} created.`)
    }
    showYearModal.value = false
  } catch (e) {
    toast.error(getErrorMessage(e, "Failed to save academic year."))
  } finally {
    yearModalSaving.value = false
  }
}

// ── Auth watch ────────────────────────────────────────────────────────────────
watch(
  () => auth.user,
  async (user) => {
    if (!user) return
    let uniId = user.university_id
    if (!uniId) {
      // university_id not on JWT/user object — fetch from API
      try {
        const { data } = await resourcesApi.universities()
        uniId = data.data?.[0]?.id || null
      } catch { /* ignore */ }
    }
    if (uniId) yearStore.loadYears(uniId)
  },
  { immediate: true },
)

// ── Heroicon SVG paths (outline) ──────────────────────────────────────────────
const ICONS = {
  dashboard:    "M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6",
  timetable:    "M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z",
  generate:     "M13 10V3L4 14h7v7l9-11h-7z",
  ai:           "M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z",
  calendar:     "M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z",
  analytics:    "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z",
  notifications:"M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9",
  university:   "M12 14l9-5-9-5-9 5 9 5z M12 14l6.16-3.422a12.083 12.083 0 01.665 6.479A11.952 11.952 0 0012 20.055a11.952 11.952 0 00-6.824-2.998 12.078 12.078 0 01.665-6.479L12 14z",
  programs:     "M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253",
  groups:       "M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z",
  departments:  "M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-2 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4",
  rooms:        "M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6",
  lecturers:    "M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z",
  courses:      "M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253",
  constraints:  "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z",
  timeslots:    "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z",
  assignments:  "M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01",
  users:        "M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z",
  audit:        "M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z",
  menu:         "M4 6h16M4 12h16M4 18h16",
  logout:       "M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1",
  chevronLeft:  "M15 19l-7-7 7-7",
  chevronDown:  "M19 9l-7 7-7-7",
  plus:         "M12 4v16m8-8H4",
  check:        "M5 13l4 4L19 7",
  x:            "M6 18L18 6M6 6l12 12",
}

function Icon({ name, class: cls = "w-5 h-5" }) {
  return h("svg", {
    class: cls,
    fill: "none",
    stroke: "currentColor",
    viewBox: "0 0 24 24",
    "stroke-width": "1.75",
    "stroke-linecap": "round",
    "stroke-linejoin": "round",
  }, [h("path", { d: ICONS[name] || "" })])
}

const navItems = computed(() => {
  const base = [
    { to: "/dashboard",              label: "Dashboard",      icon: "dashboard" },
    { to: "/timetable",              label: "Timetables",     icon: "timetable" },
   // { to: "/ai-assistant",           label: "AI Assistant",   icon: "ai" },
    { to: "/calendar",               label: "Calendar",       icon: "calendar" },
    { to: "/analytics",              label: "Analytics",      icon: "analytics" },
    { to: "/notifications",          label: "Notifications",  icon: "notifications" },
    { section: "Academic Structure" },
    { to: "/resources/universities", label: "University",     icon: "university" },
    { to: "/resources/programs",     label: "Programs",       icon: "programs" },
    { to: "/resources/student-groups", label: "Student Groups", icon: "groups" },
    { to: "/resources/departments",  label: "Departments",    icon: "departments" },
    { section: "Resources" },
    { to: "/resources/rooms",        label: "Rooms",          icon: "rooms" },
    { to: "/resources/lecturers",    label: "Lecturers",      icon: "lecturers" },
    { to: "/resources/courses",      label: "Courses",        icon: "courses" },
    { to: "/resources/assignments",  label: "Assignments",    icon: "assignments", roles: ["admin", "timetable_officer", "hod"] },
    { to: "/resources/constraints",  label: "Constraints",    icon: "constraints" },
    { to: "/resources/time-slots",   label: "Time Slots",     icon: "timeslots", roles: ["admin", "timetable_officer"] },
  ]
  if (auth.isTimetableOfficer) base.splice(2, 0, { to: "/generate", label: "Generate", icon: "generate" })
  if (auth.isAdmin) base.push(
    { section: "Administration" },
    { to: "/admin/users",  label: "Users",       icon: "users" },
    { to: "/admin/comments", label: "Comments",  icon: "notifications" },
    { to: "/admin/audit",  label: "Audit Logs",  icon: "audit" },
  )
  else if (auth.userRole === "timetable_officer") base.push(
    { section: "Administration" },
    { to: "/admin/comments", label: "Comments", icon: "notifications" },
  )
  const userRole = auth.userRole
  return base.filter((item) => !item.roles || item.roles.includes(userRole))
})

const userInitials = computed(() => {
  const f = auth.user?.first_name?.[0] || ""
  const l = auth.user?.last_name?.[0] || ""
  return (f + l).toUpperCase() || "U"
})

const roleBadge = computed(() => {
  const r = auth.userRole || ""
  return r.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
})

async function handleLogout() {
  await auth.logout()
  router.push("/login")
}
</script>

<template>
  <div class="flex h-screen overflow-hidden bg-gray-50">

    <!-- Mobile overlay -->
    <div v-if="mobileOpen" class="fixed inset-0 z-40 bg-black/40 lg:hidden" @click="mobileOpen = false" />

    <!-- ── Sidebar ──────────────────────────────────────────────────────── -->
    <aside
      :class="[
        'fixed inset-y-0 left-0 z-50 flex flex-col bg-white border-r border-gray-200 transition-all duration-300 ease-in-out',
        'lg:relative lg:z-auto lg:translate-x-0',
        mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0',
        sidebarOpen ? 'w-64' : 'w-[72px]',
      ]"
    >
      <!-- Logo -->
      <div class="flex items-center h-16 px-4 border-b border-gray-200 flex-shrink-0">
        <div class="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center flex-shrink-0">
          <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
        </div>
        <div v-if="sidebarOpen" class="ml-3 min-w-0">
          <p class="text-sm font-bold text-gray-900 truncate">Shedulex</p>
          <p class="text-xs text-gray-400 truncate">Academic Timetabling</p>
        </div>
        <button
          v-if="sidebarOpen"
          @click="sidebarOpen = false"
          class="ml-auto p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600 lg:flex hidden"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="ICONS.chevronLeft" />
          </svg>
        </button>
      </div>

      <!-- Navigation -->
      <nav class="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
        <template v-for="item in navItems" :key="item.to || item.section">
          <p v-if="item.section" :class="['px-2 pt-5 pb-1 text-xs font-semibold text-gray-400 uppercase tracking-wider select-none', !sidebarOpen && 'text-center']">
            <span v-if="sidebarOpen">{{ item.section }}</span>
            <span v-else class="block w-full border-t border-gray-200 mt-1"></span>
          </p>
          <RouterLink v-else :to="item.to" v-slot="{ isActive }" custom>
            <a
              :href="item.to"
              @click.prevent="router.push(item.to)"
              :title="!sidebarOpen ? item.label : ''"
              :class="[
                'flex items-center gap-3 px-2.5 py-2 rounded-lg text-sm font-medium transition-colors cursor-pointer',
                isActive ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900',
                !sidebarOpen && 'justify-center',
              ]"
            >
              <component :is="Icon" :name="item.icon" class="w-5 h-5 flex-shrink-0" />
              <span v-if="sidebarOpen" class="truncate">{{ item.label }}</span>
            </a>
          </RouterLink>
        </template>
      </nav>

      <!-- User section -->
      <div class="p-3 border-t border-gray-200 flex-shrink-0">
        <RouterLink to="/profile">
          <div :class="['flex items-center gap-3 px-2 py-2 rounded-lg hover:bg-gray-100 transition-colors cursor-pointer', !sidebarOpen && 'justify-center']">
            <div class="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
              {{ userInitials }}
            </div>
            <div v-if="sidebarOpen" class="min-w-0 flex-1">
              <p class="text-sm font-medium text-gray-900 truncate">{{ auth.user?.first_name }} {{ auth.user?.last_name }}</p>
              <p class="text-xs text-gray-400 truncate">{{ roleBadge }}</p>
            </div>
          </div>
        </RouterLink>
        <button
          @click="handleLogout"
          :title="!sidebarOpen ? 'Sign Out' : ''"
          :class="['mt-1 w-full flex items-center gap-3 px-2 py-2 rounded-lg text-red-500 hover:bg-red-50 hover:text-red-700 text-sm font-medium transition-colors', !sidebarOpen && 'justify-center']"
        >
          <component :is="Icon" name="logout" class="w-5 h-5 flex-shrink-0" />
          <span v-if="sidebarOpen">Sign Out</span>
        </button>
      </div>
    </aside>

    <!-- ── Main content ────────────────────────────────────────────────── -->
    <div class="flex-1 flex flex-col overflow-hidden min-w-0">

      <!-- ── Top bar ─────────────────────────────────────────────────── -->
      <header class="h-16 bg-white border-b border-gray-200 px-4 flex items-center justify-between flex-shrink-0 gap-3">

        <div class="flex items-center gap-3">
          <!-- Mobile hamburger -->
          <button @click="mobileOpen = !mobileOpen" class="p-2 rounded-lg hover:bg-gray-100 text-gray-500 lg:hidden">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="ICONS.menu" />
            </svg>
          </button>
          <!-- Desktop expand when collapsed -->
          <button v-if="!sidebarOpen" @click="sidebarOpen = true" class="p-2 rounded-lg hover:bg-gray-100 text-gray-500 hidden lg:flex">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="ICONS.menu" />
            </svg>
          </button>
        </div>

        <!-- ── Year + Semester workspace controls ── -->
        <div class="flex items-center gap-2 flex-1 justify-center sm:justify-end sm:flex-none">

          <!-- Academic Year dropdown -->
          <div class="relative">
            <button
              @click="openYearDropdown"
              class="group flex items-center gap-2 h-9 pl-3 pr-2.5 rounded-xl border border-gray-200 bg-white hover:border-blue-300 hover:bg-blue-50/50 transition-all text-sm font-medium text-gray-700 hover:text-blue-700 shadow-sm"
            >
              <svg class="w-4 h-4 text-blue-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              <span class="hidden xs:inline">{{ yearStore.currentYear?.name || "Select Year" }}</span>
              <span class="inline xs:hidden text-xs">{{ yearStore.currentYear?.name?.split("-")[0] || "—" }}</span>
              <svg class="w-3.5 h-3.5 text-gray-400 group-hover:text-blue-500 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" :d="ICONS.chevronDown" />
              </svg>
            </button>

            <!-- Year dropdown panel -->
            <Transition
              enter-active-class="transition ease-out duration-150"
              enter-from-class="opacity-0 translate-y-1 scale-95"
              enter-to-class="opacity-100 translate-y-0 scale-100"
              leave-active-class="transition ease-in duration-100"
              leave-from-class="opacity-100 translate-y-0 scale-100"
              leave-to-class="opacity-0 translate-y-1 scale-95"
            >
              <div
                v-if="yearDropdownOpen"
                class="absolute left-0 top-full mt-2 w-64 bg-white rounded-2xl shadow-xl border border-gray-100 py-2 z-50 overflow-hidden"
              >
                <div class="px-4 pt-1 pb-2 border-b border-gray-100">
                  <p class="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Academic Years</p>
                </div>

                <div class="py-1 max-h-56 overflow-y-auto">
                  <div
                    v-for="year in yearStore.years"
                    :key="year.id"
                    :class="[
                      'flex items-center gap-1 px-2 py-1.5 text-sm transition-colors group',
                      year.id === yearStore.currentYearId ? 'bg-blue-50' : 'hover:bg-gray-50',
                    ]"
                  >
                    <button
                      @click="selectYear(year)"
                      :class="['flex-1 flex items-center gap-2 text-left min-w-0', year.id === yearStore.currentYearId ? 'text-blue-700' : 'text-gray-700']"
                    >
                      <div class="flex-1 min-w-0 pl-2">
                        <p class="font-semibold truncate">{{ year.name }}</p>
                        <p v-if="year.sem1_start" class="text-xs text-gray-400 mt-0.5">
                          S1: {{ year.sem1_start }} · S2: {{ year.sem2_start || "—" }}
                        </p>
                      </div>
                      <span v-if="year.is_current" class="text-[10px] px-1.5 py-0.5 rounded-full bg-green-100 text-green-700 font-bold flex-shrink-0">ACTIVE</span>
                      <svg v-if="year.id === yearStore.currentYearId" class="w-4 h-4 text-blue-600 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
                      </svg>
                    </button>
                    <div class="flex gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
                      <button
                        @click.stop="openEditYear(year)"
                        class="p-1 rounded hover:bg-blue-100 text-gray-400 hover:text-blue-600 transition-colors"
                        title="Edit year"
                      >
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                          <path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                        </svg>
                      </button>
                      <button
                        @click.stop="deleteYear(year)"
                        class="p-1 rounded hover:bg-red-100 text-gray-400 hover:text-red-600 transition-colors"
                        title="Delete year"
                      >
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                          <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                  </div>

                  <div v-if="!yearStore.years.length" class="px-4 py-3 text-xs text-gray-400 text-center">
                    No academic years yet
                  </div>
                </div>

                <div class="border-t border-gray-100 pt-1">
                  <button
                    @click="openAddYear"
                    class="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-blue-600 font-semibold hover:bg-blue-50 transition-colors"
                  >
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" :d="ICONS.plus" />
                    </svg>
                    Add Academic Year
                  </button>
                </div>
              </div>
            </Transition>

            <!-- Click outside -->
            <div v-if="yearDropdownOpen" class="fixed inset-0 z-40" @click="yearDropdownOpen = false" />
          </div>

          <!-- Semester toggle -->
          <div class="flex items-center h-9 bg-gray-100 rounded-xl p-0.5 gap-0.5">
            <button
              @click="yearStore.setSemester(1)"
              :class="[
                'flex items-center gap-1.5 px-3 h-8 rounded-[10px] text-sm font-semibold transition-all',
                yearStore.currentSemester === 1
                  ? 'bg-white text-blue-700 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700',
              ]"
            >
              <span class="hidden sm:inline">Semester</span>
              <span>1</span>
            </button>
            <button
              @click="yearStore.setSemester(2)"
              :class="[
                'flex items-center gap-1.5 px-3 h-8 rounded-[10px] text-sm font-semibold transition-all',
                yearStore.currentSemester === 2
                  ? 'bg-white text-blue-700 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700',
              ]"
            >
              <span class="hidden sm:inline">Semester</span>
              <span>2</span>
            </button>
          </div>

          <!-- Divider -->
          <div class="h-6 w-px bg-gray-200 hidden sm:block"></div>

          <!-- Notifications -->
          <RouterLink
            to="/notifications"
            class="relative p-2 rounded-xl hover:bg-gray-100 text-gray-500 hover:text-gray-700 transition-colors"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" :d="ICONS.notifications" />
            </svg>
          </RouterLink>

          <!-- User avatar -->
          <RouterLink to="/profile">
            <div class="flex items-center gap-2 px-2.5 py-1.5 rounded-xl hover:bg-gray-50 transition-colors cursor-pointer">
              <div class="w-7 h-7 rounded-full bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center text-white text-xs font-bold">
                {{ userInitials }}
              </div>
              <div class="hidden sm:block">
                <p class="text-sm font-semibold text-gray-900 leading-none">{{ auth.user?.first_name }}</p>
                <p class="text-[11px] text-gray-400 mt-0.5">{{ roleBadge }}</p>
              </div>
            </div>
          </RouterLink>
        </div>
      </header>

      <!-- Page content -->
      <main class="flex-1 overflow-y-auto p-6">
        <RouterView />
      </main>
    </div>

    <!-- ── Add Academic Year Modal ──────────────────────────────────── -->
    <Teleport to="body">
      <Transition
        enter-active-class="transition ease-out duration-200"
        enter-from-class="opacity-0"
        enter-to-class="opacity-100"
        leave-active-class="transition ease-in duration-150"
        leave-from-class="opacity-100"
        leave-to-class="opacity-0"
      >
        <div v-if="showYearModal" class="fixed inset-0 z-[100] flex items-center justify-center p-4">
          <!-- Backdrop -->
          <div class="absolute inset-0 bg-black/50 backdrop-blur-sm" @click="showYearModal = false" />

          <!-- Modal card -->
          <Transition
            enter-active-class="transition ease-out duration-200"
            enter-from-class="opacity-0 scale-95 translate-y-4"
            enter-to-class="opacity-100 scale-100 translate-y-0"
          >
            <div v-if="showYearModal" class="relative bg-white rounded-2xl shadow-2xl w-full max-w-md z-10 overflow-hidden">

              <!-- Header -->
              <div class="px-6 pt-6 pb-4 border-b border-gray-100">
                <div class="flex items-start justify-between">
                  <div>
                    <div class="w-10 h-10 rounded-xl bg-blue-100 flex items-center justify-center mb-3">
                      <svg class="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                    </div>
                    <h3 class="text-lg font-bold text-gray-900">{{ editingYear ? "Edit Academic Year" : "Add Academic Year" }}</h3>
                    <p class="text-sm text-gray-500 mt-0.5">{{ editingYear ? "Update the semester dates for this year." : "Create a new workspace for a different academic year." }}</p>
                  </div>
                  <button @click="showYearModal = false" class="p-2 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors -mt-1 -mr-1">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="ICONS.x" />
                    </svg>
                  </button>
                </div>
              </div>

              <!-- Form body -->
              <form @submit.prevent="submitAddYear" class="px-6 py-5 space-y-5">

                <!-- Year name -->
                <div>
                  <label class="block text-sm font-semibold text-gray-700 mb-1.5">
                    Year Name <span class="text-red-500">*</span>
                  </label>
                  <input
                    v-model="yearForm.name"
                    class="w-full px-3.5 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent placeholder-gray-400"
                    placeholder="e.g. 2026-2027"
                    required
                  />
                </div>

                <!-- Semester 1 dates -->
                <div>
                  <p class="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
                    <span class="w-5 h-5 rounded-full bg-blue-100 text-blue-700 text-xs flex items-center justify-center font-bold">1</span>
                    Semester 1 Dates
                  </p>
                  <div class="grid grid-cols-2 gap-3">
                    <div>
                      <label class="block text-xs text-gray-500 mb-1">Start</label>
                      <input v-model="yearForm.sem1_start" type="date"
                        class="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
                    </div>
                    <div>
                      <label class="block text-xs text-gray-500 mb-1">End</label>
                      <input v-model="yearForm.sem1_end" type="date"
                        class="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
                    </div>
                  </div>
                </div>

                <!-- Semester 2 dates -->
                <div>
                  <p class="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
                    <span class="w-5 h-5 rounded-full bg-indigo-100 text-indigo-700 text-xs flex items-center justify-center font-bold">2</span>
                    Semester 2 Dates
                  </p>
                  <div class="grid grid-cols-2 gap-3">
                    <div>
                      <label class="block text-xs text-gray-500 mb-1">Start</label>
                      <input v-model="yearForm.sem2_start" type="date"
                        class="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
                    </div>
                    <div>
                      <label class="block text-xs text-gray-500 mb-1">End</label>
                      <input v-model="yearForm.sem2_end" type="date"
                        class="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" />
                    </div>
                  </div>
                </div>

                <!-- Set as current -->
                <label class="flex items-center gap-3 cursor-pointer p-3 rounded-xl border border-gray-200 hover:border-blue-200 hover:bg-blue-50/50 transition-colors">
                  <div class="relative flex-shrink-0">
                    <input v-model="yearForm.is_current" type="checkbox" class="sr-only" />
                    <div :class="[
                      'w-5 h-5 rounded-md border-2 flex items-center justify-center transition-all',
                      yearForm.is_current ? 'bg-blue-600 border-blue-600' : 'border-gray-300',
                    ]">
                      <svg v-if="yearForm.is_current" class="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" :d="ICONS.check" />
                      </svg>
                    </div>
                  </div>
                  <div>
                    <p class="text-sm font-semibold text-gray-700">Set as active year</p>
                    <p class="text-xs text-gray-400">This will become the default workspace</p>
                  </div>
                </label>

                <!-- Actions -->
                <div class="flex gap-3 pt-1">
                  <button
                    type="button"
                    @click="showYearModal = false"
                    class="flex-1 px-4 py-2.5 rounded-xl border border-gray-200 text-sm font-semibold text-gray-700 hover:bg-gray-50 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    :disabled="yearModalSaving"
                    class="flex-1 px-4 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white text-sm font-semibold transition-colors flex items-center justify-center gap-2"
                  >
                    <svg v-if="yearModalSaving" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                    </svg>
                    {{ yearModalSaving ? "Saving…" : (editingYear ? "Save Changes" : "Create Year") }}
                  </button>
                </div>
              </form>
            </div>
          </Transition>
        </div>
      </Transition>
    </Teleport>

  </div>
</template>
