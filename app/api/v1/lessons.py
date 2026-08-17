"""
Lessons, Homework, Grades API — /api/v1/lessons/
"""
import uuid
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User, UserRole
from app.models.lesson import Lesson, Homework, Grade
from app.models.academic import Group
from app.core.dependencies import require_roles
from app.schemas.lesson import (
    LessonCreate, LessonUpdate, LessonResponse, LessonBriefResponse,
    HomeworkCreate, HomeworkUpdate, HomeworkResponse,
    HomeworkSubmissionResponse,
    GradeCreate, GradeUpdate, GradeResponse, StudentGradeSummary,
)
from app.schemas.base import PaginatedResponse, MessageResponse

router = APIRouter(tags=["Lessons (Darslar va Baholar)"])

AnyStaff = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.TEACHER))
TeacherOrAbove = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.TEACHER))


# ═══════════════════════════════════════════════════════════════════════════════
# LESSONS
# ═══════════════════════════════════════════════════════════════════════════════
@router.get("/lessons/", response_model=PaginatedResponse[LessonResponse], summary="Darslar ro'yxati")
async def list_lessons(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyStaff],
    group_id: Optional[uuid.UUID] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=1000),
):
    query = select(Lesson)
    if group_id:
        query = query.where(Lesson.group_id == group_id)
    # O'qituvchi faqat o'z guruhlarini ko'radi
    if current_user.role == UserRole.TEACHER:
        teacher_groups = select(Group.id).where(Group.teacher_id == current_user.id)
        query = query.where(Lesson.group_id.in_(teacher_groups))

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    lessons = (await db.execute(query.offset(skip).limit(limit).order_by(Lesson.lesson_date.desc()))).scalars().all()
    return PaginatedResponse.create(data=lessons, total=total, skip=skip, limit=limit)


@router.post("/lessons/", response_model=LessonResponse, status_code=201, summary="Dars qayd etish")
async def create_lesson(
    data: LessonCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, TeacherOrAbove],
):
    # O'qituvchi faqat o'z guruhiga dars qo'sha oladi
    if current_user.role == UserRole.TEACHER:
        group = (await db.execute(
            select(Group).where(Group.id == data.group_id, Group.teacher_id == current_user.id)
        )).scalar_one_or_none()
        if not group:
            raise HTTPException(status_code=403, detail="Bu guruhda dars qo'sha olmaysiz")

    lesson = Lesson(**data.model_dump())
    db.add(lesson)
    await db.flush()
    await db.refresh(lesson)
    return lesson


@router.put("/lessons/{lesson_id}", response_model=LessonResponse, summary="Darsni yangilash")
async def update_lesson(
    lesson_id: uuid.UUID,
    data: LessonUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, TeacherOrAbove],
):
    lesson = (await db.execute(select(Lesson).where(Lesson.id == lesson_id))).scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="Dars topilmadi")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(lesson, key, value)
    await db.flush()
    await db.refresh(lesson)
    return lesson


# ═══════════════════════════════════════════════════════════════════════════════
# HOMEWORKS
# ═══════════════════════════════════════════════════════════════════════════════
@router.get("/lessons/{lesson_id}/homeworks", response_model=list[HomeworkResponse], summary="Darsning uy vazifalarini olish")
async def get_lesson_homeworks(
    lesson_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyStaff],
):
    hws = (await db.execute(select(Homework).where(Homework.lesson_id == lesson_id))).scalars().all()
    return hws

@router.post(
    "/lessons/{lesson_id}/homework",
    response_model=HomeworkResponse,
    status_code=201,
    summary="Uy vazifasi qo'shish",
)
async def create_homework(
    lesson_id: uuid.UUID,
    data: HomeworkCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, TeacherOrAbove],
):
    lesson = (await db.execute(select(Lesson).where(Lesson.id == lesson_id))).scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="Dars topilmadi")

    hw = Homework(lesson_id=lesson_id, **{k: v for k, v in data.model_dump().items() if k != "lesson_id"})
    db.add(hw)
    await db.flush()
    await db.refresh(hw)
    return hw


@router.put("/homework/{hw_id}", response_model=HomeworkResponse, summary="Uy vazifasini yangilash")
async def update_homework(
    hw_id: uuid.UUID,
    data: HomeworkUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, TeacherOrAbove],
):
    hw = (await db.execute(select(Homework).where(Homework.id == hw_id))).scalar_one_or_none()
    if not hw:
        raise HTTPException(status_code=404, detail="Uy vazifasi topilmadi")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(hw, key, value)
    await db.flush()
    await db.refresh(hw)
    return hw


# ═══════════════════════════════════════════════════════════════════════════════
# HOMEWORK SUBMISSIONS (TEACHER VIEW)
# ═══════════════════════════════════════════════════════════════════════════════
@router.get("/homework/{hw_id}/submissions", response_model=list[HomeworkSubmissionResponse], summary="Vazifa javoblarini ko'rish")
async def get_homework_submissions(
    hw_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, TeacherOrAbove],
):
    from app.models.lesson import HomeworkSubmission
    hw = (await db.execute(select(Homework).where(Homework.id == hw_id))).scalar_one_or_none()
    if not hw:
        raise HTTPException(status_code=404, detail="Uy vazifasi topilmadi")
    
    subs = (await db.execute(
        select(HomeworkSubmission)
        .options(selectinload(HomeworkSubmission.student))
        .where(HomeworkSubmission.homework_id == hw_id)
    )).scalars().all()
    return subs


# ═══════════════════════════════════════════════════════════════════════════════
# GRADES
# ═══════════════════════════════════════════════════════════════════════════════
@router.get("/grades/", response_model=PaginatedResponse[GradeResponse], summary="Baholar ro'yxati")
async def list_grades(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyStaff],
    student_id: Optional[uuid.UUID] = None,
    lesson_id: Optional[uuid.UUID] = None,
    group_id: Optional[uuid.UUID] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=1000),
):
    query = select(Grade)
    if student_id:
        query = query.where(Grade.student_id == student_id)
    if lesson_id:
        query = query.where(Grade.lesson_id == lesson_id)
    if group_id:
        query = query.join(Lesson).where(Lesson.group_id == group_id)

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    grades = (await db.execute(query.offset(skip).limit(limit))).scalars().all()
    return PaginatedResponse.create(data=grades, total=total, skip=skip, limit=limit)


@router.post("/grades/", response_model=GradeResponse, status_code=201, summary="Baho qo'yish")
async def create_grade(
    data: GradeCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, TeacherOrAbove],
):
    grade = Grade(**data.model_dump(), graded_by=current_user.id)
    db.add(grade)
    await db.flush()
    await db.refresh(grade)
    return grade


@router.put("/grades/{grade_id}", response_model=GradeResponse, summary="Bahoni tahrirlash")
async def update_grade(
    grade_id: uuid.UUID,
    data: GradeUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, TeacherOrAbove],
):
    if current_user.role == UserRole.TEACHER:
        raise HTTPException(status_code=403, detail="O'qituvchi qo'yilgan bahoni o'zgartira olmaydi")

    grade = (await db.execute(select(Grade).where(Grade.id == grade_id))).scalar_one_or_none()
    if not grade:
        raise HTTPException(status_code=404, detail="Baho topilmadi")
    if data.score and grade.max_score and data.score > grade.max_score:
        raise HTTPException(status_code=400, detail=f"Ball maksimal ({grade.max_score}) dan oshib ketdi")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(grade, key, value)
    await db.flush()
    await db.refresh(grade)
    return grade
