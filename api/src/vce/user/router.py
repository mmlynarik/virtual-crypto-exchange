from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from vce.dependencies import DBSession
from vce.user import services
from vce.user.exceptions import UserAlreadyExists
from vce.user.repository import UsersRepository
from vce.user.schemas import UserCreateByEmail, UserCreateByGithub, UserCreated, UserResponse

router = APIRouter(tags=["users"])


@router.post("/users/email", response_class=JSONResponse)
async def register_user_by_email(user_create: UserCreateByEmail, session: DBSession) -> UserCreated:
    repo = UsersRepository(session)
    try:
        user = await services.register_user_by_email(user_create=user_create, repo=repo, session=session)
    except UserAlreadyExists:
        raise HTTPException(status_code=409, detail=f"User with email {user_create.email} already exists")
    return user


@router.post("/users/github", response_class=JSONResponse)
async def register_user_by_github(user_create: UserCreateByGithub, session: DBSession) -> UserCreated:
    repo = UsersRepository(session)
    try:
        user = await services.register_user_by_github(user_create=user_create, repo=repo, session=session)
    except UserAlreadyExists:
        raise HTTPException(
            status_code=409, detail=f"User with github_id {user_create.github_id} already exists"
        )
    return user


@router.get("/users/id/{id}")
async def get_user_by_id(id: int, session: DBSession) -> UserResponse:
    repo = UsersRepository(session)
    user = await services.get_user_by_id(id=id, repo=repo)
    if not user:
        raise HTTPException(status_code=404, detail=f"User with id {id} not found")

    return UserResponse.model_validate(user)


@router.get("/users/email/{email}")
async def get_user_by_email(email: str, session: DBSession) -> UserResponse:
    repo = UsersRepository(session)
    user = await services.get_user_by_email(email=email, repo=repo)
    if not user:
        raise HTTPException(status_code=404, detail=f"User with email {email} not found")

    return UserResponse.model_validate(user)


@router.get("/users/github/{github_id}")
async def get_user_by_github(github_id: int, session: DBSession) -> UserResponse:
    repo = UsersRepository(session)
    user = await services.get_user_by_github_id(github_id=github_id, repo=repo)
    if not user:
        raise HTTPException(status_code=404, detail=f"User with github id {github_id} not found")

    return UserResponse.model_validate(user)
