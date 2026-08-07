# EduCRM Backend API 🚀

EduCRM — bu xususiy o'quv markazlari, IELTS markazlari va maktablar jarayonlarini avtomatlashtirish uchun mo'ljallangan, yuqori yuklamaga bardoshli (High-Load) ERP va LMS tizimining backend qismi. Loyiha **Single-Tenant** (har bir markaz uchun alohida server va baza) arxitekturasida qurilgan bo'lib, xavfsizlik va barqarorlikni maksimal darajada ta'minlaydi.

Tizim o'z ichiga IoT (Face ID uskunalar) integratsiyasini, asinxron so'rovlarni, to'liq moliyaviy hisob-kitoblarni va ota-onalarga real vaqtda Telegram/SMS xabarnomalar yuborish imkoniyatlarini qamrab oladi. Kelajakda istalgan turdagi Mobil Ilova yoki Web Frontend ulanishi uchun 100% tayyor.

---

## 🏗 Texnologiyalar Steki (Tech Stack)

| Soha | Texnologiya | Maqsad |
|---|---|---|
| **Freymvork** | FastAPI | Yuqori tezlik va asinxron ishlash |
| **Ma'lumotlar bazasi** | PostgreSQL 15+ | Normalizatsiya 3NF, JSONB, Index |
| **ORM & Migratsiyalar** | SQLAlchemy 2.0 & Alembic | Model va migratsiya boshqaruvi |
| **Kesh** | Redis | Token cache, session, rate limiting |
| **Background Tasks** | Celery + Redis Broker | Xabarlar, hisobotlar, davomat tahlili |
| **Konteynerizatsiya** | Docker & Docker Compose | Bir xil muhit, oson deploy |
| **Autentifikatsiya** | JWT + RBAC | Access/Refresh token, rol asosida ruxsat |
| **IoT Integratsiya** | Face ID HTTP/MQTT | Davomat avtomatik qayd etish |
| **Xabarnomalar** | Telegram Bot API, SMS | Real vaqt ota-ona xabardorligi |

---

## 🗄 Ma'lumotlar Bazasining Arxitekturasi

Ma'lumotlar bazasi to'liq relyatsion tamoyillarga (Foreign Keys, Index, Constraints, Cascade) asoslangan. Barcha jadvallar kod takrorlanishini oldini olish uchun yagona `BaseModel` dan (`id`, `created_at`, `updated_at`) meros oladi.

### 👥 Foydalanuvchilar va O'quvchilar

| Model | Tavsif |
|---|---|
| **`User`** | CRM tizimidan foydalanadigan xodimlar: `ADMIN`, `MANAGER`, `TEACHER` rollari |
| **`Parent`** | Ota-onalar. Bitta ota-ona bir nechta farzandga ega, yagona Telegram ID orqali xabarnoma oladi |
| **`Student`** | O'quvchilar profili — Face ID ma'lumotlari (`face_data_id`), balans, holat va h.k. |

### 📚 Akademik Bo'lim (LMS)

| Model | Tavsif |
|---|---|
| **`Course`** | Fan / kurs yo'nalishlari: IELTS, SAT, Matematika va h.k. |
| **`Room`** | Dars xonalari va ularning sig'imi (capacity) |
| **`Group`** | Kurs bo'yicha ochilgan guruhlar. Jadval (schedule) **JSONB** da saqlangan |
| **`Enrollment`** | M:M bog'lovchi — o'quvchi holati: `ACTIVE`, `FROZEN`, `DROPPED` |
| **`Lesson`** | Har bir guruhning o'tkazilgan darslari |
| **`Homework`** | Darsga bog'liq uy vazifalari |
| **`Grade`** | O'quvchi baholari (homework va lesson bo'yicha) |

### 💰 Moliya (Finance)

| Model | Tavsif |
|---|---|
| **`Payment`** | O'quvchi to'lovlari — `CASH`, `CARD`, `BANK_TRANSFER`, `CLICK`, `PAYME` |
| **`Expense`** | Markaz xarajatlari (ijara, kommunal, uskunalar va h.k.) |
| **`Salary`** | O'qituvchi maoshi — asosiy, bonus, jarima, holat: `PENDING`, `PAID` |

### 🤖 IoT va Davomat (Face ID)

| Model | Tavsif |
|---|---|
| **`FaceDevice`** | Markazga o'rnatilgan qurilmalar — IP, serial raqam, holat |
| **`FaceLog`** | Qurilmadan keladigan xom (raw) loglar — tahlil uchun alohida saqlanadi |
| **`Attendance`** | Toza davomat — `PRESENT`, `ABSENT`, `LATE`, `EXCUSED` |

### 🛡 Xavfsizlik va Tizim

| Model | Tavsif |
|---|---|
| **`Notification`** | Telegram/SMS/Email xabarnomalar tarixi va holati |
| **`RefreshToken`** | Xavfsiz JWT uchun bazada saqlanuvchi refresh tokenlar |
| **`AuditLog`** | Kim, qachon, qaysi jadvalni, qanday o'zgartirganini kuzatuvchi jurnal |

---

## 📊 Entity Relationship Diagram (Abstrakt ERD)

```text
User (Admin, Manager, Teacher)
  ├── Group (teacher_id → FK)
  ├── Payment (created_by → FK)
  ├── Salary (user_id → FK)
  ├── AuditLog (user_id → FK)
  └── RefreshToken (user_id → FK)

Course ────── Group ────── Room
                │
                ├── Lesson ──────── Homework
                │     │                │
                │     └── Attendance   └── Grade
                │
            Enrollment (M:M)
           /             \
       Student           Group
          │
          ├── Grade
          ├── Payment
          ├── Notification
          └── FaceLog (face_data_id)

Parent ──── Student (parent_id → FK)
              │
              └── Notification (shared via parent Telegram ID)

FaceDevice ──── FaceLog ──── Student (face_data_id → FK)
                   │
                   └── Attendance (auto-generated)
```

---

## 🗃 Modellar Tuzilishi (Database Schema)

> Barcha modellar `BaseModel` dan meros oladi: `id` (UUID), `created_at`, `updated_at`

---

### 🔷 BaseModel (Abstract)

```python
id          UUID        PRIMARY KEY, default=uuid4
created_at  TIMESTAMP   NOT NULL, default=now()
updated_at  TIMESTAMP   NOT NULL, onupdate=now()
```

---

### 👤 User (Xodimlar)

```python
# Enum: UserRole
ADMIN    = "admin"
MANAGER  = "manager"
TEACHER  = "teacher"

# Jadval: users
id            UUID         PK
full_name     VARCHAR(100) NOT NULL
phone         VARCHAR(20)  UNIQUE, NOT NULL          -- login sifatida
email         VARCHAR(100) UNIQUE, NULLABLE
password_hash VARCHAR(255) NOT NULL
role          UserRole     NOT NULL, default=TEACHER
is_active     BOOLEAN      NOT NULL, default=True
photo_url     VARCHAR(255) NULLABLE
last_login    TIMESTAMP    NULLABLE

# Index: idx_users_phone, idx_users_role
```

---

### 👨‍👩‍👧 Parent (Ota-onalar)

```python
# Jadval: parents
id           UUID         PK
full_name    VARCHAR(100) NOT NULL
phone        VARCHAR(20)  UNIQUE, NOT NULL
telegram_id  BIGINT       UNIQUE, NULLABLE   -- Telegram xabarlar uchun
is_bot_active BOOLEAN     NOT NULL, default=False
notes        TEXT         NULLABLE

# Index: idx_parents_telegram_id
```

---

### 🎓 Student (O'quvchilar)

```python
# Enum: StudentStatus
ACTIVE    = "active"
INACTIVE  = "inactive"
GRADUATED = "graduated"
EXPELLED  = "expelled"

# Jadval: students
id              UUID          PK
full_name       VARCHAR(100)  NOT NULL
phone           VARCHAR(20)   UNIQUE, NULLABLE
birth_date      DATE          NULLABLE
photo_url       VARCHAR(255)  NULLABLE
parent_id       UUID          FK → parents.id, ON DELETE SET NULL
status          StudentStatus NOT NULL, default=ACTIVE
balance         NUMERIC(12,2) NOT NULL, default=0.00  -- to'lov balansi
face_data_id    VARCHAR(100)  UNIQUE, NULLABLE        -- Face ID qurilma ID
notes           TEXT          NULLABLE

# Index: idx_students_parent_id, idx_students_face_data_id, idx_students_status
# Constraint: balance >= 0 (CHECK)
```

---

### 📘 Course (Kurslar)

```python
# Jadval: courses
id           UUID          PK
name         VARCHAR(100)  NOT NULL          -- "IELTS", "SAT", "Matematika"
description  TEXT          NULLABLE
monthly_fee  NUMERIC(10,2) NOT NULL          -- oylik to'lov
duration_months INT        NULLABLE          -- kurs davomiyligi
is_active    BOOLEAN       NOT NULL, default=True
color_hex    VARCHAR(7)    NULLABLE          -- UI uchun rang (#FF5733)

# Index: idx_courses_is_active
```

---

### 🏫 Room (Xonalar)

```python
# Jadval: rooms
id           UUID         PK
name         VARCHAR(50)  NOT NULL          -- "Xona 1", "Lab A"
capacity     SMALLINT     NOT NULL          -- max sig'im
floor        SMALLINT     NULLABLE
has_projector BOOLEAN     NOT NULL, default=False
is_active    BOOLEAN      NOT NULL, default=True
```

---

### 👥 Group (Guruhlar)

```python
# Enum: GroupStatus
ACTIVE   = "active"
ARCHIVED = "archived"
PLANNED  = "planned"

# Jadval: groups
id          UUID         PK
name        VARCHAR(100) NOT NULL           -- "IELTS-2024-A"
course_id   UUID         FK → courses.id, NOT NULL
room_id     UUID         FK → rooms.id, NULLABLE
teacher_id  UUID         FK → users.id, ON DELETE SET NULL
status      GroupStatus  NOT NULL, default=PLANNED
start_date  DATE         NOT NULL
end_date    DATE         NULLABLE
max_students SMALLINT    NOT NULL, default=15
schedule    JSONB        NOT NULL
# schedule namunasi:
# [
#   {"day": "monday", "start": "09:00", "end": "11:00"},
#   {"day": "wednesday", "start": "09:00", "end": "11:00"}
# ]

# Index: idx_groups_teacher_id, idx_groups_course_id, idx_groups_status
# GIN Index: idx_groups_schedule (JSONB tezkor qidiruv)
```

---

### 📋 Enrollment (O'quvchi ↔ Guruh)

```python
# Enum: EnrollmentStatus
ACTIVE  = "active"
FROZEN  = "frozen"    -- to'xtatilgan (hisoblanmaydi)
DROPPED = "dropped"   -- tashlab ketgan

# Jadval: enrollments
id           UUID             PK
student_id   UUID             FK → students.id, NOT NULL
group_id     UUID             FK → groups.id, NOT NULL
status       EnrollmentStatus NOT NULL, default=ACTIVE
enrolled_at  DATE             NOT NULL, default=today()
dropped_at   DATE             NULLABLE
discount_pct NUMERIC(5,2)     NOT NULL, default=0  -- chegirma foizi (0-100)
notes        TEXT             NULLABLE

# UNIQUE: (student_id, group_id)
# Index: idx_enrollments_student_id, idx_enrollments_group_id, idx_enrollments_status
```

---

### 📅 Lesson (Darslar)

```python
# Jadval: lessons
id           UUID         PK
group_id     UUID         FK → groups.id, NOT NULL
title        VARCHAR(200) NULLABLE          -- "Unit 5: Reading"
lesson_date  DATE         NOT NULL
start_time   TIME         NOT NULL
end_time     TIME         NOT NULL
topic        TEXT         NULLABLE
is_cancelled BOOLEAN      NOT NULL, default=False
cancel_reason TEXT        NULLABLE

# Index: idx_lessons_group_id, idx_lessons_lesson_date
```

---

### 📝 Homework (Uy Vazifalari)

```python
# Jadval: homeworks
id           UUID         PK
lesson_id    UUID         FK → lessons.id, NOT NULL
title        VARCHAR(200) NOT NULL
description  TEXT         NULLABLE
due_date     DATE         NULLABLE
max_score    NUMERIC(5,2) NOT NULL, default=100
file_url     VARCHAR(255) NULLABLE          -- vazifa fayli

# Index: idx_homeworks_lesson_id
```

---

### ⭐ Grade (Baholar)

```python
# Enum: GradeType
HOMEWORK  = "homework"
LESSON    = "lesson"     -- dars ichidagi baho
EXAM      = "exam"

# Jadval: grades
id           UUID         PK
student_id   UUID         FK → students.id, NOT NULL
lesson_id    UUID         FK → lessons.id, NULLABLE
homework_id  UUID         FK → homeworks.id, NULLABLE
grade_type   GradeType    NOT NULL
score        NUMERIC(5,2) NOT NULL
max_score    NUMERIC(5,2) NOT NULL, default=100
comment      TEXT         NULLABLE
graded_by    UUID         FK → users.id  -- O'qituvchi

# Constraint: score <= max_score (CHECK)
# Index: idx_grades_student_id, idx_grades_lesson_id
```

---

### 💵 Payment (To'lovlar)

```python
# Enum: PaymentMethod
CASH          = "cash"
CARD          = "card"
BANK_TRANSFER = "bank_transfer"
CLICK         = "click"
PAYME         = "payme"

# Enum: PaymentStatus
PENDING   = "pending"
CONFIRMED = "confirmed"
CANCELLED = "cancelled"

# Jadval: payments
id             UUID          PK
student_id     UUID          FK → students.id, NOT NULL
enrollment_id  UUID          FK → enrollments.id, NULLABLE
amount         NUMERIC(12,2) NOT NULL
method         PaymentMethod NOT NULL
status         PaymentStatus NOT NULL, default=CONFIRMED
period_month   SMALLINT      NOT NULL           -- 1-12
period_year    SMALLINT      NOT NULL           -- 2024
transaction_id VARCHAR(100)  UNIQUE, NULLABLE   -- Click/Payme tranzaksiya ID
receipt_url    VARCHAR(255)  NULLABLE
comment        TEXT          NULLABLE
created_by     UUID          FK → users.id      -- qabul qilgan xodim

# Index: idx_payments_student_id, idx_payments_period, idx_payments_status
# Index: (period_year, period_month) -- oylik hisobot uchun
```

---

### 💸 Expense (Xarajatlar)

```python
# Enum: ExpenseCategory
RENT        = "rent"          -- ijara
SALARY      = "salary"        -- maosh
UTILITY     = "utility"       -- kommunal
EQUIPMENT   = "equipment"     -- uskunalar
MARKETING   = "marketing"
OTHER       = "other"

# Jadval: expenses
id           UUID            PK
category     ExpenseCategory NOT NULL
amount       NUMERIC(12,2)   NOT NULL
description  TEXT            NOT NULL
expense_date DATE            NOT NULL
receipt_url  VARCHAR(255)    NULLABLE
created_by   UUID            FK → users.id

# Index: idx_expenses_expense_date, idx_expenses_category
```

---

### 💰 Salary (Maoshlar)

```python
# Enum: SalaryStatus
PENDING   = "pending"
PAID      = "paid"
CANCELLED = "cancelled"

# Jadval: salaries
id            UUID          PK
user_id       UUID          FK → users.id, NOT NULL
period_month  SMALLINT      NOT NULL
period_year   SMALLINT      NOT NULL
base_amount   NUMERIC(12,2) NOT NULL      -- asosiy maosh
bonus_amount  NUMERIC(12,2) NOT NULL, default=0
penalty_amount NUMERIC(12,2) NOT NULL, default=0
-- total = base + bonus - penalty (computed/property)
status        SalaryStatus  NOT NULL, default=PENDING
paid_at       TIMESTAMP     NULLABLE
paid_by       UUID          FK → users.id, NULLABLE
comment       TEXT          NULLABLE

# UNIQUE: (user_id, period_month, period_year)
# Index: idx_salaries_user_id, idx_salaries_status
```

---

### 📷 FaceDevice (Face ID Qurilmalar)

```python
# Enum: DeviceStatus
ONLINE   = "online"
OFFLINE  = "offline"
ERROR    = "error"

# Jadval: face_devices
id            UUID         PK
name          VARCHAR(100) NOT NULL        -- "Kirish eshigi", "Lab B"
ip_address    VARCHAR(45)  UNIQUE, NOT NULL
serial_number VARCHAR(100) UNIQUE, NOT NULL
location      VARCHAR(200) NULLABLE
status        DeviceStatus NOT NULL, default=OFFLINE
last_ping     TIMESTAMP    NULLABLE
api_secret    VARCHAR(255) NOT NULL        -- webhook autentifikatsiya

# Index: idx_face_devices_status
```

---

### 📄 FaceLog (Xom Loglar)

```python
# Jadval: face_logs
id            UUID         PK
device_id     UUID         FK → face_devices.id, NOT NULL
face_data_id  VARCHAR(100) NOT NULL        -- qurilma yuborgan shaxs ID
raw_payload   JSONB        NOT NULL        -- qurilmadan kelgan to'liq JSON
logged_at     TIMESTAMP    NOT NULL        -- qurilma vaqti
received_at   TIMESTAMP    NOT NULL, default=now()
is_processed  BOOLEAN      NOT NULL, default=False
error_message TEXT         NULLABLE        -- tahlil xatosi

# Index: idx_face_logs_is_processed, idx_face_logs_logged_at
# Index: idx_face_logs_face_data_id
# GIN Index: idx_face_logs_payload (JSONB)
```

---

### 📊 Attendance (Davomat)

```python
# Enum: AttendanceStatus
PRESENT  = "present"
ABSENT   = "absent"
LATE     = "late"       -- kechikib keldi
EXCUSED  = "excused"    -- sababli yo'q

# Jadval: attendances
id            UUID             PK
student_id    UUID             FK → students.id, NOT NULL
lesson_id     UUID             FK → lessons.id, NOT NULL
status        AttendanceStatus NOT NULL
check_in_time TIME             NULLABLE      -- kirish vaqti
late_minutes  SMALLINT         NULLABLE      -- necha daqiqa kechikdi
face_log_id   UUID             FK → face_logs.id, NULLABLE  -- manba log
is_manual     BOOLEAN          NOT NULL, default=False      -- qo'lda kiritilganmi
manual_by     UUID             FK → users.id, NULLABLE
note          TEXT             NULLABLE

# UNIQUE: (student_id, lesson_id)
# Index: idx_attendances_student_id, idx_attendances_lesson_id, idx_attendances_status
```

---

### 🔔 Notification (Xabarnomalar)

```python
# Enum: NotificationChannel
TELEGRAM = "telegram"
SMS      = "sms"
EMAIL    = "email"

# Enum: NotificationStatus
PENDING  = "pending"
SENT     = "sent"
FAILED   = "failed"

# Enum: NotificationType
ATTENDANCE     = "attendance"
PAYMENT_DUE    = "payment_due"
PAYMENT_RECEIVED = "payment_received"
GRADE          = "grade"
GENERAL        = "general"

# Jadval: notifications
id            UUID                 PK
parent_id     UUID                 FK → parents.id, NULLABLE
student_id    UUID                 FK → students.id, NULLABLE
channel       NotificationChannel  NOT NULL
notif_type    NotificationType     NOT NULL
title         VARCHAR(200)         NOT NULL
body          TEXT                 NOT NULL
status        NotificationStatus   NOT NULL, default=PENDING
sent_at       TIMESTAMP            NULLABLE
error_message TEXT                 NULLABLE
external_id   VARCHAR(100)         NULLABLE  -- Telegram message_id

# Index: idx_notifications_status, idx_notifications_parent_id
```

---

### 🔑 RefreshToken

```python
# Jadval: refresh_tokens
id          UUID         PK
user_id     UUID         FK → users.id, NOT NULL, ON DELETE CASCADE
token_hash  VARCHAR(255) NOT NULL            -- SHA-256 hash
device_info VARCHAR(255) NULLABLE            -- "iPhone 14 / iOS 17"
ip_address  VARCHAR(45)  NULLABLE
is_revoked  BOOLEAN      NOT NULL, default=False
expires_at  TIMESTAMP    NOT NULL

# Index: idx_refresh_tokens_user_id, idx_refresh_tokens_is_revoked
# Partial Index: WHERE is_revoked = FALSE  (faqat aktiv tokenlar)
```

---

### 🔍 AuditLog (Audit Jurnali)

```python
# Enum: AuditAction
CREATE = "create"
UPDATE = "update"
DELETE = "delete"
LOGIN  = "login"
LOGOUT = "logout"

# Jadval: audit_logs
id            UUID         PK
user_id       UUID         FK → users.id, NULLABLE  -- tizim amali bo'lsa NULL
action        AuditAction  NOT NULL
table_name    VARCHAR(100) NOT NULL       -- "students", "payments"
record_id     UUID         NULLABLE       -- o'zgartirilgan yozuv ID
old_values    JSONB        NULLABLE       -- o'zgarishdan oldingi holat
new_values    JSONB        NULLABLE       -- o'zgarishdan keyingi holat
ip_address    VARCHAR(45)  NULLABLE
user_agent    TEXT         NULLABLE
description   TEXT         NULLABLE

# Index: idx_audit_logs_user_id, idx_audit_logs_table_name
# Index: idx_audit_logs_created_at  -- vaqt bo'yicha filtrlash
# NOTE: Bu jadvalga UPDATE va DELETE ta'qiqlangan (immutable log)
```

---

## 📁 Loyiha Strukturasi

```
CRM-oquv_markazlar/
│
├── app/
│   ├── main.py                  # FastAPI ilovasi, router ulanishlari
│   ├── config.py                # Muhit o'zgaruvchilari (Pydantic Settings)
│   ├── database.py              # SQLAlchemy engine, session
│   │
│   ├── models/                  # SQLAlchemy modellari
│   │   ├── base.py              # BaseModel (id, created_at, updated_at)
│   │   ├── user.py              # User, RefreshToken
│   │   ├── student.py           # Student, Parent
│   │   ├── academic.py          # Course, Room, Group, Enrollment
│   │   ├── lesson.py            # Lesson, Homework, Grade
│   │   ├── finance.py           # Payment, Expense, Salary
│   │   ├── iot.py               # FaceDevice, FaceLog, Attendance
│   │   └── system.py            # Notification, AuditLog
│   │
│   ├── schemas/                 # Pydantic sxemalari (Request/Response)
│   │   ├── user.py
│   │   ├── student.py
│   │   ├── academic.py
│   │   ├── finance.py
│   │   └── iot.py
│   │
│   ├── api/                     # API Router endpointlari
│   │   ├── v1/
│   │   │   ├── auth.py          # Login, refresh, logout
│   │   │   ├── users.py         # Xodimlar CRUD
│   │   │   ├── students.py      # O'quvchilar CRUD
│   │   │   ├── groups.py        # Guruhlar va jadval
│   │   │   ├── attendance.py    # Davomat boshqaruvi
│   │   │   ├── finance.py       # To'lovlar, xarajatlar, maosh
│   │   │   ├── face.py          # IoT webhook endpointlari
│   │   │   └── reports.py       # Hisobot va statistika
│   │
│   ├── core/                    # Markaziy logika
│   │   ├── security.py          # JWT, parol hashing
│   │   ├── permissions.py       # RBAC dekoratorlari
│   │   ├── dependencies.py      # FastAPI Depends() to'plamlari
│   │   └── audit.py             # AuditLog yozish yordamchisi
│   │
│   ├── services/                # Biznes logika
│   │   ├── attendance_service.py
│   │   ├── notification_service.py
│   │   ├── salary_service.py
│   │   └── report_service.py
│   │
│   └── tasks/                   # Celery background tasklar
│       ├── celery_app.py
│       ├── notification_tasks.py
│       └── report_tasks.py
│
├── alembic/                     # DB migratsiyalari
│   ├── env.py
│   └── versions/
│
├── tests/                       # Testlar
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_students.py
│   └── test_finance.py
│
├── .env.example                 # Muhit o'zgaruvchilari namunasi
├── docker-compose.yml           # Docker konteynerlari
├── Dockerfile                   # FastAPI image
├── requirements.txt             # Python kutubxonalari
└── README.md
```

---

## 🔐 RBAC — Rol Asosida Ruxsat Tizimi

```
ADMIN
  └── Barcha amallar (o'qish, yozish, o'chirish, moliya, xodimlar)

MANAGER
  ├── O'quvchilar va guruhlar boshqaruvi
  ├── To'lovlarni qayd etish
  ├── Davomat ko'rish
  └── Hisobotlarni ko'rish (moliya KIRIMSIZ)

TEACHER
  ├── Faqat o'z guruhlarini ko'rish
  ├── Dars va uy vazifalarini qo'shish
  ├── O'z guruhidagi o'quvchilar davomat va baholarini boshqarish
  └── O'z maosh tarixini ko'rish
```

---

## 🚀 O'rnatish va Ishga Tushirish

### 1. Repozitoriyani Klonlash

```bash
git clone https://github.com/yourname/CRM-oquv_markazlar.git
cd CRM-oquv_markazlar
```

### 2. Muhit O'zgaruvchilarini Sozlash

```bash
cp .env.example .env
# .env faylini o'z ma'lumotlaringiz bilan to'ldiring
```

`.env` fayl namunasi:

```env
# PostgreSQL
DATABASE_URL=postgresql+asyncpg://crm_user:strongpassword@db:5432/educrm_db

# Redis
REDIS_URL=redis://redis:6379/0

# JWT
SECRET_KEY=your-super-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=30

# Telegram Bot
TELEGRAM_BOT_TOKEN=your-telegram-bot-token

# SMS Gateway (Eskiz.uz yoki Playmobile)
SMS_API_KEY=your-sms-api-key
SMS_SENDER=4546

# App
APP_ENV=development
DEBUG=True
```

### 3. Docker bilan Ishga Tushirish (Tavsiya etilgan)

```bash
# Konteynerni qurish va ishga tushirish
docker-compose up --build -d

# Migratsiyalarni qo'llash
docker-compose exec api alembic upgrade head

# Loglarni kuzatish
docker-compose logs -f api
```

### 4. Local Muhitda Ishga Tushirish

```bash
# Virtual muhit yaratish
python -m venv venv
source venv/bin/activate

# Kutubxonalarni o'rnatish
pip install -r requirements.txt

# Migratsiyalarni qo'llash
alembic upgrade head

# Serverni ishga tushirish
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 🐳 Docker Compose Xizmatlari

```yaml
services:
  api:        # FastAPI — port 8000
  db:         # PostgreSQL 15
  redis:      # Redis 7
  celery:     # Celery Worker (xabarnomalar)
  celery-beat # Celery Beat (rejalashtirilgan vazifalar)
```

---

## 📡 API Endpointlari (v1)

### Autentifikatsiya
| Method | Endpoint | Tavsif |
|---|---|---|
| `POST` | `/api/v1/auth/login` | Token olish |
| `POST` | `/api/v1/auth/refresh` | Tokenni yangilash |
| `POST` | `/api/v1/auth/logout` | Tizimdan chiqish |

### Foydalanuvchilar
| Method | Endpoint | Tavsif |
|---|---|---|
| `GET` | `/api/v1/users/` | Barcha xodimlar ro'yxati |
| `POST` | `/api/v1/users/` | Yangi xodim qo'shish |
| `GET` | `/api/v1/users/{id}` | Xodim ma'lumoti |
| `PUT` | `/api/v1/users/{id}` | Xodim tahrirlash |
| `DELETE` | `/api/v1/users/{id}` | Xodimni o'chirish |

### O'quvchilar
| Method | Endpoint | Tavsif |
|---|---|---|
| `GET` | `/api/v1/students/` | O'quvchilar ro'yxati |
| `POST` | `/api/v1/students/` | Yangi o'quvchi qo'shish |
| `GET` | `/api/v1/students/{id}` | O'quvchi profili + guruhlar + balans |
| `PUT` | `/api/v1/students/{id}` | O'quvchi tahrirlash |
| `GET` | `/api/v1/students/{id}/payments` | O'quvchi to'lovlar tarixi |
| `GET` | `/api/v1/students/{id}/attendance` | O'quvchi davomat tarixi |

### Guruhlar va Akademik
| Method | Endpoint | Tavsif |
|---|---|---|
| `GET` | `/api/v1/groups/` | Barcha guruhlar |
| `POST` | `/api/v1/groups/` | Yangi guruh |
| `POST` | `/api/v1/groups/{id}/enroll` | O'quvchini guruhga qo'shish |
| `GET` | `/api/v1/groups/{id}/schedule` | Guruh dars jadvali |
| `POST` | `/api/v1/lessons/` | Dars qayd etish |
| `POST` | `/api/v1/lessons/{id}/homework` | Uy vazifasi qo'shish |

### Moliya
| Method | Endpoint | Tavsif |
|---|---|---|
| `POST` | `/api/v1/payments/` | To'lov qabul qilish |
| `GET` | `/api/v1/payments/` | To'lovlar ro'yxati (filter bilan) |
| `POST` | `/api/v1/expenses/` | Xarajat qayd etish |
| `GET` | `/api/v1/salary/` | Maoshlar ro'yxati |
| `POST` | `/api/v1/salary/{id}/pay` | Maosh to'lash |

### IoT / Face ID
| Method | Endpoint | Tavsif |
|---|---|---|
| `POST` | `/api/v1/face/webhook` | Face ID qurilmadan log qabul qilish |
| `GET` | `/api/v1/attendance/` | Davomat ro'yxati |
| `PUT` | `/api/v1/attendance/{id}` | Davomat qo'lda tahrirlash |

### Hisobotlar
| Method | Endpoint | Tavsif |
|---|---|---|
| `GET` | `/api/v1/reports/finance` | Moliyaviy hisobot (oy/yil) |
| `GET` | `/api/v1/reports/attendance` | Davomat hisoboti |
| `GET` | `/api/v1/reports/teacher/{id}` | O'qituvchi ko'rsatkichlari |

---

## ⚙️ Celery Background Tasklar

```python
# Har kuni soat 09:00 da o'tmish to'lovchi o'quvchilarga eslatma
send_payment_reminders.delay()

# Davomat logidan Attendance jadvaliga avtomatik tahlil
process_face_log.delay(face_log_id)

# Ota-onaga Telegram orqali davomat xabari
notify_parent_attendance.delay(student_id, status)

# Oylik maosh hisoboti (Celery Beat)
generate_monthly_salary_report.delay()
```

---

## 🔔 Xabarnoma Oqimi (Notification Flow)

```
Face ID Qurilma
    │
    ▼ HTTP POST /api/v1/face/webhook
FaceLog (xom ma'lumot saqlanadi)
    │
    ▼ Celery Task: process_face_log
Attendance (PRESENT / LATE aniqlash)
    │
    ▼ Celery Task: notify_parent_attendance
Notification (DB ga yoziladi)
    │
    ├──▶ Telegram Bot API → Ota-onaga xabar
    └──▶ SMS Gateway (agar Telegram yo'q bo'lsa)
```

---

## 🧪 Testlar

```bash
# Barcha testlarni ishga tushirish
pytest tests/ -v

# Coverage bilan
pytest tests/ --cov=app --cov-report=html

# Faqat autentifikatsiya testlari
pytest tests/test_auth.py -v
```

---

## 📈 Kelajakdagi Rejalar (Roadmap)

- [ ] **v1.0** — Asosiy CRUD, Auth, Finance ✅
- [ ] **v1.1** — Face ID webhook va Attendance avtomatizatsiyasi
- [ ] **v1.2** — Telegram Bot ota-onalar uchun
- [ ] **v1.3** — Hisobotlar (PDF/Excel eksport)
- [ ] **v2.0** — Multi-branch qo'llab-quvvatlash (bir zanjir, bir nechta filial)
- [ ] **v2.1** — Mobile App uchun optimizatsiya (React Native / Flutter)

---

## 🤝 Hissa Qo'shish (Contributing)

1. Repozitoriyani fork qiling
2. Yangi branch yarating: `git checkout -b feature/your-feature`
3. O'zgarishlarni commit qiling: `git commit -m 'feat: add some feature'`
4. Branch ga push qiling: `git push origin feature/your-feature`
5. Pull Request oching

---

## 📄 Litsenziya

Bu loyiha [MIT License](LICENSE) ostida tarqatiladi.

---

<div align="center">

**EduCRM** — O'quv markazingizni raqamlashtiring 🎓

*FastAPI · PostgreSQL · Redis · Celery · Docker*

</div>
