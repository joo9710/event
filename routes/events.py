import json
from typing import List
from fastapi import APIRouter, Body, Depends, File, Form, Path, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlmodel import select
from auth.authenticate import authenticate
from database.connection import get_session
from models.events import Event, EventUpdate
import os
import boto3
from uuid import uuid4
from database.connection import settings
event_router = APIRouter(tags=["Event"])



# pathlib 모듈의 Path 클래스를 FilePath 이름으로 사용
from pathlib import Path as FilePath
#FILE_DIR = FilePath("C:/temp/uploads")
# FILE_DIR = FilePath("C:/temp/uploads"1)
FILE_DIR = FilePath("/app/uploads")
FILE_DIR.mkdir(exist_ok=True)


# S3 설정
AWS_ACCESS_KEY_ID = settings.AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY = settings.AWS_SECRET_ACCESS_KEY

S3_BUCKET = os.getenv("S3_BUCKET_NAME", "mini3bucket-crcl")
S3_REGION = os.getenv("AWS_REGION", "ap-northeast-2")

s3_client = boto3.client(
    "s3",
    region_name=S3_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

# 이벤트 전체 조회  /events/ => retrive_all_events()
@event_router.get("/", response_model=List[Event])
async def retrive_all_events(session = Depends(get_session)) -> List[Event]:
   statement = select(Event)
   events = session.exec(statement)
   return events

# 이벤트 상세 조회  /events/{event_id} => retrive_event(event_id)
@event_router.get("/{event_id}", response_model=Event)
async def retrive_event(event_id: int, session = Depends(get_session)) -> Event:
    event = session.get(Event, event_id)
    if event:
        return event

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="일치하는 이벤트를 찾을 수 없습니다."
    )

# 이벤트 등록       /events/ => create_event()
# @event_router.post("/", status_code=status.HTTP_201_CREATED)
# #async def create_event(data: Event = Body(...), user_id = Depends(authenticate), session = Depends(get_session)) -> dict:
# async def create_event(
#         data = Form(...),                   # Form으로 전달된 데이터
#         user_id = Depends(authenticate),    # 인증된 사용자 ID
#         image: UploadFile = File(...),       # 업로드된 파일 정보를 저장할 변수   
#         session = Depends(get_session)      # DB 세션
#     ) -> dict:

#     # 전달된 데이터를 JSON 형식으로 변환 후 Event 모델에 맞게 변환
#     data = json.loads(data)
#     data = Event(**data)
    
#     # 파일을 저장
#     file_path = FILE_DIR / image.filename
#     with open(file_path, "wb") as file:
#         file.write(image.file.read())

#     # 파일 경로를 Event 모델의 image 필드에 저장
#     data.image = str(file_path)

#     data.user_id = user_id
#     session.add(data)
#     session.commit()
#     session.refresh(data)

#     return {"message": "이벤트 등록이 완료되었습니다."}

# 이벤트 하나 삭제  /events/{event_id} => delete_event(event_id)

# 이미지등록 (s3 파일 업로드)



@event_router.post("/", status_code=status.HTTP_201_CREATED)
async def create_event(
    data = Form(...),                   # Form으로 전달된 JSON 문자열
    user_id = Depends(authenticate),   # 인증된 사용자 ID
    image: UploadFile = File(...),     # 업로드된 파일
    session = Depends(get_session)     # DB 세션
) -> dict:
    # 1. JSON 데이터 파싱
    try:
        data = json.loads(data)
        event_data = Event(**data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"데이터 파싱 오류: {str(e)}")

    # 2. S3에 파일 업로드
    try:
        file_extension = os.path.splitext(image.filename)[1]
        s3_key = f"events/{uuid4()}{file_extension}"

        s3_client.upload_fileobj(
            image.file,
            S3_BUCKET,
            s3_key,
            ExtraArgs={"ContentType": image.content_type}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"S3 업로드 실패: {str(e)}")

    # 3. S3 URL 생성 후 event 데이터에 저장
    s3_url = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{s3_key}"
    event_data.image = s3_url
    event_data.user_id = user_id

    # 4. DB에 저장
    try:
        session.add(event_data)
        session.commit()
        session.refresh(event_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB 저장 실패: {str(e)}")

    return {"message": "이벤트 등록이 완료되었습니다.", "event_id": event_data.id}

@event_router.delete("/{event_id}")
async def delete_event(event_id: int, session = Depends(get_session)) -> dict:
    event = session.get(Event, event_id)
    if event:
        session.delete(event)
        session.commit()
        return {"message": "이벤트 삭제가 완료되었습니다."}
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="일치하는 이벤트를 찾을 수 없습니다."
    )

# 이벤트 전체 삭제  /events/ => delete_all_events()
@event_router.delete("/")
async def delete_all_events(session = Depends(get_session)) -> dict:
    statement = select(Event)
    events = session.exec(statement)
    for event in events:
        session.delete(event)
    session.commit()

    return {"message": "이벤트 전체 삭제가 완료되었습니다."}

# 이벤트 수정      /events/{event_id} => update_event(event_id)
@event_router.put("/{event_id}", response_model=Event)
async def update_event(data: EventUpdate, event_id: int = Path(...), session = Depends(get_session)) -> Event:
    event = session.get(Event, event_id)
    if event:
        event_data = data.model_dump(exclude_unset=True)

        for key, value in event_data.items():
            setattr(event, key, value)

        session.add(event)
        session.commit()    
        session.refresh(event)

        return event
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="일치하는 이벤트를 찾을 수 없습니다."
    )


# @event_router.get("/download/{event_id}")
# async def download_file(event_id: int, session = Depends(get_session)):
#     event = session.get(Event, event_id)
#     if not event:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="이벤트를 찾을 수 없습니다."
#         )        
    
#     file_path = event.image
#     if not FilePath(file_path).exists():
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="파일을 찾을 수 없습니다."
#         )
    
#     return FileResponse(file_path, media_type="application/octet-stream", filename=FilePath(file_path).name)

@event_router.get("/download/{event_id}")
async def download_file(event_id: int, session = Depends(get_session)):
    event = session.get(Event, event_id)
    if not event or not event.image:
        raise HTTPException(status_code=404, detail="이벤트 또는 이미지가 없습니다.")

    return RedirectResponse(event.image)  # 클라이언트가 직접 이미지 URL로 이동