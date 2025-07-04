from typing import Optional
from pydantic_settings import BaseSettings
from sqlmodel import SQLModel, create_engine, Session

class Settings(BaseSettings):
    DATABASE_URL: Optional[str] = None
    SECRET_KEY: Optional[str] = None
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    naver_client_id: str
    naver_client_secret: str
    naver_redirect_uri: str    
    print(SECRET_KEY)
    
    class Config:
        env_file = ".env"

settings = Settings()
    
#database_connection_string = "mysql+pymysql://fastapiuser:p%40ssw0rd@localhost:3306/fastapidb"
engine_url = create_engine(
    settings.DATABASE_URL,
    echo=True,
)

def conn():
    SQLModel.metadata.create_all(engine_url)

def get_session():
    with Session(engine_url) as session:
        yield session