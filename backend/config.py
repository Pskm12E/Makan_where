from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

class Config:
    DEBUG = True
    SECRET_KEY = "makanwheresg-demo-key"
    SQLALCHEMY_DATABASE_URI = "mysql+pymysql://root:password@localhost:3306/makanwheresg"
    MONGO_URI = "mongodb://localhost:27017"
    MONGO_DB_NAME = "makanwheresg"
