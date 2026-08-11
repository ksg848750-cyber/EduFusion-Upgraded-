from datetime import datetime, timezone
from fastapi import Depends, HTTPException, Header, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.database import get_database
from app.core.security import verify_jwt_token


async def get_current_user(
    authorization: str | None = Header(None, alias="Authorization"),
    db: AsyncIOMotorDatabase = Depends(get_database)
) -> dict:
    """
    FastAPI Security Dependency:
    1. Extracts 'Bearer <token>' from Authorization header.
    2. Validates token using verify_jwt_token.
    3. Resolves user in MongoDB 'users' collection by authUserId / sub.
    4. Auto-provisions user profile if token is valid but DB document is missing.
    5. Returns current user dict.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "MISSING_TOKEN", "message": "Authorization header is missing."}},
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "MALFORMED_HEADER", "message": "Authorization header must be 'Bearer <token>'."}},
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = parts[1]
    payload = verify_jwt_token(token)
    
    auth_user_id = payload.get("sub") or payload.get("id") or payload.get("authUserId")
    email = payload.get("email", "")
    name = payload.get("name", "Student")
    
    if not auth_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_PAYLOAD", "message": "Token payload missing user identifier."}},
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Query MongoDB for user record
    users_collection = db["users"]
    user_doc = await users_collection.find_one({"authUserId": str(auth_user_id)})
    
    now_iso = datetime.now(timezone.utc).isoformat()
    
    if not user_doc:
        # Auto-provision user record in MongoDB Atlas
        new_user = {
          "authUserId": str(auth_user_id),
          "email": email,
          "name": name,
          "interests": payload.get("interests", ["technology"]),
          "preferences": {
              "language": "en",
              "educationLevel": "undergraduate",
              "studyClass": "btech-3"
          },
          "isOnboarded": True,
          "createdAt": now_iso,
          "updatedAt": now_iso
        }
        result = await users_collection.insert_one(new_user)
        new_user["_id"] = str(result.inserted_id)
        user_doc = new_user
    else:
        user_doc["_id"] = str(user_doc["_id"])
        
    return user_doc
