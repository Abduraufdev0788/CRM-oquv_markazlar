# CRM-oquv_markazlar
# EduCRM Backend API 🚀

EduCRM — bu xususiy o'quv markazlari, IELTS markazlari va maktablar jarayonlarini avtomatlashtirish uchun mo'ljallangan, yuqori yuklamaga bardoshli (High-Load) ERP va LMS tizimining backend qismi. Loyiha **Single-Tenant** (har bir markaz uchun alohida server va baza) arxitekturasida qurilgan bo'lib, xavfsizlik va barqarorlikni maksimal darajada ta'minlaydi.

Tizim o'z ichiga IoT (Face ID uskunalar) integratsiyasini, asinxron so'rovlarni, to'liq moliyaviy hisob-kitoblarni va ota-onalarga real vaqtda Telegram/SMS xabarnomalar yuborish imkoniyatlarini qamrab oladi. Kelajakda istalgan turdagi Mobil Ilova yoki Web Frontend ulanishi uchun 100% tayyor.

---

## 🏗 Texnologiyalar Steki (Tech Stack)

* **Freymvork:** [FastAPI](https://fastapi.tiangolo.com/) (Yuqori tezlik va asinxron ishlash uchun)
* **Ma'lumotlar bazasi:** PostgreSQL 15+ (Normalizatsiya 3NF)
* **ORM & Migratsiyalar:** SQLAlchemy 2.0 & Alembic
* **Kesh va Background Tasks:** Redis & Celery (Xabarlar va hisobotlar uchun)
* **Konteynerizatsiya:** Docker & Docker Compose
* **Autentifikatsiya:** JWT (Access & Refresh Tokens) va RBAC (Role-Based Access Control)

---

## 🗄 Ma'lumotlar Bazasining Arxitekturasi

Ma'lumotlar bazasi to'liq relyatsion tamoyillarga (Foreign Keys, Index, Constraints, Cascade) asoslangan. Barcha jadvallar kod takrorlanishini oldini olish uchun yagona `BaseModel` dan (`id`, `created_at`, `updated_at`) meros oladi.

### 👥 Foydalanuvchilar va O'quvchilar
* **`User`**: CRM tizimidan foydalanadigan xodimlar (Administrator, Menejer, O'qituvchi).
* **`Parent`**: Ota-onalar. Bitta ota-ona bir nechta farzandga ega bo'lishi mumkin va yagona Telegram ID orqali barcha farzandlari bo'yicha xabarnoma oladi.
* **`Student`**: O'quvchilar profili (Face ID ma'lumotlari, balansi va h.k).

### 📚 Akademik Bo'lim (LMS)
* **`Course`**: Fan yoki kurs yo'nalishlari (Masalan: IELTS, SAT, Matematika).
* **`Room`**: Dars o'tiladigan xonalar va ularning sig'imi.
* **`Group`**: Kurslar bo'yicha ochilgan guruhlar. Dars jadvallari (schedule) tezkor qidiruv uchun **JSONB** formatida saqlanadi.
* **`Enrollment`**: (Many-to-Many bog'lovchi). Bitta o'quvchini bir nechta guruhga qatnashishini va uning holatini (ACTIVE, FROZEN, DROPPED) nazorat qiluvchi jadval.
* **`Lesson`, `Homework`, `Grade`**: Har bir dars, uy vazifalari va o'quvchilarning baholari.

### 💰 Moliya (Finance)
* **`Payment`**: O'quvchilar tomonidan qilingan to'lovlar (CASH, CARD, BANK_TRANSFER, CLICK, PAYME).
* **`Expense`**: Markazning kundalik xarajatlari.
* **`Salary`**: O'qituvchilarning oylik maoshlari, bonus va jarimalari.

### 🤖 IoT va Davomat (Face ID)
* **`FaceDevice`**: Markazga o'rnatilgan Face ID uskunalarining ro'yxati (IP, Serial Number).
* **`FaceLog`**: Uskunadan keladigan xom loglar (Raw data). Server qotmasligi va xatoliklarni tahlil qilish uchun alohida saqlanadi.
* **`Attendance`**: Tahlil qilingan toza davomat jadvali (PRESENT, ABSENT, LATE, EXCUSED).

### 🛡 Xavfsizlik va Tizim
* **`Notification`**: Telegram, SMS yoki Email orqali yuborilgan barcha xabarlar tarixi va holati.
* **`RefreshToken`**: Xavfsiz JWT autentifikatsiyasini ta'minlash uchun bazada saqlanuvchi tokenlar.
* **`AuditLog`**: Tizimdagi har qanday muhim amallarni (kim, qachon, qaysi jadvalni, qanday o'zgartirdi) kuzatib boruvchi xavfsizlik jurnali.

---

## 📊 Entity Relationship Diagram (Abstrakt ERD)

```text
User (Admin, Manager, Teacher)
  ├── Groups (Teacher)
  ├── Payments (Created by)
  ├── Salary
  ├── AuditLog
  └── RefreshToken

Course ────── Group ────── Room
                │
                ├── Lesson ────── Homework
                │     │
                │     └── Attendance
                │
            Enrollment (M:M)
                │
Parent ────── Student ────── Grade
                │
                ├── Payment
                └── Notification

FaceDevice ── FaceLog ── Student (face_data_id)
