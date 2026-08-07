"""
Attendance API — /api/v1/attendance/
"""
import uuid
from datetime import date
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.database import get_db
from app.models.user import User, UserRole
from app.models.iot import Attendance, AttendanceStatus
from app.models.academic import Group, Enrollment, EnrollmentStatus
from app.models.lesson import Lesson
from app.core.dependencies import require_roles
from app.schemas import (
    AttendanceCreate, AttendanceUpdate, AttendanceResponse,
    AttendanceBulkCreate, StudentAttendanceSummary,
    PaginatedResponse, MessageResponse,
)

router = APIRouter(prefix="/attendance", tags=["Attendance (Davomat)"])

AnyStaff = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.TEACHER))
ManagerOrAdmin = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER))


@router.get("/", response_model=PaginatedResponse[AttendanceResponse], summary="Davomat ro'yxati")
async def list_attendance(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyStaff],
    student_id: Optional[uuid.UUID] = None,
    lesson_id: Optional[uuid.UUID] = None,
    att_status: Optional[AttendanceStatus] = Query(None, alias="status"),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    query = select(Attendance)
    if student_id:
        query = query.where(Attendance.student_id == student_id)
    if lesson_id:
        query = query.where(Attendance.lesson_id == lesson_id)
    if att_status:
        query = query.where(Attendance.status == att_status)
    # Sana filtri — Lesson orqali
    if date_from or date_to:
        query = query.join(Lesson, Attendance.lesson_id == Lesson.id)
        if date_from:
            query = query.where(Lesson.lesson_date >= date_from)
        if date_to:
            query = query.where(Lesson.lesson_date <= date_to)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    records = (await db.execute(query.offset(skip).limit(limit).order_by(Attendance.created_at.desc()))).scalars().all()
    return PaginatedResponse.create(data=records, total=total, skip=skip, limit=limit)


@router.post("/", response_model=AttendanceResponse, status_code=201, summary="Qo'lda davomat kiritish")
async def create_attendance(
    data: AttendanceCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyStaff],
):
    # Takroriy yozilishni tekshirish
    existing = (await db.execute(
        select(Attendance).where(
            and_(Attendance.student_id == data.student_id, Attendance.lesson_id == data.lesson_id)
        )
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Bu dars uchun davomat allaqachon kiritilgan")

    attendance = Attendance(
        **data.model_dump(),
        is_manual=True,
        manual_by=current_user.id,
    )
    db.add(attendance)
    await db.flush()
    await db.refresh(attendance)
    return attendance


@router.post(
    "/bulk",
    response_model=list[AttendanceResponse],
    status_code=201,
    summary="Bir dars uchun barcha o'quvchilar davomatini kiritish",
)
async def bulk_create_attendance(
    data: AttendanceBulkCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyStaff],
):
    results = []
    for record in data.records:
        existing = (await db.execute(
            select(Attendance).where(
                and_(Attendance.student_id == record.student_id, Attendance.lesson_id == data.lesson_id)
            )
        )).scalar_one_or_none()
        if existing:
            # Mavjud bo'lsa — yangilash
            for key, value in record.model_dump(exclude_unset=True).items():
                if key != "lesson_id":
                    setattr(existing, key, value)
            existing.is_manual = True
            existing.manual_by = current_user.id
            results.append(existing)
        else:
            att = Attendance(
                student_id=record.student_id,
                lesson_id=data.lesson_id,
                status=record.status,
                check_in_time=record.check_in_time,
                late_minutes=record.late_minutes,
                note=record.note,
                is_manual=True,
                manual_by=current_user.id,
            )
            db.add(att)
            results.append(att)

    await db.flush()
    for att in results:
        await db.refresh(att)
    return results


@router.put("/{attendance_id}", response_model=AttendanceResponse, summary="Davomatni yangilash")
async def update_attendance(
    attendance_id: uuid.UUID,
    data: AttendanceUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyStaff],
):
    att = (await db.execute(select(Attendance).where(Attendance.id == attendance_id))).scalar_one_or_none()
    if not att:
        raise HTTPException(status_code=404, detail="Davomat yozuvi topilmadi")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(att, key, value)
    att.is_manual = True
    att.manual_by = current_user.id

    await db.flush()
    await db.refresh(att)
    return att


@router.get(
    "/student/{student_id}/summary",
    response_model=StudentAttendanceSummary,
    summary="O'quvchi davomat statistikasi",
)
async def student_attendance_summary(
    student_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyStaff],
    group_id: Optional[uuid.UUID] = None,
):
    query = select(Attendance).where(Attendance.student_id == student_id)
    if group_id:
        lessons_in_group = select(Lesson.id).where(Lesson.group_id == group_id)
        query = query.where(Attendance.lesson_id.in_(lessons_in_group))

    records = (await db.execute(query)).scalars().all()
    total = len(records)

    counts = {s: 0 for s in AttendanceStatus}
    for r in records:
        counts[r.status] += 1

    from app.models.student import Student
    student = (await db.execute(select(Student).where(Student.id == student_id))).scalar_one_or_none()
    if not student:
        raise HTTPException(status_code=404, detail="O'quvchi topilmadi")

    rate = round(counts[AttendanceStatus.PRESENT] / total * 100, 1) if total > 0 else 0.0

    return StudentAttendanceSummary(
        student_id=student_id,
        full_name=student.full_name,
        present_count=counts[AttendanceStatus.PRESENT],
        absent_count=counts[AttendanceStatus.ABSENT],
        late_count=counts[AttendanceStatus.LATE],
        excused_count=counts[AttendanceStatus.EXCUSED],
        attendance_rate=rate,
    )
