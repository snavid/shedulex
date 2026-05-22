<script setup>
import { ref, computed, h } from "vue"
import { RouterView, useRouter, RouterLink, useLink } from "vue-router"
import { useAuthStore } from "@/stores/auth"

const auth = useAuthStore()
const router = useRouter()
const sidebarOpen = ref(true)
const mobileOpen = ref(false)

// ── Heroicon SVG paths (outline style) ───────────────────────────────────────
const ICONS = {
  dashboard: "M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6",
  timetable: "M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z",
  generate: "M13 10V3L4 14h7v7l9-11h-7z",
  ai: "M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z",
  calendar: "M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z",
  analytics: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z",
  notifications: "M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9",
  university: "M12 14l9-5-9-5-9 5 9 5z M12 14l6.16-3.422a12.083 12.083 0 01.665 6.479A11.952 11.952 0 0012 20.055a11.952 11.952 0 00-6.824-2.998 12.078 12.078 0 01.665-6.479L12 14z",
  programs: "M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253",
  groups: "M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z",
  departments: "M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-2 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4",
  rooms: "M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6",
  lecturers: "M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z",
  courses: "M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253",
  constraints: "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z",
  timeslots: "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z",
  users: "M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z",
  audit: "M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z",
  menu: "M4 6h16M4 12h16M4 18h16",
  close: "M6 18L18 6M6 6l12 12",
  logout: "M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1",
  chevronLeft: "M15 19l-7-7 7-7",
  chevronRight: "M9 5l7 7-7 7",
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
    { to: "/dashboard", label: "Dashboard", icon: "dashboard" },
    { to: "/timetable", label: "Timetables", icon: "timetable" },
    { to: "/ai-assistant", label: "AI Assistant", icon: "ai" },
    { to: "/calendar", label: "Calendar", icon: "calendar" },
    { to: "/analytics", label: "Analytics", icon: "analytics" },
    { to: "/notifications", label: "Notifications", icon: "notifications" },
    { section: "Academic Structure" },
    { to: "/resources/universities", label: "Universities", icon: "university", roles: ["admin", "timetable_officer"] },
    { to: "/resources/programs", label: "Programs", icon: "programs" },
    { to: "/resources/student-groups", label: "Student Groups", icon: "groups" },
    { to: "/resources/departments", label: "Departments", icon: "departments" },
    { section: "Resources" },
    { to: "/resources/rooms", label: "Rooms", icon: "rooms" },
    { to: "/resources/lecturers", label: "Lecturers", icon: "lecturers" },
    { to: "/resources/courses", label: "Courses", icon: "courses" },
    { to: "/resources/constraints", label: "Constraints", icon: "constraints" },
    { to: "/resources/time-slots", label: "Time Slots", icon: "timeslots", roles: ["admin", "timetable_officer"] },
  ]

  if (auth.isTimetableOfficer) {
    base.splice(2, 0, { to: "/generate", label: "Generate", icon: "generate" })
  }

  if (auth.isAdmin) {
    base.push(
      { section: "Administration" },
      { to: "/admin/users", label: "Users", icon: "users" },
      { to: "/admin/audit", label: "Audit Logs", icon: "audit" },
    )
  }

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
          <!-- Section label -->
          <p v-if="item.section" :class="['px-2 pt-5 pb-1 text-xs font-semibold text-gray-400 uppercase tracking-wider select-none', !sidebarOpen && 'text-center']">
            <span v-if="sidebarOpen">{{ item.section }}</span>
            <span v-else class="block w-full border-t border-gray-200 mt-1"></span>
          </p>

          <!-- Nav link -->
          <RouterLink v-else :to="item.to" v-slot="{ isActive }" custom>
            <a
              :href="item.to"
              @click.prevent="router.push(item.to)"
              :title="!sidebarOpen ? item.label : ''"
              :class="[
                'flex items-center gap-3 px-2.5 py-2 rounded-lg text-sm font-medium transition-colors cursor-pointer',
                isActive
                  ? 'bg-blue-50 text-blue-700'
                  : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900',
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

      <!-- Top bar -->
      <header class="h-16 bg-white border-b border-gray-200 px-4 flex items-center justify-between flex-shrink-0 gap-4">
        <div class="flex items-center gap-3">
          <!-- Mobile hamburger -->
          <button @click="mobileOpen = !mobileOpen" class="p-2 rounded-lg hover:bg-gray-100 text-gray-500 lg:hidden">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="ICONS.menu" />
            </svg>
          </button>

          <!-- Desktop expand button (when collapsed) -->
          <button v-if="!sidebarOpen" @click="sidebarOpen = true" class="p-2 rounded-lg hover:bg-gray-100 text-gray-500 hidden lg:flex">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" :d="ICONS.menu" />
            </svg>
          </button>
        </div>

        <!-- Right actions -->
        <div class="flex items-center gap-2">
          <RouterLink
            to="/notifications"
            class="relative p-2 rounded-lg hover:bg-gray-100 text-gray-500 hover:text-gray-700 transition-colors"
          >
            <component :is="Icon" name="notifications" class="w-5 h-5" />
          </RouterLink>

          <RouterLink to="/profile">
            <div class="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-gray-50 transition-colors cursor-pointer">
              <div class="w-7 h-7 rounded-full bg-gradient-to-br from-blue-500 to-blue-700 flex items-center justify-center text-white text-xs font-bold">
                {{ userInitials }}
              </div>
              <div class="hidden sm:block">
                <p class="text-sm font-medium text-gray-900 leading-none">{{ auth.user?.first_name }}</p>
                <p class="text-xs text-gray-400 mt-0.5">{{ roleBadge }}</p>
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
  </div>
</template>
