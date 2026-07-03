import { createRouter, createWebHistory } from "vue-router"
import { useAuthStore } from "@/stores/auth"

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    // Public routes
    { path: "/login", name: "login", component: () => import("@/views/auth/LoginView.vue"), meta: { guest: true } },
    { path: "/register", name: "register", component: () => import("@/views/auth/RegisterView.vue"), meta: { guest: true } },
    { path: "/verify-email", name: "verify-email", component: () => import("@/views/auth/VerifyEmailView.vue"), meta: { guest: true } },
    { path: "/reset-password", name: "reset-password", component: () => import("@/views/auth/ResetPasswordView.vue"), meta: { guest: true } },
    { path: "/forgot-password", name: "forgot-password", component: () => import("@/views/auth/ForgotPasswordView.vue"), meta: { guest: true } },

    // Protected routes (inside app shell)
    {
      path: "/",
      component: () => import("@/layouts/AppLayout.vue"),
      meta: { requiresAuth: true },
      children: [
        { path: "", redirect: "/dashboard" },
        { path: "dashboard", name: "dashboard", component: () => import("@/views/DashboardView.vue") },
        { path: "timetable", name: "timetable", component: () => import("@/views/timetable/TimetableView.vue") },
        { path: "timetable/:id", name: "timetable-detail", component: () => import("@/views/timetable/TimetableDetailView.vue") },
        {
          path: "generate",
          name: "generate",
          component: () => import("@/views/timetable/GenerateView.vue"),
          meta: { roles: ["admin", "timetable_officer"] },
        },
        { path: "resources/universities", name: "universities", component: () => import("@/views/resources/UniversityView.vue") },
        { path: "resources/programs", name: "programs", component: () => import("@/views/resources/ProgramsView.vue") },
        { path: "resources/student-groups", name: "student-groups", component: () => import("@/views/resources/StudentGroupsView.vue") },
        { path: "resources/departments", name: "departments", component: () => import("@/views/resources/DepartmentsView.vue") },
        { path: "resources/rooms", name: "rooms", component: () => import("@/views/resources/RoomsView.vue") },
        { path: "resources/lecturers", name: "lecturers", component: () => import("@/views/resources/LecturersView.vue") },
        { path: "resources/courses", name: "courses", component: () => import("@/views/resources/CoursesView.vue") },
        { path: "resources/assignments", name: "assignments", component: () => import("@/views/resources/AssignmentsView.vue") },
        { path: "resources/constraints", name: "constraints", component: () => import("@/views/resources/ConstraintsView.vue") },
        { path: "resources/time-slots", name: "time-slots", component: () => import("@/views/resources/TimeSlotsView.vue"), meta: { roles: ["admin", "timetable_officer"] } },
        { path: "ai-assistant", name: "ai-assistant", component: () => import("@/views/AIAssistantView.vue") },
        { path: "calendar", name: "calendar", component: () => import("@/views/CalendarView.vue") },
        { path: "analytics", name: "analytics", component: () => import("@/views/AnalyticsView.vue") },
        { path: "notifications", name: "notifications", component: () => import("@/views/NotificationsView.vue"), meta: { roles: ["admin", "timetable_officer"] } },
        { path: "admin/users", name: "admin-users", component: () => import("@/views/admin/UsersView.vue"), meta: { roles: ["admin"] } },
        { path: "admin/audit", name: "admin-audit", component: () => import("@/views/admin/AuditView.vue"), meta: { roles: ["admin"] } },
        { path: "profile", name: "profile", component: () => import("@/views/ProfileView.vue") },
      ],
    },

    { path: "/:pathMatch(.*)*", redirect: "/dashboard" },
  ],
})

router.beforeEach(async (to, from, next) => {
  const auth = useAuthStore()

  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return next({ name: "login", query: { redirect: to.fullPath } })
  }

  if (to.meta.guest && auth.isAuthenticated) {
    return next({ name: "dashboard" })
  }

  if (auth.isAuthenticated && !auth.user) {
    try { await auth.fetchMe() } catch { auth.logout(); return next({ name: "login" }) }
  }

  if (to.meta.roles && !to.meta.roles.includes(auth.userRole)) {
    return next({ name: "dashboard" })
  }

  next()
})

export default router
