"""
Permissions — RBAC dekoratorlari va ruxsat tekshiruv yordamchilari.
`dependencies.py` dagi `require_roles` ning qulay alias lari.
"""
from fastapi import Depends
from app.core.dependencies import require_roles, get_current_active_user
from app.models.user import UserRole

# ── Tayyor Dependency Alias lari ───────────────────────────────────────────────
AdminOnly = Depends(require_roles(UserRole.ADMIN))
ManagerOrAdmin = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER))
AnyStaff = Depends(require_roles(UserRole.ADMIN, UserRole.MANAGER, UserRole.TEACHER))
CurrentUser = Depends(get_current_active_user)


def is_owner_or_admin(resource_user_id, current_user) -> bool:
    """
    Resurs egasi yoki Admin ekanligini tekshirish.
    Misol: O'z profilini yoki Admin har kimning profilini o'zgartirishda.
    """
    return str(resource_user_id) == str(current_user.id) or current_user.role == UserRole.ADMIN


def teacher_owns_group(group_teacher_id, current_user) -> bool:
    """O'qituvchi faqat o'z guruhini boshqara olishini tekshirish."""
    if current_user.role in (UserRole.ADMIN, UserRole.MANAGER):
        return True
    return str(group_teacher_id) == str(current_user.id)
