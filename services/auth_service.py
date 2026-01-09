# app/services/auth_service.py
from datetime import datetime
from sqlalchemy.orm import Session
from typing import Dict, Optional

from models.user import User

class AuthService:
    """认证服务"""
    
    @staticmethod
    async def login_user(
        db: Session, 
        username: str, 
        password: str
    ) -> Dict[str, any]:
        """
        用户登录验证
        
        Args:
            db: 数据库会话
            username: 用户名
            password: 密码
        
        Returns:
            包含登录结果的字典
        """
        # 1. 查找用户
        user = await AuthService.get_user_by_username(db, username)
        
        # 2. 验证用户是否存在
        if not user:
            return {
                "success": False,
                "error": "用户名不存在"
            }
        
        # 3. 验证密码（这里使用明文比较，实际应该使用哈希）
        if not AuthService.verify_password(user.password, password):
            return {
                "success": False,
                "error": "密码错误"
            }
        
        # 4. 验证用户状态（如果有的话）
        if hasattr(user, 'is_active') and not user.is_active:
            return {
                "success": False,
                "error": "用户已被禁用"
            }
        
        # 5. 登录成功，返回用户信息
        return {
            "success": True,
            "user_id": user.id,
            "username": user.username,
            "login_time": datetime.now().isoformat()
        }
    
    @staticmethod
    async def get_user_by_username(db: Session, username: str) -> Optional[User]:
        """根据用户名获取用户"""
        return db.query(User).filter(User.username == username).first()
    
    @staticmethod
    def verify_password(stored_password: str, provided_password: str) -> bool:
        """
        验证密码
        
        TODO: 实际应用中应该使用密码哈希（如 bcrypt）
        """
        # 这里是明文比较，实际应该使用：
        # return bcrypt.checkpw(provided_password.encode(), stored_password.encode())
        return stored_password == provided_password
    
    @staticmethod
    async def create_user(
        db: Session, 
        username: str, 
        password: str, 
        **kwargs
    ) -> Dict[str, any]:
        """创建新用户"""
        try:
            # 检查用户是否已存在
            existing_user = await AuthService.get_user_by_username(db, username)
            if existing_user:
                return {
                    "success": False,
                    "error": "用户名已存在"
                }
            
            # TODO: 实际应该使用密码哈希
            # hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
            
            # 创建用户
            new_user = User(
                username=username,
                password=password,  # 直接存储，实际应该存哈希
                **kwargs
            )
            
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            
            return {
                "success": True,
                "user_id": new_user.id,
                "username": new_user.username
            }
            
        except Exception as e:
            db.rollback()
            return {
                "success": False,
                "error": f"创建用户失败: {str(e)}"
            }
    
    @staticmethod
    async def get_current_user_from_session(
        db: Session, 
        session_data: Dict
    ) -> Optional[User]:
        """从 session 中获取当前用户"""
        user_id = session_data.get("user_id")
        if not user_id:
            return None
        
        return db.query(User).filter(User.id == user_id).first()
    