<script setup>
import { ref, computed } from "vue"
import { RouterView, useRouter } from "vue-router"
import { useAuthStore } from "@/stores/auth"

const auth = useAuthStore()
const router = useRouter()
const sidebarOpen = ref(true)

const navItems = computed(() => {
  const base = [
    { to: "/dashboard", label: "Dashboard", icon: "📊" },
    { to: "/timetable", label: "Timetables", icon: "📅" },
    { to: "/generate", label: "Generate", icon: "⚡" },
    { to: "/ai-assistant", label: "AI Assistant", icon: "🤖" },
    { to: "/calendar", label: "Calendar", icon: "🗓️" },
    { to: "/analytics", label: "Analytics", icon: "📈" },
    { to: "/notifications", label: "Notifications", icon: "🔔" },
    { section: "Resources" },
    { to: "/resources/departments", label: "Departments", icon: "🏛️" },
    { to: "/resources/rooms", label: "Rooms", icon: "🚪" },
    { to: "/resources/lecturers", label: "Lecturers", icon: "👨‍🏫" },
    { to: "/resources/courses", label: "Courses", icon: "📚" },
    { to: "/resources/constraints", label: "Constraints", icon: "⚙️" },
  ]
  if (auth.isAdmin) {
    base.push(
      { section: "Admin" },
      { to: "/admin/users", label: "Users", icon: "👥" },
      { to: "/admin/audit", label: "Audit Logs", icon: "🔍" },
    )
  }
  return base
})

async function handleLogout() {
  await auth.logout()
  router.push("/login")
}
</script>

<template>
  <div class="flex h-screen overflow-hidden bg-gray-50">
    <!-- Sidebar -->
    <aside
      :class="['flex-shrink-0 flex flex-col bg-white border-r border-gray-200 transition-all duration-300', sidebarOpen ? 'w-60' : 'w-16']"
    >
      <!-- Logo -->
      <div class="flex items-center gap-3 px-4 py-5 border-b border-gray-200">
        <div class="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold text-sm flex-shrink-0">S</div>
        <span v-if="sidebarOpen" class="font-bold text-gray-900 text-lg">Shedulex</span>
      </div>

      <!-- Navigation -->
      <nav class="flex-1 overflow-y-auto py-4 px-3 space-y-1">
        <template v-for="item in navItems" :key="item.to || item.section">
          <p v-if="item.section" class="px-3 pt-4 pb-1 text-xs font-semibold text-gray-400 uppercase tracking-wider">
            {{ sidebarOpen ? item.section : "—" }}
          </p>
          <RouterLink
            v-else
            :to="item.to"
            v-slot="{ isActive }"
          >
            <a
              :class="['sidebar-link', isActive ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900']"
            >
              <span class="text-lg flex-shrink-0">{{ item.icon }}</span>
              <span v-if="sidebarOpen" class="truncate">{{ item.label }}</span>
            </a>
          </RouterLink>
        </template>
      </nav>

      <!-- User section -->
      <div class="p-3 border-t border-gray-200">
        <RouterLink to="/profile" class="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-gray-100 transition-colors">
          <div class="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
            {{ auth.user?.first_name?.[0] || "U" }}
          </div>
          <div v-if="sidebarOpen" class="min-w-0">
            <p class="text-sm font-medium text-gray-900 truncate">{{ auth.user?.first_name }} {{ auth.user?.last_name }}</p>
            <p class="text-xs text-gray-500 truncate capitalize">{{ auth.userRole?.replace("_", " ") }}</p>
          </div>
        </RouterLink>
        <button
          @click="handleLogout"
          class="mt-2 w-full flex items-center gap-3 px-3 py-2 rounded-lg text-red-600 hover:bg-red-50 text-sm font-medium transition-colors"
        >
          <span class="text-lg flex-shrink-0">🚪</span>
          <span v-if="sidebarOpen">Sign Out</span>
        </button>
      </div>
    </aside>

    <!-- Main content -->
    <div class="flex-1 flex flex-col overflow-hidden">
      <!-- Top bar -->
      <header class="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between flex-shrink-0">
        <button @click="sidebarOpen = !sidebarOpen" class="p-2 rounded-lg hover:bg-gray-100 transition-colors text-gray-600">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <div class="flex items-center gap-3">
          <RouterLink to="/notifications" class="p-2 rounded-lg hover:bg-gray-100 text-gray-600">🔔</RouterLink>
          <RouterLink to="/profile" class="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white text-xs font-bold">
            {{ auth.user?.first_name?.[0] || "U" }}
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
