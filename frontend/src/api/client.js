import axios from "axios"

const BASE = "/api/v1"

const api = axios.create({
  baseURL: BASE,
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token")
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config
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
  rooms: () => api.get("/rooms"),
  createRoom: (data) => api.post("/rooms", data),
  updateRoom: (id, data) => api.put(`/rooms/${id}`, data),
  lecturers: () => api.get("/lecturers"),
  createLecturer: (data) => api.post("/lecturers", data),
  courses: (params) => api.get("/courses", { params }),
  createCourse: (data) => api.post("/courses", data),
  updateCourse: (id, data) => api.put(`/courses/${id}`, data),
  constraints: () => api.get("/constraints"),
  createConstraint: (data) => api.post("/constraints", data),
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
