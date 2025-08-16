"""
Query service for optimized database operations with eager loading.

This module provides optimized query methods that use eager loading
to prevent N+1 query patterns and improve performance for common
database operations.
"""
from __future__ import annotations

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy import and_, or_, desc, asc

from .. import db
from ..models import Job, User, JobStatus
from ..models_conversion import Conversion, ConversionStatus


class JobQueryService:
    """Service for optimized Job queries with eager loading."""
    
    @staticmethod
    def get_job_by_id(job_id: int, user_id: Optional[int] = None, 
                      visitor_session_id: Optional[str] = None) -> Optional[Job]:
        """Get a single job by ID with eager loading of user relationship."""
        query = Job.query.options(selectinload(Job.user))
        
        # Apply ownership filter
        if user_id is not None:
            query = query.filter(Job.user_id == user_id)
        elif visitor_session_id is not None:
            query = query.filter(Job.visitor_session_id == visitor_session_id)
        
        return query.filter(Job.id == job_id).first()
    
    @staticmethod
    def get_jobs_by_user(user_id: int, status: Optional[str] = None, 
                        limit: Optional[int] = None, offset: int = 0) -> List[Job]:
        """Get jobs for a user with optional status filtering and pagination."""
        query = Job.query.options(selectinload(Job.user)).filter(Job.user_id == user_id)
        
        if status:
            query = query.filter(Job.status == JobStatus(status))
        
        query = query.order_by(desc(Job.created_at))
        
        if limit:
            query = query.limit(limit).offset(offset)
        
        return query.all()
    
    @staticmethod
    def get_jobs_by_visitor_session(visitor_session_id: str, status: Optional[str] = None,
                                   limit: Optional[int] = None, offset: int = 0) -> List[Job]:
        """Get jobs for a visitor session with optional status filtering and pagination."""
        query = Job.query.options(selectinload(Job.user)).filter(Job.visitor_session_id == visitor_session_id)
        
        if status:
            query = query.filter(Job.status == JobStatus(status))
        
        query = query.order_by(desc(Job.created_at))
        
        if limit:
            query = query.limit(limit).offset(offset)
        
        return query.all()
    
    @staticmethod
    def get_jobs_by_status(status: str, limit: Optional[int] = None) -> List[Job]:
        """Get jobs by status (for worker processing)."""
        query = Job.query.options(selectinload(Job.user)).filter(Job.status == JobStatus(status))
        query = query.order_by(asc(Job.created_at))
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    @staticmethod
    def get_job_count_by_owner(user_id: Optional[int] = None, 
                              visitor_session_id: Optional[str] = None) -> int:
        """Get job count for an owner (user or visitor session)."""
        query = Job.query
        
        if user_id is not None:
            query = query.filter(Job.user_id == user_id)
        elif visitor_session_id is not None:
            query = query.filter(Job.visitor_session_id == visitor_session_id)
        
        return query.count()
    
    @staticmethod
    def get_jobs_by_date_range(start_date: datetime, end_date: datetime,
                              user_id: Optional[int] = None) -> List[Job]:
        """Get jobs within a date range with eager loading."""
        query = Job.query.options(selectinload(Job.user)).filter(
            and_(
                Job.created_at >= start_date,
                Job.created_at <= end_date
            )
        )
        
        if user_id is not None:
            query = query.filter(Job.user_id == user_id)
        
        return query.order_by(desc(Job.created_at)).all()


class ConversionQueryService:
    """Service for optimized Conversion queries with eager loading."""
    
    @staticmethod
    def get_conversion_by_id(conversion_id: str, user_id: Optional[int] = None,
                            visitor_session_id: Optional[str] = None) -> Optional[Conversion]:
        """Get a single conversion by ID with eager loading."""
        query = Conversion.query
        
        # Apply ownership filter
        if user_id is not None:
            query = query.filter(Conversion.user_id == user_id)
        elif visitor_session_id is not None:
            query = query.filter(Conversion.visitor_session_id == visitor_session_id)
        
        return query.filter(Conversion.id == conversion_id).first()
    
    @staticmethod
    def get_conversion_by_sha256(sha256: str, user_id: Optional[int] = None,
                                visitor_session_id: Optional[str] = None) -> Optional[Conversion]:
        """Get conversion by SHA256 hash with ownership filtering."""
        query = Conversion.query.filter(Conversion.sha256 == sha256)
        
        if user_id is not None:
            query = query.filter(Conversion.user_id == user_id)
        elif visitor_session_id is not None:
            query = query.filter(Conversion.visitor_session_id == visitor_session_id)
        
        return query.order_by(desc(Conversion.created_at)).first()
    
    @staticmethod
    def get_conversions_by_user(user_id: int, status: Optional[str] = None,
                               limit: Optional[int] = None, offset: int = 0) -> List[Conversion]:
        """Get conversions for a user with optional status filtering and pagination."""
        query = Conversion.query.filter(Conversion.user_id == user_id)
        
        if status:
            query = query.filter(Conversion.status == ConversionStatus(status))
        
        query = query.order_by(desc(Conversion.created_at))
        
        if limit:
            query = query.limit(limit).offset(offset)
        
        return query.all()
    
    @staticmethod
    def get_conversions_by_visitor_session(visitor_session_id: str, status: Optional[str] = None,
                                          limit: Optional[int] = None, offset: int = 0) -> List[Conversion]:
        """Get conversions for a visitor session with optional status filtering and pagination."""
        query = Conversion.query.filter(Conversion.visitor_session_id == visitor_session_id)
        
        if status:
            query = query.filter(Conversion.status == ConversionStatus(status))
        
        query = query.order_by(desc(Conversion.created_at))
        
        if limit:
            query = query.limit(limit).offset(offset)
        
        return query.all()
    
    @staticmethod
    def get_conversions_by_status(status: str, limit: Optional[int] = None) -> List[Conversion]:
        """Get conversions by status (for worker processing)."""
        query = Conversion.query.filter(Conversion.status == ConversionStatus(status))
        query = query.order_by(asc(Conversion.created_at))
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    @staticmethod
    def get_conversion_count_by_owner(user_id: Optional[int] = None,
                                     visitor_session_id: Optional[str] = None) -> int:
        """Get conversion count for an owner (user or visitor session)."""
        query = Conversion.query
        
        if user_id is not None:
            query = query.filter(Conversion.user_id == user_id)
        elif visitor_session_id is not None:
            query = query.filter(Conversion.visitor_session_id == visitor_session_id)
        
        return query.count()
    
    @staticmethod
    def get_completed_conversion_by_sha256(sha256: str, user_id: Optional[int] = None,
                                          visitor_session_id: Optional[str] = None) -> Optional[Conversion]:
        """Get completed conversion by SHA256 for idempotency checks."""
        query = Conversion.query.filter(
            and_(
                Conversion.sha256 == sha256,
                Conversion.status == ConversionStatus.COMPLETED
            )
        )
        
        if user_id is not None:
            query = query.filter(Conversion.user_id == user_id)
        elif visitor_session_id is not None:
            query = query.filter(Conversion.visitor_session_id == visitor_session_id)
        
        return query.order_by(desc(Conversion.created_at)).first()
    
    @staticmethod
    def get_pending_conversions_by_sha256(sha256: str, user_id: Optional[int] = None,
                                         visitor_session_id: Optional[str] = None) -> List[Conversion]:
        """Get pending/processing conversions by SHA256 for duplicate detection."""
        query = Conversion.query.filter(
            and_(
                Conversion.sha256 == sha256,
                Conversion.status.in_([ConversionStatus.QUEUED, ConversionStatus.PROCESSING])
            )
        )
        
        if user_id is not None:
            query = query.filter(Conversion.user_id == user_id)
        elif visitor_session_id is not None:
            query = query.filter(Conversion.visitor_session_id == visitor_session_id)
        
        return query.order_by(desc(Conversion.created_at)).all()
    
    @staticmethod
    def get_conversions_by_date_range(start_date: datetime, end_date: datetime,
                                     user_id: Optional[int] = None) -> List[Conversion]:
        """Get conversions within a date range."""
        query = Conversion.query.filter(
            and_(
                Conversion.created_at >= start_date,
                Conversion.created_at <= end_date
            )
        )
        
        if user_id is not None:
            query = query.filter(Conversion.user_id == user_id)
        
        return query.order_by(desc(Conversion.created_at)).all()


class UserQueryService:
    """Service for optimized User queries with eager loading."""
    
    @staticmethod
    def get_user_by_id(user_id: int) -> Optional[User]:
        """Get user by ID with eager loading of jobs."""
        return User.query.options(selectinload(User.jobs)).filter(User.id == user_id).first()
    
    @staticmethod
    def get_user_by_email(email: str) -> Optional[User]:
        """Get user by email with eager loading of jobs."""
        return User.query.options(selectinload(User.jobs)).filter(User.email == email).first()
    
    @staticmethod
    def get_users_with_jobs(limit: Optional[int] = None) -> List[User]:
        """Get users with their jobs (for admin/reporting)."""
        query = User.query.options(selectinload(User.jobs))
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
