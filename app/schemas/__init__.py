"""
Schemas — barcha import lar shu yerdan amalga oshiriladi.
"""

# ── Base ───────────────────────────────────────────────────────────────────────
from app.schemas.base import BaseSchema, BaseResponse, PaginatedResponse, MessageResponse

# ── User & Auth ────────────────────────────────────────────────────────────────
from app.schemas.user import (
    TokenResponse, RefreshRequest, LogoutRequest,
    UserCreate, UserUpdate, PasswordChange,
    UserResponse, UserBriefResponse,
)

# ── Student & Parent ───────────────────────────────────────────────────────────
from app.schemas.student import (
    ParentCreate, ParentUpdate, ParentResponse, ParentBriefResponse,
    StudentCreate, StudentUpdate, StudentResponse,
    StudentBriefResponse, StudentBalanceResponse,
)

# ── Academic ───────────────────────────────────────────────────────────────────
from app.schemas.academic import (
    CourseCreate, CourseUpdate, CourseResponse, CourseBriefResponse,
    RoomCreate, RoomUpdate, RoomResponse,
    ScheduleItem,
    GroupCreate, GroupUpdate, GroupResponse, GroupBriefResponse,
    EnrollmentCreate, EnrollmentUpdate, EnrollmentResponse,
)

# ── Lesson ─────────────────────────────────────────────────────────────────────
from app.schemas.lesson import (
    LessonCreate, LessonUpdate, LessonResponse, LessonBriefResponse,
    HomeworkCreate, HomeworkUpdate, HomeworkResponse,
    GradeCreate, GradeUpdate, GradeResponse, StudentGradeSummary,
)

# ── Finance ────────────────────────────────────────────────────────────────────
from app.schemas.finance import (
    PaymentCreate, PaymentUpdate, PaymentResponse,
    PaymentBriefResponse, MonthlyPaymentSummary,
    ExpenseCreate, ExpenseUpdate, ExpenseResponse, ExpenseSummary,
    SalaryCreate, SalaryUpdate, SalaryPayRequest, SalaryResponse,
)

# ── IoT ────────────────────────────────────────────────────────────────────────
from app.schemas.iot import (
    FaceDeviceCreate, FaceDeviceUpdate, FaceDeviceResponse,
    FaceWebhookPayload, FaceLogResponse,
    AttendanceCreate, AttendanceUpdate, AttendanceResponse,
    AttendanceBulkCreate, GroupAttendanceSummary, StudentAttendanceSummary,
)

# ── System ─────────────────────────────────────────────────────────────────────
from app.schemas.system import (
    NotificationCreate, NotificationResponse,
    AuditLogResponse, AuditLogFilter,
)

__all__ = [
    # Base
    "BaseSchema", "BaseResponse", "PaginatedResponse", "MessageResponse",
    # Auth
    "TokenResponse", "RefreshRequest", "LogoutRequest",
    # User
    "UserCreate", "UserUpdate", "PasswordChange", "UserResponse", "UserBriefResponse",
    # Student
    "ParentCreate", "ParentUpdate", "ParentResponse", "ParentBriefResponse",
    "StudentCreate", "StudentUpdate", "StudentResponse", "StudentBriefResponse", "StudentBalanceResponse",
    # Academic
    "CourseCreate", "CourseUpdate", "CourseResponse", "CourseBriefResponse",
    "RoomCreate", "RoomUpdate", "RoomResponse",
    "ScheduleItem",
    "GroupCreate", "GroupUpdate", "GroupResponse", "GroupBriefResponse",
    "EnrollmentCreate", "EnrollmentUpdate", "EnrollmentResponse",
    # Lesson
    "LessonCreate", "LessonUpdate", "LessonResponse", "LessonBriefResponse",
    "HomeworkCreate", "HomeworkUpdate", "HomeworkResponse",
    "GradeCreate", "GradeUpdate", "GradeResponse", "StudentGradeSummary",
    # Finance
    "PaymentCreate", "PaymentUpdate", "PaymentResponse", "PaymentBriefResponse", "MonthlyPaymentSummary",
    "ExpenseCreate", "ExpenseUpdate", "ExpenseResponse", "ExpenseSummary",
    "SalaryCreate", "SalaryUpdate", "SalaryPayRequest", "SalaryResponse",
    # IoT
    "FaceDeviceCreate", "FaceDeviceUpdate", "FaceDeviceResponse",
    "FaceWebhookPayload", "FaceLogResponse",
    "AttendanceCreate", "AttendanceUpdate", "AttendanceResponse",
    "AttendanceBulkCreate", "GroupAttendanceSummary", "StudentAttendanceSummary",
    # System
    "NotificationCreate", "NotificationResponse",
    "AuditLogResponse", "AuditLogFilter",
]
