variable "cohort" {
  description = "班級代號，群組、規則和 setup key 名稱的開頭（.env 的 COHORT）"
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{0,23}$", var.cohort))
    error_message = "COHORT 必須是小寫英數字和 -，最多 24 個字元。"
  }
}

variable "student_count" {
  description = "學生人數，學生 ID 是 student01 到 studentNN（.env 的 STUDENT_COUNT）"
  type        = number

  validation {
    condition     = var.student_count == floor(var.student_count) && var.student_count >= 1 && var.student_count <= 99
    error_message = "STUDENT_COUNT 必須是 1 到 99 的整數。"
  }
}

variable "teacher_devices" {
  description = "老師的裝置名稱，用逗號分隔，每台一把一次性 setup key（.env 的 TEACHER_DEVICES）"
  type        = string

  validation {
    condition     = length([for d in split(",", var.teacher_devices) : d if trimspace(d) != ""]) > 0
    error_message = "TEACHER_DEVICES 至少要有一台裝置。"
  }
}

variable "revoked_students" {
  description = "已撤權的學生，用逗號分隔：停用 SSH 規則、撤銷 setup key（.env 的 REVOKED_STUDENTS）"
  type        = string
  default     = ""

  validation {
    condition = alltrue([
      for s in split(",", var.revoked_students) : trimspace(s) == "" || contains(
        [for i in range(1, var.student_count + 1) : format("student%02d", i)], trimspace(s)
      )
    ])
    error_message = "REVOKED_STUDENTS 只能填 student01 到 STUDENT_COUNT 之間的學生。"
  }
}

variable "management_url" {
  description = "NetBird 管理網址，由 .env 的 NETBIRD_DOMAIN 組成"
  type        = string

  validation {
    condition     = can(regex("^https://[a-z0-9.-]+$", var.management_url))
    error_message = "management_url 必須是 https://網域。"
  }
}

variable "setup_key_days" {
  description = "一次性 setup key 的有效天數（.env 的 SETUP_KEY_DAYS）"
  type        = number

  validation {
    condition     = var.setup_key_days == floor(var.setup_key_days) && var.setup_key_days >= 1 && var.setup_key_days <= 30
    error_message = "SETUP_KEY_DAYS 必須是 1 到 30 的整數。"
  }
}

variable "default_policy_id" {
  description = "NetBird 預設 All 政策的 ID，make keys 會用 API 查出來"
  type        = string
  default     = ""
}
