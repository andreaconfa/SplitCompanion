from fastapi import APIRouter, Request, Response, HTTPException
from sqlmodel import select
from app.auth import DB, CurrentUser, Admin, hasher, verify_password, create_session, DUMMY_HASH
from app.config import get_settings
from app.models import User, now
from app.schemas import PasswordChange, Login, AuthResponse, UserCreate, UserUpdate, UserResponse
from app.services.access import get_or_404
from app.services.instance_settings import public_settings

router = APIRouter(prefix="/api")


@router.post("/auth/login", response_model=None)
def login(data: Login, request: Request, response: Response, s: DB):
    from app.services.mfa_service import throttle, issue_challenge

    throttle(s, request, "password", data.username.strip().lower())
    user = s.exec(select(User).where(User.username == data.username.strip().lower())).first()
    valid = verify_password(user.password_hash if user else DUMMY_HASH, data.password)
    if not user or not valid or not user.is_active:
        raise HTTPException(401, "Username o password non corretti.")
    if hasher.check_needs_rehash(user.password_hash):
        user.password_hash = hasher.hash(data.password)
        s.add(user)
    if get_settings().mfa_required or user.mfa_enabled:
        response.delete_cookie("split_session", path="/")
        return issue_challenge(s, user)
    return finish_login(s, user, request, response)


def finish_login(s, user, request, response, mfa_verified=False):
    from app.api.push import revoke_browser

    revoke_browser(s, request, response, new_user_id=user.id)
    token, csrf = create_session(s, user, mfa_verified=mfa_verified)
    cfg = get_settings()
    response.set_cookie(
        "split_session",
        token,
        httponly=True,
        samesite="lax",
        secure=cfg.secure_cookie or request.url.scheme == "https",
        max_age=cfg.session_hours * 3600,
        path="/",
    )
    return AuthResponse(
        user=UserResponse.model_validate(user),
        csrf_token=csrf,
        timezone=cfg.timezone,
        **public_settings(s),
    )


@router.get("/auth/me", response_model=AuthResponse)
def me(request: Request, user: CurrentUser, s: DB):
    return AuthResponse(
        user=UserResponse.model_validate(user),
        csrf_token=request.state.auth.csrf_token,
        timezone=get_settings().timezone,
        **public_settings(s),
    )


@router.post("/auth/logout")
def logout(request: Request, response: Response, user: CurrentUser, s: DB):
    from app.api.push import revoke_session, revoke_browser

    revoke_browser(s, request, response)
    revoke_session(s, request.state.auth.token_hash)
    s.delete(request.state.auth)
    response.delete_cookie("split_session", path="/")
    return {"ok": True}


@router.post("/auth/password")
def change_password(
    data: PasswordChange, request: Request, response: Response, user: CurrentUser, s: DB
):
    from app.auth import current_user
    from app.services.mfa_service import throttle, verify_factor, revoke_user_auth

    # Persist attempts, then recheck the session after reacquiring the write lock.
    throttle(s, request, "mfa", str(user.id))
    s.expire_all()
    user = current_user(request, s)
    if not verify_password(user.password_hash, data.current_password):
        raise HTTPException(401, "Password attuale o codice di verifica non valido.")
    if data.current_password == data.new_password:
        raise HTTPException(422, "Scegli una password diversa da quella attuale.")
    if user.mfa_enabled and (not data.code or not verify_factor(s, user, data.code)):
        raise HTTPException(
            401, "Password attuale o codice di verifica non valido. Usa un codice nuovo."
        )
    user.password_hash = hasher.hash(data.new_password)
    user.updated_at = now()
    s.add(user)
    revoke_user_auth(s, user.id)
    response.delete_cookie("split_session", path="/")
    response.delete_cookie("split_push_device", path="/")
    return {"ok": True}


@router.get("/users", response_model=list[UserResponse])
def users(user: CurrentUser, s: DB):
    return [
        UserResponse.model_validate(u)
        for u in s.exec(select(User).order_by(User.display_name)).all()
    ]


@router.post("/users", response_model=UserResponse, status_code=201)
def create_user(data: UserCreate, admin: Admin, s: DB):
    if s.exec(select(User).where(User.username == data.username)).first():
        raise HTTPException(409, "Username già utilizzato.")
    user = User(**data.model_dump(exclude={"password"}), password_hash=hasher.hash(data.password))
    s.add(user)
    s.flush()
    return UserResponse.model_validate(user)


@router.get("/users/{id}", response_model=UserResponse)
def get_user(id: int, user: CurrentUser, s: DB):
    return UserResponse.model_validate(get_or_404(s, User, id))


@router.patch("/users/{id}", response_model=UserResponse)
def update_user(id: int, data: UserUpdate, admin: Admin, s: DB):
    user = get_or_404(s, User, id)
    values = data.model_dump(exclude_unset=True)
    if any(v is None for v in values.values()):
        raise ValueError("I campi utente non possono essere vuoti.")
    if user.id == admin.id and (
        values.get("is_active") is False or values.get("is_admin") is False
    ):
        raise ValueError("Non puoi disabilitare o rimuovere i tuoi privilegi amministrativi.")
    if "password" in values:
        user.password_hash = hasher.hash(values.pop("password"))
    for key, value in values.items():
        setattr(user, key, value)
    user.updated_at = now()
    s.add(user)
    from app.services.mfa_service import revoke_user_auth

    revoke_user_auth(s, id)
    s.flush()
    return UserResponse.model_validate(user)
