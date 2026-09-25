from .seed import seed
from .database import Base, engine

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    seed()
    print("Database ready")
