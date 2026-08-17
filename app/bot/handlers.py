from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.student import Parent, Student
from app.models.iot import Attendance, AttendanceStatus
from app.models.academic import Enrollment
from app.models.finance import Payment
from app.bot.states import RegistrationState
from app.bot.keyboards import contact_keyboard, main_menu_keyboard
from sqlalchemy.orm import selectinload

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    async with AsyncSessionLocal() as session:
        # Check if user already exists
        result = await session.execute(select(Parent).where(Parent.telegram_id == message.from_user.id))
        parent = result.scalar_one_or_none()

        if parent:
            await message.answer(
                f"Assalomu alaykum, {parent.full_name}!\nEduCRM tizimiga xush kelibsiz.",
                reply_markup=main_menu_keyboard()
            )
            await state.clear()
        else:
            await message.answer(
                "Assalomu alaykum!\nBotdan foydalanish uchun telefon raqamingizni tasdiqlashingiz kerak.\nIltimos, pastdagi tugmani bosing:",
                reply_markup=contact_keyboard()
            )
            await state.set_state(RegistrationState.waiting_for_contact)


@router.message(RegistrationState.waiting_for_contact, F.contact)
async def process_contact(message: Message, state: FSMContext):
    contact = message.contact
    # Format phone number: remove '+' and spaces if any
    phone = contact.phone_number.replace("+", "").replace(" ", "")
    # Add + if it's missing in DB format (assume DB stores as +9989X or 9989X)
    # Let's search using ilike to be safe, or direct match
    if not phone.startswith("+"):
        phone_with_plus = f"+{phone}"
    else:
        phone_with_plus = phone
        phone = phone.replace("+", "")

    async with AsyncSessionLocal() as session:
        # Find parent by phone
        result = await session.execute(
            select(Parent).where((Parent.phone == phone) | (Parent.phone == phone_with_plus))
        )
        parent = result.scalar_one_or_none()

        if parent:
            parent.telegram_id = message.from_user.id
            parent.is_bot_active = True
            await session.commit()

            await message.answer(
                f"Raqamingiz muvaffaqiyatli tasdiqlandi!\nXush kelibsiz, {parent.full_name}.",
                reply_markup=main_menu_keyboard()
            )
            await state.clear()
        else:
            await message.answer(
                "Bunday raqam o'quv markazimiz bazasidan topilmadi. "
                "Iltimos, ma'muriyatga ulanib telefon raqamingizni to'g'irlating.",
                reply_markup=ReplyKeyboardRemove()
            )


@router.message(F.text == "👦 Farzandlarim")
async def my_children(message: Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Parent).where(Parent.telegram_id == message.from_user.id))
        parent = result.scalar_one_or_none()

        if not parent:
            return await message.answer("Siz ro'yxatdan o'tmagansiz. Iltimos /start ni bosing.")

        # Get students with enrollments
        st_result = await session.execute(
            select(Student)
            .options(selectinload(Student.enrollments).selectinload(Enrollment.group))
            .where(Student.parent_id == parent.id)
        )
        students = st_result.scalars().all()

        if not students:
            return await message.answer("Sizga biriktirilgan farzandlar topilmadi.")

        text = "Sizning farzandlaringiz:\n\n"
        for st in students:
            text += f"👤 Ismi: <b>{st.full_name}</b>\n"
            
            # Active groups
            active_groups = [enr.group.name for enr in st.enrollments if enr.status.value == "active"]
            if active_groups:
                text += f"📚 Guruhlari: {', '.join(active_groups)}\n"
                
            text += f"💳 Balansi: {st.balance:,.0f} so'm\n"
            text += f"📊 Holati: {st.status.value}\n\n"
        
        await message.answer(text, parse_mode="HTML")


@router.message(F.text == "💰 To'lov holati")
async def payments_status(message: Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Parent).where(Parent.telegram_id == message.from_user.id))
        parent = result.scalar_one_or_none()

        if not parent:
            return await message.answer("Siz ro'yxatdan o'tmagansiz. Iltimos /start ni bosing.")

        st_result = await session.execute(select(Student).where(Student.parent_id == parent.id))
        students = st_result.scalars().all()

        if not students:
            return await message.answer("Sizga biriktirilgan farzandlar topilmadi.")

        text = "💰 To'lov holati va tarixi:\n\n"
        for st in students:
            text += f"👦 O'quvchi: <b>{st.full_name}</b>\n"
            text += f"💳 Joriy balans: <b>{st.balance:,.0f} so'm</b>\n\n"
            
            pay_result = await session.execute(
                select(Payment)
                .where(Payment.student_id == st.id)
                .order_by(Payment.created_at.desc())
                .limit(3)
            )
            payments = pay_result.scalars().all()

            if not payments:
                text += "   Hali to'lovlar amalga oshirilmagan.\n\n"
                continue

            text += "   <i>Oxirgi to'lovlar:</i>\n"
            for pay in payments:
                date_str = pay.created_at.strftime("%d.%m.%Y %H:%M")
                method = pay.method.value.upper()
                text += f"   💵 {pay.amount:,.0f} so'm ({date_str}) - {method}\n"
            text += "\n"

        await message.answer(text, parse_mode="HTML")


@router.message(F.text == "📅 Davomat")
async def attendance_status(message: Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Parent).where(Parent.telegram_id == message.from_user.id))
        parent = result.scalar_one_or_none()

        if not parent:
            return await message.answer("Siz ro'yxatdan o'tmagansiz. Iltimos /start ni bosing.")

        st_result = await session.execute(select(Student).where(Student.parent_id == parent.id))
        students = st_result.scalars().all()

        if not students:
            return await message.answer("Sizga biriktirilgan farzandlar topilmadi.")

        text = "📅 Davomat tarixi:\n\n"
        for st in students:
            text += f"👦 O'quvchi: <b>{st.full_name}</b>\n"
            
            att_result = await session.execute(
                select(Attendance)
                .options(selectinload(Attendance.lesson))
                .where(Attendance.student_id == st.id)
                .order_by(Attendance.created_at.desc())
                .limit(5)
            )
            attendances = att_result.scalars().all()

            if not attendances:
                text += "   Hozircha davomat ma'lumotlari yo'q.\n\n"
                continue

            for att in attendances:
                date_str = att.lesson.lesson_date.strftime("%d.%m.%Y")
                if att.status == AttendanceStatus.PRESENT:
                    status_emoji = "✅ Keldi"
                elif att.status == AttendanceStatus.ABSENT:
                    status_emoji = "❌ Kelmadi"
                elif att.status == AttendanceStatus.LATE:
                    status_emoji = "⏰ Kechikdi"
                elif att.status == AttendanceStatus.EXCUSED:
                    status_emoji = "📝 Sababli"
                else:
                    status_emoji = str(att.status.value)

                time_str = f" (Vaqt: {att.check_in_time.strftime('%H:%M')})" if att.check_in_time else ""
                
                text += f"   🔹 {date_str} - {status_emoji}{time_str}\n"
            text += "\n"

        await message.answer(text, parse_mode="HTML")


@router.message(F.text == "📞 Markaz bilan aloqa")
async def contact_admin(message: Message):
    await message.answer(
        "O'quv markazimiz ma'muriyati bilan aloqa:\n\n"
        "📞 Telefon: +998 90 123 45 67\n"
        "💬 Telegram: @admin_username\n"
        "📍 Manzil: Toshkent sh., Chilonzor tumani"
    )

