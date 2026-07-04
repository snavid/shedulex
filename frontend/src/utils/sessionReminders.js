const DAY_INDEX = {
  Sunday: 0,
  Monday: 1,
  Tuesday: 2,
  Wednesday: 3,
  Thursday: 4,
  Friday: 5,
  Saturday: 6,
}

export const LEAD_OPTIONS = [
  { minutes: 1440, label: "1 day before" },
  { minutes: 60, label: "1 hour before" },
  { minutes: 15, label: "15 minutes before" },
  { minutes: 0, label: "At class time" },
]

export const REMINDER_CHANNELS = [
  { value: "sms", label: "SMS" },
  { value: "email", label: "Email" },
  { value: "both", label: "Both" },
]

export function dayNameToIndex(day) {
  return DAY_INDEX[day] ?? 1
}

function parseTimeOnDate(date, timeStr) {
  const [h, m] = (timeStr || "09:00").split(":").map(Number)
  const d = new Date(date)
  d.setHours(h || 0, m || 0, 0, 0)
  return d
}

export function nextOccurrence(entry, fromDate = new Date()) {
  const day = entry?.time_slot?.day
  const startTime = entry?.time_slot?.start_time
  if (!day || !startTime) return null

  const targetDow = dayNameToIndex(day)
  const cursor = new Date(fromDate)
  cursor.setHours(0, 0, 0, 0)

  for (let i = 0; i < 8; i++) {
    const check = new Date(cursor)
    check.setDate(cursor.getDate() + i)
    if (check.getDay() !== targetDow) continue

    const start = parseTimeOnDate(check, startTime)
    if (start > fromDate) return start
  }
  return null
}

export function countWeeklyOccurrences(entry, fromDate, untilDateStr) {
  const first = nextOccurrence(entry, fromDate)
  if (!first || !untilDateStr) return 0
  const until = new Date(untilDateStr + "T23:59:59")
  let count = 0
  let current = new Date(first)
  while (current <= until) {
    count++
    current = new Date(current)
    current.setDate(current.getDate() + 7)
  }
  return count
}

export function buildSessionReminderPayload(entry, options) {
  const {
    channel,
    leadTimes,
    occurrenceDate,
    repeatWeeklyUntil = null,
  } = options

  const occ = occurrenceDate instanceof Date ? occurrenceDate : new Date(occurrenceDate)
  const dateStr = occ.toISOString().slice(0, 10)
  const endTime = entry?.time_slot?.end_time
  const endDate = endTime ? parseTimeOnDate(occ, endTime) : new Date(occ.getTime() + 60 * 60 * 1000)

  const title = entry.course?.name || entry.course?.code || "Class session"
  const payload = {
    event_source: "session",
    event_key: `session:${entry.id}:${dateStr}`,
    event_title: title,
    event_start: occ.toISOString(),
    event_end: endDate.toISOString(),
    channel,
    lead_times: [...leadTimes],
    metadata: {
      entry_id: entry.id,
      occurrence_date: dateStr,
      course_code: entry.course?.code,
      course_name: entry.course?.name,
      room: entry.room?.name || entry.room?.code,
    },
  }

  if (repeatWeeklyUntil) {
    payload.repeat_weekly_until = repeatWeeklyUntil
    payload.entry_id = entry.id
  }

  return payload
}

export function leadLabel(minutes) {
  return LEAD_OPTIONS.find(o => o.minutes === minutes)?.label || `${minutes} min before`
}

export function formatReminderTime(iso) {
  if (!iso) return "—"
  return new Date(iso).toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

export function remindersForEntry(reminders, entryId) {
  return (reminders || []).filter(
    r => r.status === "pending" && (
      r.metadata?.entry_id === entryId
      || r.event_key?.startsWith(`session:${entryId}:`)
    ),
  )
}

export function pendingCountForEntry(reminders, entryId) {
  return remindersForEntry(reminders, entryId).length
}
