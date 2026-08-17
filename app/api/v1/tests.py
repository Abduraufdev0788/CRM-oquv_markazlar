import uuid
import json
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None
import google.generativeai as genai

from app.config import settings
from app.database import get_db
from app.models.user import User, UserRole
from app.models.student import Student
from app.models.academic import Test, TestResult, Group, Enrollment
from app.core.dependencies import require_roles, get_current_user, get_current_user_or_student
from app.schemas.academic import TestCreate, TestResponse, TestResultResponse, TestUpdate, TestSubmit
from app.schemas.base import PaginatedResponse, MessageResponse
from datetime import datetime, timezone

router = APIRouter(prefix="/tests", tags=["Tests (Testlar)"])

AnyStaff = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.TEACHER))


@router.post("/", response_model=TestResponse, status_code=201, summary="Yangi test yaratish")
async def create_test(
    data: TestCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyStaff],
):
    group = (await db.execute(select(Group).where(Group.id == data.group_id))).scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Guruh topilmadi")
        
    if current_user.role == UserRole.TEACHER and group.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Siz faqat o'zingizning guruhingizga test yarata olasiz")

    # Serialize questions to dict list
    questions_data = [q.model_dump() for q in data.questions]

    test = Test(
        group_id=data.group_id,
        title=data.title,
        description=data.description,
        questions=questions_data,
        max_score=data.max_score,
        is_active=data.is_active,
        start_time=data.start_time,
        end_time=data.end_time,
        teacher_id=current_user.id
    )
    db.add(test)
    await db.commit()
    
    test = (await db.execute(
        select(Test)
        .options(
            selectinload(Test.teacher), 
            selectinload(Test.group).selectinload(Group.course),
            selectinload(Test.group).selectinload(Group.room)
        )
        .where(Test.id == test.id)
    )).scalar_one()
    
    return test


@router.get("/", response_model=PaginatedResponse[TestResponse], summary="Testlar ro'yxati")
async def list_tests(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | Student, Depends(get_current_user_or_student)],
    group_id: Optional[uuid.UUID] = Query(None),
    skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
):
    query = select(Test).options(
        selectinload(Test.teacher), 
        selectinload(Test.group).selectinload(Group.course),
        selectinload(Test.group).selectinload(Group.room)
    )
    
    if isinstance(current_user, User) and current_user.role == UserRole.TEACHER:
        teacher_groups = (await db.execute(select(Group.id).where(Group.teacher_id == current_user.id))).scalars().all()
        query = query.where(Test.group_id.in_(teacher_groups))
        
    elif isinstance(current_user, Student):
        student_groups = (await db.execute(
            select(Enrollment.group_id).where(Enrollment.student_id == current_user.id)
        )).scalars().all()
        query = query.where(Test.group_id.in_(student_groups), Test.is_active == True)
        
    if group_id:
        query = query.where(Test.group_id == group_id)
        
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    tests = (await db.execute(query.offset(skip).limit(limit).order_by(Test.created_at.desc()))).scalars().all()
    
    if isinstance(current_user, Student) and tests:
        test_ids = [t.id for t in tests]
        results_counts = (await db.execute(
            select(TestResult.test_id, func.count(TestResult.id))
            .where(TestResult.test_id.in_(test_ids), TestResult.student_id == current_user.id)
            .group_by(TestResult.test_id)
        )).all()
        
        counts_map = {row[0]: row[1] for row in results_counts}
        for test in tests:
            test.attempts_used = counts_map.get(test.id, 0)
    
    return PaginatedResponse.create(data=tests, total=total, skip=skip, limit=limit)


@router.get("/{test_id}", response_model=TestResponse, summary="Test tafsilotlari")
async def get_test(
    test_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | Student, Depends(get_current_user_or_student)],
):
    test = (await db.execute(
        select(Test)
        .options(
            selectinload(Test.teacher), 
            selectinload(Test.group).selectinload(Group.course),
            selectinload(Test.group).selectinload(Group.room)
        )
        .where(Test.id == test_id)
    )).scalar_one_or_none()
    
    if not test:
        raise HTTPException(status_code=404, detail="Test topilmadi")
        
    if isinstance(current_user, Student):
        # Check how many times they submitted
        result_count = (await db.execute(
            select(func.count(TestResult.id)).where(TestResult.test_id == test_id, TestResult.student_id == current_user.id)
        )).scalar_one()
        
        if result_count < test.max_attempts:
            # SQLAlchemy session dan uzamiz, shunda qirqib olingan savollar bazaga yozilib ketmaydi
            db.expunge(test)
            
            test.attempts_used = result_count
            
            # Only strip correct_answer if they haven't submitted yet
            sanitized_questions = []
            for q in test.questions:
                q_copy = dict(q)
                q_copy.pop("correct_answer", None)
                sanitized_questions.append(q_copy)
            test.questions = sanitized_questions
        else:
            # Agar urinishlar tugagan bo'lsa, faqat ishlagan (javob belgilagan) savollarining to'g'ri javobini ko'rsatamiz
            db.expunge(test)
            test.attempts_used = result_count
            
            # O'quvchining so'nggi natijasini olamiz
            latest_result = (await db.execute(
                select(TestResult)
                .where(TestResult.test_id == test_id, TestResult.student_id == current_user.id)
                .order_by(TestResult.created_at.desc())
                .limit(1)
            )).scalar_one_or_none()
            
            attempted_indices = set()
            if latest_result and latest_result.answers:
                attempted_indices = set(latest_result.answers.keys())
                
            sanitized_questions = []
            for i, q in enumerate(test.questions):
                q_copy = dict(q)
                # Agar savolga javob berilmagan bo'lsa, to'g'ri javobni yashiramiz
                if str(i) not in attempted_indices:
                    q_copy.pop("correct_answer", None)
                sanitized_questions.append(q_copy)
            test.questions = sanitized_questions
            
    return test


@router.delete("/{test_id}", response_model=MessageResponse, summary="Testni o'chirish")
async def delete_test(
    test_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyStaff],
):
    test = (await db.execute(select(Test).where(Test.id == test_id))).scalar_one_or_none()
    
    if not test:
        raise HTTPException(status_code=404, detail="Test topilmadi")
        
    if current_user.role == UserRole.TEACHER and test.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Boshqa o'qituvchining testini o'chira olmaysiz")
            
    await db.delete(test)
    await db.commit()
    
    return MessageResponse(detail="Test muvaffaqiyatli o'chirildi")


@router.get("/{test_id}/results", response_model=PaginatedResponse[TestResultResponse], summary="Test natijalari")
async def get_test_results(
    test_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyStaff],
    skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200),
):
    test = (await db.execute(select(Test).where(Test.id == test_id))).scalar_one_or_none()
    if not test:
        raise HTTPException(status_code=404, detail="Test topilmadi")
        
    if current_user.role == UserRole.TEACHER and test.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Siz bu test natijalarini ko'ra olmaysiz")

    query = select(TestResult).options(selectinload(TestResult.student)).where(TestResult.test_id == test_id)
    
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    results = (await db.execute(query.offset(skip).limit(limit).order_by(TestResult.score.desc()))).scalars().all()
    
    return PaginatedResponse.create(data=results, total=total, skip=skip, limit=limit)


@router.put("/{test_id}", response_model=TestResponse, summary="Testni tahrirlash")
async def update_test(
    test_id: uuid.UUID,
    data: TestUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, AnyStaff],
):
    test = (await db.execute(select(Test).where(Test.id == test_id))).scalar_one_or_none()
    if not test:
        raise HTTPException(status_code=404, detail="Test topilmadi")
        
    if current_user.role == UserRole.TEACHER and test.teacher_id != current_user.id:
        raise HTTPException(status_code=403, detail="Siz faqat o'zingizning testingizni tahrirlay olasiz")

    update_data = data.model_dump(exclude_unset=True)
    
    if "questions" in update_data:
        update_data["questions"] = [q for q in update_data["questions"]]

    for key, value in update_data.items():
        setattr(test, key, value)
        
    # JSONB ustun o'zgarganini SQLAlchemy-ga majburiy bildirish
    from sqlalchemy.orm.attributes import flag_modified
    if "questions" in update_data:
        flag_modified(test, "questions")
        
    await db.commit()
    await db.refresh(test)
    
    test = (await db.execute(
        select(Test)
        .options(
            selectinload(Test.teacher), 
            selectinload(Test.group).selectinload(Group.course),
            selectinload(Test.group).selectinload(Group.room)
        )
        .where(Test.id == test.id)
    )).scalar_one()
    
    return test


@router.post("/{test_id}/submit", response_model=TestResultResponse, summary="Testni yakunlash va natijani saqlash")
async def submit_test(
    test_id: uuid.UUID,
    data: TestSubmit,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[Student, Depends(get_current_user_or_student)],
):
    if not isinstance(current_user, Student):
        raise HTTPException(status_code=403, detail="Faqat o'quvchilar test yechishi mumkin")
        
    test = (await db.execute(select(Test).where(Test.id == test_id))).scalar_one_or_none()
    if not test:
        raise HTTPException(status_code=404, detail="Test topilmadi")
        
    if not test.is_active:
        raise HTTPException(status_code=400, detail="Test faol emas")
        
    now = datetime.now(timezone.utc)
    if test.start_time and now < test.start_time:
        raise HTTPException(status_code=400, detail="Test hali boshlanmagan")
    
    # 2 daqiqa "grace period" (kechikib yetib kelishiga ruxsat)
    from datetime import timedelta
    if test.end_time and now > (test.end_time + timedelta(minutes=2)):
        raise HTTPException(status_code=400, detail="Test vaqti tugagan")
        
    # Check if student already exhausted attempts
    result_count = (await db.execute(select(func.count(TestResult.id)).where(TestResult.test_id == test_id, TestResult.student_id == current_user.id))).scalar_one()
    if result_count >= test.max_attempts:
        # Tizim xato bermasdan oxirgi natijani qaytarishi kerak
        result = (await db.execute(
            select(TestResult)
            .options(selectinload(TestResult.student))
            .where(TestResult.test_id == test_id, TestResult.student_id == current_user.id)
            .order_by(TestResult.created_at.desc())
            .limit(1)
        )).scalar_one()
        return result
        
    # Calculate score
    correct_count = 0
    total_questions = len(test.questions)
    
    for i, q in enumerate(test.questions):
        student_ans = data.answers.get(str(i))
        if student_ans is not None and student_ans == q.get("correct_answer"):
            correct_count += 1
            
    # Score calculation (e.g., percentage based on max_score)
    score = int((correct_count / total_questions) * test.max_score) if total_questions > 0 else 0
    
    result = TestResult(
        test_id=test_id,
        student_id=current_user.id,
        score=score,
        answers=data.answers
    )
    db.add(result)
    await db.commit()
    await db.refresh(result)
    
    result = (await db.execute(
        select(TestResult).options(selectinload(TestResult.student)).where(TestResult.id == result.id)
    )).scalar_one()
    
    return result


@router.post("/generate-ai", summary="AI orqali PDF dan test yaratish")
async def generate_tests_from_pdf(
    file: UploadFile = File(...),
    current_user: User = AnyStaff,
):
    if not settings.GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="Gemini API kaliti sozlanmagan")
    if fitz is None:
        raise HTTPException(status_code=500, detail="PyMuPDF o'rnatilmagan")
        
    try:
        content = await file.read()
        doc = fitz.open(stream=content, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
            if len(text) > 500000: # Limit length to avoid huge tokens
                break
                
        if not text.strip():
            raise HTTPException(status_code=400, detail="PDF dan matn o'qib bo'lmadi")
            
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-flash-latest')
        
        prompt = f"""
        Quyidagi matn asosida barcha muhim ma'lumotlarni qamrab oluvchi iloji boricha ko'p (maksimal) test savollarini tuzib ber.
        Har bir savol 4 ta variantdan (A, B, C, D) iborat bo'lsin.
        Javobni FAQAT qat'iy JSON formatida qaytar. Hech qanday qo'shimcha izoh yoki matn kerak emas.
        Format quyidagicha bo'lishi shart:
        [
          {{
            "text": "Savol matni?",
            "type": "choice",
            "options": ["A variant", "B variant", "C variant", "D variant"],
            "correct_answer": 0 
          }}
        ]
        "correct_answer" qiymati to'g'ri variantning indeksi (0 dan 3 gacha) bo'lishi kerak.
        
        Matn:
        {text[:500000]}
        """
        
        response = model.generate_content(prompt)
        result_text = response.text
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()
            
        questions = json.loads(result_text)
        return {"questions": questions}
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="AI no'to'g'ri javob formatini qaytardi")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI xatosi: {str(e)}")
