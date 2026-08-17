from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def contact_keyboard() -> ReplyKeyboardMarkup:
    """Ota-onalardan telefon raqam so'rash uchun klaviatura."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📞 Telefon raqamni yuborish", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Asosiy menyu klaviaturasi."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👦 Farzandlarim"), KeyboardButton(text="💰 To'lov holati")],
            [KeyboardButton(text="📅 Davomat"), KeyboardButton(text="📞 Markaz bilan aloqa")]
        ],
        resize_keyboard=True
    )
