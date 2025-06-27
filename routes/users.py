from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import select
from auth.hash_password import HashPassword
from auth.jwt_handler import create_jwt_token
from database.connection import Settings, get_session
from models.users import User, UserSignIn, UserSignUp
import httpx
from database.connection import settings
from fastapi.responses import RedirectResponse


user_router = APIRouter(tags=["User"])


def get_settings():
    return settings

# users = {}

hash_password = HashPassword()

# 회원 가입(등록)
@user_router.post("/signup", status_code=status.HTTP_201_CREATED)
async def sign_new_user(data: UserSignUp, session = Depends(get_session)) -> dict:
    statement = select(User).where(User.email == data.email)
    user = session.exec(statement).first()
    if user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, 
            detail="동일한 사용자가 존재합니다.")
    
    new_user = User(
        email=data.email,
        password=hash_password.hash_password(data.password),
        username=data.username, 
        events=[]
    )
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    return {
        "message": "사용자 등록이 완료되었습니다.",
        "user": new_user
    }

# 로그인
@user_router.post("/signin")
async def sign_in(data: OAuth2PasswordRequestForm = Depends(), session = Depends(get_session)) -> dict:
    statement = select(User).where(User.email == data.username)
    user = session.exec(statement).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="사용자를 찾을 수 없습니다.")    

    # if user.password != data.password:
    if hash_password.verify_password(data.password, user.password) == False:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="패스워드가 일치하지 않습니다.")
    
    return {
        "message": "로그인에 성공했습니다. CICD test 성공",
        "username": user.username, 
        "access_token": create_jwt_token(user.email, user.id)
    }
    # return JSONResponse(    
    #     status_code=status.HTTP_200_OK,
    #     content={
    #         "message": "로그인에 성공했습니다.",
    #         "username": user.username, 
    #         "access_token": create_jwt_token(user.email, user.id)
    #     }
    # )


    # 네이버 아이디로 로그인

@user_router.get("/auth/naver/callback")
async def naver_callback(
    code: str = Query(...),
    state: str = Query(...),
    session=Depends(get_session),
    settings: Settings = Depends(get_settings)
):
    NAVER_CLIENT_ID = settings.naver_client_id
    NAVER_CLIENT_SECRET = settings.naver_client_secret
    NAVER_REDIRECT_URI = settings.naver_redirect_uri

    token_url = "https://nid.naver.com/oauth2.0/token"
    params = {
        "grant_type": "authorization_code",
        "client_id": NAVER_CLIENT_ID,
        "client_secret": NAVER_CLIENT_SECRET,
        "code": code,
        "state": state,
        "redirect_uri": NAVER_REDIRECT_URI,
    }

    async with httpx.AsyncClient(timeout=10) as client:
        token_resp = await client.get(token_url, params=params)
        print("토큰 응답:", token_resp.text)
    if token_resp.status_code != 200:
        raise HTTPException(status_code=token_resp.status_code, detail="Access token 요청 실패")
    token_data = token_resp.json()
    access_token = token_data.get("access_token")

    if not access_token:
        raise HTTPException(status_code=400, detail="Access token 획득 실패")

    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=10) as client:
        profile_resp = await client.get("https://openapi.naver.com/v1/nid/me", headers=headers)
    if profile_resp.status_code != 200:
        raise HTTPException(status_code=profile_resp.status_code, detail="프로필 정보 조회 실패")
    profile_data = profile_resp.json()

    if profile_data.get("resultcode") != "00":
        raise HTTPException(status_code=400, detail="프로필 정보 조회 실패")

    user_info = profile_data["response"]
    email = user_info.get("email")
    username = user_info.get("nickname")

    statement = select(User).where(User.email == email)
    user = session.exec(statement).first()
    print(f"네이버 프로필 email: {email}")
    print(f"DB에서 조회한 user: {user}")
    print(f"user is None? {user is None}")

    if not user:
    # 네이버 로그인으로 자동 가입 처리
        user = User(
            email=email,
            username=username,
            password="",  # 소셜 로그인은 비밀번호 없음
            events=[]
        )
        session.add(user)
        session.commit()
        session.refresh(user)

    token = create_jwt_token(user.email, user.id)

    # 클라이언트 앱으로 리디렉트 (토큰과 유저명 포함)
    redirect_url = f"http://13.124.75.129/:80/naver/callback?token={token}&username={user.username}"
    return RedirectResponse(url=redirect_url)
