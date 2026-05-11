import { defineStore } from "pinia"
import { ref, computed } from "vue"
import { authApi } from "@/api/client"

export const useAuthStore = defineStore("auth", () => {
  const user = ref(null)
  const accessToken = ref(localStorage.getItem("access_token") || null)
  const refreshToken = ref(localStorage.getItem("refresh_token") || null)

  const isAuthenticated = computed(() => !!accessToken.value)
  const userRole = computed(() => user.value?.role?.name || null)
  const isAdmin = computed(() => userRole.value === "admin")
  const isTimetableOfficer = computed(() => ["admin", "timetable_officer"].includes(userRole.value))

  async function login(email, password) {
    const { data } = await authApi.login({ email, password })
    const d = data.data
    accessToken.value = d.access_token
    refreshToken.value = d.refresh_token
    user.value = d.user
    localStorage.setItem("access_token", d.access_token)
    localStorage.setItem("refresh_token", d.refresh_token)
    return d
  }

  async function register(payload) {
    const { data } = await authApi.register(payload)
    const d = data.data
    accessToken.value = d.access_token
    refreshToken.value = d.refresh_token
    user.value = d.user
    localStorage.setItem("access_token", d.access_token)
    localStorage.setItem("refresh_token", d.refresh_token)
    return d
  }

  async function logout() {
    try { await authApi.logout() } catch {}
    user.value = null
    accessToken.value = null
    refreshToken.value = null
    localStorage.removeItem("access_token")
    localStorage.removeItem("refresh_token")
  }

  async function fetchMe() {
    const { data } = await authApi.me()
    user.value = data.data
    return data.data
  }

  return { user, accessToken, isAuthenticated, userRole, isAdmin, isTimetableOfficer, login, register, logout, fetchMe }
})
