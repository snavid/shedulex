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
  if (payload?.errors) {
    const msgs = Object.values(payload.errors).flat().filter(Boolean)
    if (msgs.length) return msgs.join(" ")
  }
  return payload?.message || payload?.error || error?.message || fallback
}

export function validatePhone(phone) {
  if (!phone?.trim()) return "Phone number is required."
  const value = phone.trim()
  if (value.includes("@")) return "Phone cannot be an email address."
  if (value.length < 10 || value.length > 25) return "Phone must be 10–25 characters."
  return null
}

export function isInvalidStoredPhone(phone) {
  if (!phone) return false
  return phone.includes("@") || phone.length > 25 || phone.length < 10
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
  generate: (data) => api.post("/timetable/generate", data, { timeout: 600000 }),
  list: (params) => api.get("/timetable/", { params }),
  get: (id) => api.get(`/timetable/${id}`),
  conflicts: (id) => api.get(`/timetable/${id}/conflicts`),
  violations: (id) => api.get(`/timetable/${id}/violations`),
  predictions: (id) => api.post(`/timetable/${id}/predict-conflicts`),
  swapEntries: (data) => api.post("/timetable/entries/swap", data),
  moveEntry: (entryId, time_slot_id) =>
    api.patch(`/timetable/entries/${entryId}`, { time_slot_id }),
  toggleLock: (timetableId, entryId) =>
    api.patch(`/timetable/${timetableId}/entries/${entryId}/lock`),
  substituteLecturer: (timetableId, data) =>
    api.post(`/timetable/${timetableId}/substitute-lecturer`, data),
  archive: (timetableId) => api.patch(`/timetable/${timetableId}/archive`),
  delete: (timetableId) => api.delete(`/timetable/${timetableId}`),
  listVersions: (timetableId) => api.get(`/timetable/${timetableId}/versions`),
  createVersion: (timetableId, data) => api.post(`/timetable/${timetableId}/versions`, data),
  restoreVersion: (snapshotId) => api.post(`/timetable/versions/${snapshotId}/restore`),
}

export const resourcesApi = {
  // Universities
  universities: (params) => api.get("/universities", { params }),
  createUniversity: (data) => api.post("/universities", data),
  updateUniversity: (id, data) => api.put(`/universities/${id}`, data),
  deleteUniversity: (id) => api.delete(`/universities/${id}`),
  // Programs
  programs: (params) => api.get("/programs", { params }),
  createProgram: (data) => api.post("/programs", data),
  updateProgram: (id, data) => api.put(`/programs/${id}`, data),
  deleteProgram: (id) => api.delete(`/programs/${id}`),
  assignLecturerToProgram: (progId, lecturerId) => api.post(`/programs/${progId}/lecturers`, { lecturer_id: lecturerId }),
  removeLecturerFromProgram: (progId, lecId) => api.delete(`/programs/${progId}/lecturers/${lecId}`),
  // Student Groups
  studentGroups: (params) => api.get("/student-groups", { params }),
  createStudentGroup: (data) => api.post("/student-groups", data),
  updateStudentGroup: (id, data) => api.put(`/student-groups/${id}`, data),
  deleteStudentGroup: (id) => api.delete(`/student-groups/${id}`),
  // Departments
  departments: (params) => api.get("/departments", { params }),
  createDepartment: (data) => api.post("/departments", data),
  updateDepartment: (id, data) => api.put(`/departments/${id}`, data),
  deleteDepartment: (id) => api.delete(`/departments/${id}`),
  // Rooms
  rooms: () => api.get("/rooms"),
  createRoom: (data) => api.post("/rooms", data),
  updateRoom: (id, data) => api.put(`/rooms/${id}`, data),
  deleteRoom: (id) => api.delete(`/rooms/${id}`),
  // Lecturers (timetable service)
  lecturers: () => api.get("/lecturers"),
  createLecturer: (data) => api.post("/lecturers", data),
  updateLecturer: (id, data) => api.put(`/lecturers/${id}`, data),
  deleteLecturer: (id) => api.delete(`/lecturers/${id}`),
  // Courses
  courses: (params) => api.get("/courses", { params }),
  createCourse: (data) => api.post("/courses", data),
  updateCourse: (id, data) => api.put(`/courses/${id}`, data),
  deleteCourse: (id) => api.delete(`/courses/${id}`),
  // Course ↔ StudentGroup assignments
  getCourseGroups: (id) => api.get(`/courses/${id}/groups`),
  setCourseGroups: (id, groupIds) => api.post(`/courses/${id}/groups`, { group_ids: groupIds }),
  removeCourseGroup: (courseId, groupId) => api.delete(`/courses/${courseId}/groups/${groupId}`),
  // Per-group lecturer overrides
  setGroupLecturer: (courseId, groupId, lecturerId) =>
    api.put(`/courses/${courseId}/groups/${groupId}/lecturer`, { lecturer_id: lecturerId }),
  removeGroupLecturer: (courseId, groupId) =>
    api.delete(`/courses/${courseId}/groups/${groupId}/lecturer`),
  // Constraints
  constraints: (params) => api.get("/constraints", { params }),
  createConstraint: (data) => api.post("/constraints", data),
  updateConstraint: (id, data) => api.put(`/constraints/${id}`, data),
  deleteConstraint: (id) => api.delete(`/constraints/${id}`),
  // Time Slots
  timeSlots: (params) => api.get("/time-slots", { params }),
  createTimeSlot: (data) => api.post("/time-slots", data),
  updateTimeSlot: (id, data) => api.put(`/time-slots/${id}`, data),
  deleteTimeSlot: (id) => api.delete(`/time-slots/${id}`),
  // Timetable Templates
  templates: (params) => api.get("/templates", { params }),
  getTemplate: (id) => api.get(`/templates/${id}`),
  createTemplate: (data) => api.post("/templates", data),
  updateTemplate: (id, data) => api.put(`/templates/${id}`, data),
  deleteTemplate: (id) => api.delete(`/templates/${id}`),
  templateBlocks: (templateId) => api.get(`/templates/${templateId}/blocks`),
  createTemplateBlock: (templateId, data) => api.post(`/templates/${templateId}/blocks`, data),
  updateTemplateBlock: (templateId, blockId, data) => api.put(`/templates/${templateId}/blocks/${blockId}`, data),
  deleteTemplateBlock: (templateId, blockId) => api.delete(`/templates/${templateId}/blocks/${blockId}`),
  generateSlotsFromTemplate: (templateId) => api.post(`/templates/${templateId}/generate-slots`),
}

export const adjustmentApi = {
  // Legacy single-shot API
  chat: (data) => api.post("/adjustments/chat", data, { timeout: 180000 }),
  requestStatus: (requestId) => api.get(`/adjustments/requests/${requestId}`),
  history: (params) => api.get("/adjustments/history", { params }),
  conflicts: (params) => api.get("/adjustments/conflicts", { params }),
  suggestSlots: (data) => api.post("/adjustments/suggest-slots", data),
  // Session-based AI API
  createSession:  (data)     => api.post("/adjustments/sessions", data),
  listSessions:   (params)   => api.get("/adjustments/sessions", { params }),
  getSession:     (id)       => api.get(`/adjustments/sessions/${id}`),
  sessionChat:    (id, data) => api.post(`/adjustments/sessions/${id}/chat`, data, { timeout: 30000 }),
  sessionRespond: (id, data) => api.post(`/adjustments/sessions/${id}/respond`, data),
  archiveSession: (id)       => api.post(`/adjustments/sessions/${id}/archive`),
}

export const notificationApi = {
  send: (data) => api.post("/notifications/send", data),
  list: () => api.get("/notifications/"),
  templates: () => api.get("/notifications/templates"),
  broadcast: (data) => api.post("/notifications/broadcast", data),
}

export const calendarApi = {
  // Events
  events: (params) => api.get("/calendar/events", { params }),
  createEvent: (data) => api.post("/calendar/events", data),
  updateEvent: (id, data) => api.put(`/calendar/events/${id}`, data),
  deleteEvent: (id) => api.delete(`/calendar/events/${id}`),
  cancelEvent: (id, reason) => api.patch(`/calendar/events/${id}/cancel`, { reason }),
  uncancelEvent: (id) => api.patch(`/calendar/events/${id}/uncancel`),
  affectedSessions: (id) => api.get(`/calendar/events/${id}/affected-sessions`),
  exportIcs: () => `${BASE}/calendar/events/export.ics`,
  // Semesters
  semesters: (params) => api.get("/calendar/semesters", { params }),
  currentSemester: (params) => api.get("/calendar/semesters/current", { params }),
  getSemester: (id) => api.get(`/calendar/semesters/${id}`),
  createSemester: (data) => api.post("/calendar/semesters", data),
  updateSemester: (id, data) => api.put(`/calendar/semesters/${id}`, data),
  deleteSemester: (id) => api.delete(`/calendar/semesters/${id}`),
  setCurrentSemester: (id) => api.patch(`/calendar/semesters/${id}/set-current`),
  // Holidays
  holidays: (params) => api.get("/calendar/holidays", { params }),
  createHoliday: (data) => api.post("/calendar/holidays", data),
  updateHoliday: (id, data) => api.put(`/calendar/holidays/${id}`, data),
  deleteHoliday: (id) => api.delete(`/calendar/holidays/${id}`),
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
  approveUser: (id) => api.patch(`/users/${id}/approve`),
  rejectUser: (id) => api.patch(`/users/${id}/reject`),
  roles: () => api.get("/users/roles/all"),
  createLecturer: (data) => api.post("/users/lecturers", data),
  resendCredentials: (id) => api.post(`/users/${id}/resend-credentials`),
}

export const academicYearsApi = {
  list: (params) => api.get("/academic-years", { params }),
  create: (data) => api.post("/academic-years", data),
  update: (id, data) => api.put(`/academic-years/${id}`, data),
  activate: (id) => api.post(`/academic-years/${id}/activate`),
  delete: (id) => api.delete(`/academic-years/${id}`),
}

export const auditApi = {
  list: (params) => api.get("/audit/logs", { params }),
  userActivity: (userId) => api.get(`/audit/logs/user/${userId}`),
  stats: () => api.get("/audit/logs/stats"),
}
