import axios from "axios"

const BASE = "/api/v1"

const api = axios.create({
  baseURL: BASE,
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
})

export function getErrorMessage(error, fallback = "Request failed.") {
  const payload = error?.response?.data
  if (typeof payload === "string" && payload) return payload
  return payload?.message || payload?.error || error?.message || fallback
}

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token")
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config
    const message = (error?.response?.data?.message || "").toLowerCase()

    if (error.response?.status === 401 && message.includes("mandatory 'iss'")) {
      localStorage.removeItem("access_token")
      localStorage.removeItem("refresh_token")
      if (window.location.pathname !== "/login") {
        window.location.href = "/login?reason=session"
      }
      return Promise.reject(error)
    }

    if (error.response?.status === 401 && !original._retry) {
      original._retry = true
      const refreshToken = localStorage.getItem("refresh_token")
      if (refreshToken) {
        try {
          const { data } = await axios.post(`${BASE}/auth/refresh`, {}, {
            headers: { Authorization: `Bearer ${refreshToken}` },
          })
          localStorage.setItem("access_token", data.data.access_token)
          original.headers.Authorization = `Bearer ${data.data.access_token}`
          return api(original)
        } catch {
          localStorage.clear()
          window.location.href = "/login"
        }
      }
    }
    return Promise.reject(error)
  },
)

export default api

// Typed API modules
export const authApi = {
  register: (data) => api.post("/auth/register", data),
  login: (data) => api.post("/auth/login", data),
  logout: () => api.post("/auth/logout"),
  me: () => api.get("/auth/me"),
  changePassword: (data) => api.post("/auth/change-password", data),
  requestReset: (data) => api.post("/auth/password-reset/request", data),
  confirmReset: (data) => api.post("/auth/password-reset/confirm", data),
  verifyEmail: (token) => api.get(`/auth/verify-email?token=${token}`),
}

export const timetableApi = {
  generate: (data) => api.post("/timetable/generate", data),
  list: (params) => api.get("/timetable/", { params }),
  get: (id) => api.get(`/timetable/${id}`),
  conflicts: (id) => api.get(`/timetable/${id}/conflicts`),
  swapEntries: (data) => api.post("/timetable/entries/swap", data),
}

export const resourcesApi = {
  departments: () => api.get("/departments"),
  createDepartment: (data) => api.post("/departments", data),
  updateDepartment: (id, data) => api.put(`/departments/${id}`, data),
  deleteDepartment: (id) => api.delete(`/departments/${id}`),
  rooms: () => api.get("/rooms"),
  createRoom: (data) => api.post("/rooms", data),
  updateRoom: (id, data) => api.put(`/rooms/${id}`, data),
  deleteRoom: (id) => api.delete(`/rooms/${id}`),
  lecturers: () => api.get("/lecturers"),
  createLecturer: (data) => api.post("/lecturers", data),
  updateLecturer: (id, data) => api.put(`/lecturers/${id}`, data),
  deleteLecturer: (id) => api.delete(`/lecturers/${id}`),
  courses: (params) => api.get("/courses", { params }),
  createCourse: (data) => api.post("/courses", data),
  updateCourse: (id, data) => api.put(`/courses/${id}`, data),
  deleteCourse: (id) => api.delete(`/courses/${id}`),
  constraints: () => api.get("/constraints"),
  createConstraint: (data) => api.post("/constraints", data),
  timeSlots: () => api.get("/time-slots"),
}

export const adjustmentApi = {
  chat: (data) => api.post("/adjustments/chat", data),
  history: (params) => api.get("/adjustments/history", { params }),
  conflicts: (params) => api.get("/adjustments/conflicts", { params }),
  suggestSlots: (data) => api.post("/adjustments/suggest-slots", data),
}

export const notificationApi = {
  send: (data) => api.post("/notifications/send", data),
  list: () => api.get("/notifications/"),
  templates: () => api.get("/notifications/templates"),
  broadcast: (data) => api.post("/notifications/broadcast", data),
}

export const calendarApi = {
  events: (params) => api.get("/calendar/events", { params }),
  createEvent: (data) => api.post("/calendar/events", data),
  updateEvent: (id, data) => api.put(`/calendar/events/${id}`, data),
  deleteEvent: (id) => api.delete(`/calendar/events/${id}`),
  semesters: () => api.get("/calendar/semesters"),
  createSemester: (data) => api.post("/calendar/semesters", data),
  exportIcs: () => `${BASE}/calendar/events/export.ics`,
}

export const documentApi = {
  downloadPdf: (id) => `${BASE}/documents/timetable/${id}/pdf`,
  downloadExcel: (id) => `${BASE}/documents/timetable/${id}/excel`,
  downloadCsv: (id) => `${BASE}/documents/timetable/${id}/csv`,
  downloadBundle: (id, formats = ["pdf", "excel", "csv"]) =>
    `${BASE}/documents/timetable/${id}/bundle?formats=${encodeURIComponent(formats.join(","))}`,
  preview: (id) => api.get(`/documents/timetable/${id}/preview`),
  downloadPdfBlob: (id) => api.get(`/documents/timetable/${id}/pdf`, { responseType: "blob" }),
  downloadExcelBlob: (id) => api.get(`/documents/timetable/${id}/excel`, { responseType: "blob" }),
  downloadCsvBlob: (id) => api.get(`/documents/timetable/${id}/csv`, { responseType: "blob" }),
  downloadBundleBlob: (id, formats = ["pdf", "excel", "csv"]) =>
    api.get(`/documents/timetable/${id}/bundle`, { params: { formats: formats.join(",") }, responseType: "blob" }),
  createShareLink: (data) => api.post("/documents/share-links", data),
  analyticsOverview: (params) => api.get("/documents/analytics/overview", { params }),
}

export const analyticsApi = {
  overview: () => api.get("/analytics/overview"),
  timetableMetrics: (id) => api.get(`/analytics/timetable/${id}/metrics`),
  roomUtilization: () => api.get("/analytics/rooms/utilization"),
  lecturerWorkload: () => api.get("/analytics/lecturers/workload"),
}

export const usersApi = {
  list: (params) => api.get("/users/", { params }),
  get: (id) => api.get(`/users/${id}`),
  update: (id, data) => api.patch(`/users/${id}`, data),
  toggleActivation: (id) => api.patch(`/users/${id}/activate`),
  changeRole: (id, role_name) => api.patch(`/users/${id}/role`, { role_name }),
  roles: () => api.get("/users/roles/all"),
}

export const auditApi = {
  list: (params) => api.get("/audit/logs", { params }),
  userActivity: (userId) => api.get(`/audit/logs/user/${userId}`),
  stats: () => api.get("/audit/logs/stats"),
}
