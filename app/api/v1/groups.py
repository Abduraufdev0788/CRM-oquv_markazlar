"""
Groups & Enrollment API — /api/v1/groups/, /api/v1/courses/, /api/v1/rooms/
"""
import uuid
from datetime import date
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.database import get_db
from app.models.user import User, UserRole
from app.models.academic import Course, Room, Group, Enrollment, GroupStatus, EnrollmentStatus
from app.core.dependencies import require_roles
from app.schemas import (
    CourseCreate, CourseUpdate, CourseResponse,
    RoomCreate, RoomUpdate, RoomResponse,
    GroupCreate, GroupUpdate, GroupResponse, GroupBriefResponse,
    EnrollmentCreate, EnrollmentUpdate, EnrollmentResponse,
    PaginatedResponse, MessageResponse,
)

router = APIRouter(tags=["Academic (Kurslar, Guruhlar)"])

AnyStaff = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.TEACHER))
ManagerOrAdmin = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER))
AdminOnly = Depends(require_roles(UserRole.ADMIN))


# ── COURSES ────────────────────────────────────────────────────────────────────
@router.get("/courses/", response_model=PaginatedResponse[CourseResponse], summary="Kurslar ro'yxati")
async def list_courses(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyStaff],
    is_active: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
):
    query = select(Course)
    if is_active is not None:
        query = query.where(Course.is_active == is_active)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    courses = (await db.execute(query.offset(skip).limit(limit))).scalars().all()
    return PaginatedResponse.create(data=courses, total=total, skip=skip, limit=limit)


@router.post("/courses/", response_model=CourseResponse, status_code=201, summary="Yangi kurs")
async def create_course(
    data: CourseCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, ManagerOrAdmin],
):
    course = Course(**data.model_dump())
    db.add(course)
    await db.flush()
    await db.refresh(course)
    return course


@router.put("/courses/{course_id}", response_model=CourseResponse, summary="Kursni yangilash")
async def update_course(
    course_id: uuid.UUID, data: CourseUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, ManagerOrAdmin],
):
    course = (await db.execute(select(Course).where(Course.id == course_id))).scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Kurs topilmadi")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(course, k, v)
    await db.flush()
    await db.refresh(course)
    return course


# ── ROOMS ──────────────────────────────────────────────────────────────────────
@router.get("/rooms/", response_model=PaginatedResponse[RoomResponse], summary="Xonalar ro'yxati")
async def list_rooms(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyStaff],
    is_active: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
):
    query = select(Room)
    if is_active is not None:
        query = query.where(Room.is_active == is_active)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rooms = (await db.execute(query.offset(skip).limit(limit))).scalars().all()
    return PaginatedResponse.create(data=rooms, total=total, skip=skip, limit=limit)


@router.post("/rooms/", response_model=RoomResponse, status_code=201, summary="Yangi xona")
async def create_room(
    data: RoomCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, ManagerOrAdmin],
):
    room = Room(**data.model_dump())
    db.add(room)
    await db.flush()
    await db.refresh(room)
    return room


@router.put("/rooms/{room_id}", response_model=RoomResponse, summary="Xonani yangilash")
async def update_room(
    room_id: uuid.UUID, data: RoomUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, ManagerOrAdmin],
):
    room = (await db.execute(select(Room).where(Room.id == room_id))).scalar_one_or_none()
    if not room:
        raise HTTPException(status_code=404, detail="Xona topilmadi")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(room, k, v)
    await db.flush()
    await db.refresh(room)
    return room


# ── GROUPS ─────────────────────────────────────────────────────────────────────
@router.get("/groups/", response_model=PaginatedResponse[GroupBriefResponse], summary="Guruhlar ro'yxati")
async def list_groups(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyStaff],
    group_status: Optional[GroupStatus] = Query(None, alias="status"),
    course_id: Optional[uuid.UUID] = Query(None),
    teacher_id: Optional[uuid.UUID] = Query(None),
    skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
):
    if current_user.role == UserRole.TEACHER:
        teacher_id = current_user.id
    query = select(Group)
    if group_status:
        query = query.where(Group.status == group_status)
    if course_id:
        query = query.where(Group.course_id == course_id)
    if teacher_id:
        query = query.where(Group.teacher_id == teacher_id)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    groups = (await db.execute(query.offset(skip).limit(limit).order_by(Group.start_date.desc()))).scalars().all()
    return PaginatedResponse.create(data=groups, total=total, skip=skip, limit=limit)


@router.get("/groups/{group_id}", response_model=GroupResponse, summary="Guruh to'liq ma'lumoti")
async def get_group(
    group_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyStaff],
):
    group = (await db.execute(select(Group).where(Group.id == group_id))).scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Guruh topilmadi")
    if current_user.role == UserRole.TEACHER and group.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Bu guruhga kirish huquqi yo'q")
    count = (await db.execute(
        select(func.count()).where(
            and_(Enrollment.group_id == group_id, Enrollment.status == EnrollmentStatus.ACTIVE)
        )
    )).scalar_one()
    result = GroupResponse.model_validate(group)
    result.enrolled_count = count
    return result


@router.post("/groups/", response_model=GroupResponse, status_code=201, summary="Yangi guruh")
async def create_group(
    data: GroupCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, ManagerOrAdmin],
):
    course = (await db.execute(select(Course).where(Course.id == data.course_id))).scalar_one_or_none()
    if not course:
        raise HTTPException(status_code=404, detail="Kurs topilmadi")
    if data.teacher_id:
        teacher = (await db.execute(
            select(User).where(User.id == data.teacher_id, User.role == UserRole.TEACHER)
        )).scalar_one_or_none()
        if not teacher:
            raise HTTPException(status_code=404, detail="O'qituvchi topilmadi yoki roli TEACHER emas")
    group = Group(
        **{k: v for k, v in data.model_dump().items() if k != "schedule"},
        schedule=[item.model_dump() for item in data.schedule],
    )
    db.add(group)
    await db.flush()
    await db.refresh(group)
    return group


@router.put("/groups/{group_id}", response_model=GroupResponse, summary="Guruhni yangilash")
async def update_group(
    group_id: uuid.UUID, data: GroupUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, ManagerOrAdmin],
):
    group = (await db.execute(select(Group).where(Group.id == group_id))).scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Guruh topilmadi")
    upd = data.model_dump(exclude_unset=True)
    if "schedule" in upd and data.schedule:
        upd["schedule"] = [i.model_dump() for i in data.schedule]
    for k, v in upd.items():
        setattr(group, k, v)
    await db.flush()
    await db.refresh(group)
    return group


# ── ENROLLMENTS ────────────────────────────────────────────────────────────────
@router.post("/groups/{group_id}/enroll", response_model=EnrollmentResponse, status_code=201, summary="O'quvchini guruhga qo'shish")
async def enroll_student(
    group_id: uuid.UUID, data: EnrollmentCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, ManagerOrAdmin],
):
    group = (await db.execute(select(Group).where(Group.id == group_id))).scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Guruh topilmadi")
    if group.status == GroupStatus.ARCHIVED:
        raise HTTPException(status_code=400, detail="Arxivlangan guruhga o'quvchi qo'shib bo'lmaydi")
    current_count = (await db.execute(
        select(func.count()).where(and_(Enrollment.group_id == group_id, Enrollment.status == EnrollmentStatus.ACTIVE))
    )).scalar_one()
    if current_count >= group.max_students:
        raise HTTPException(status_code=400, detail=f"Guruh to'ldi. Maksimal: {group.max_students}")
    existing = (await db.execute(
        select(Enrollment).where(and_(Enrollment.student_id == data.student_id, Enrollment.group_id == group_id))
    )).scalar_one_or_none()
    if existing:
        if existing.status == EnrollmentStatus.ACTIVE:
            raise HTTPException(status_code=409, detail="O'quvchi bu guruhda allaqachon faol")
        existing.status = EnrollmentStatus.ACTIVE
        existing.dropped_at = None
        await db.flush()
        await db.refresh(existing)
        return existing
    enrollment = Enrollment(
        student_id=data.student_id, group_id=group_id,
        discount_pct=data.discount_pct, notes=data.notes, enrolled_at=date.today(),
    )
    db.add(enrollment)
    await db.flush()
    await db.refresh(enrollment)
    return enrollment


@router.put("/enrollments/{enrollment_id}", response_model=EnrollmentResponse, summary="Enrollment holatini o'zgartirish")
async def update_enrollment(
    enrollment_id: uuid.UUID, data: EnrollmentUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, ManagerOrAdmin],
):
    enrollment = (await db.execute(select(Enrollment).where(Enrollment.id == enrollment_id))).scalar_one_or_none()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment topilmadi")
    upd = data.model_dump(exclude_unset=True)
    if upd.get("status") == EnrollmentStatus.DROPPED:
        upd["dropped_at"] = date.today()
    for k, v in upd.items():
        setattr(enrollment, k, v)
    await db.flush()
    await db.refresh(enrollment)
    return enrollment


@router.get("/groups/{group_id}/students", response_model=list[EnrollmentResponse], summary="Guruh o'quvchilari")
async def group_students(
    group_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyStaff],
    enroll_status: Optional[EnrollmentStatus] = Query(EnrollmentStatus.ACTIVE, alias="status"),
):
    query = select(Enrollment).where(Enrollment.group_id == group_id)
    if enroll_status:
        query = query.where(Enrollment.status == enroll_status)
    return (await db.execute(query)).scalars().all()
