"""SLA calculation utilities."""

from datetime import datetime, timedelta,timezone
from typing import Optional, Dict, Any
from enum import Enum as PyEnum

from app.models.ticket import SLAStatus


class SLAType(PyEnum):
    """SLA type enumeration."""
    RESPONSE = "response"
    RESOLUTION = "resolution"


class SLACalculator:
    """Utility class for SLA calculations and time management."""
    
    @staticmethod
    def calculate_deadline(start_time: datetime, target_minutes: int) -> datetime:
        """Calculate SLA deadline from start time and target in minutes."""
        return start_time + timedelta(minutes=target_minutes)
    
    @staticmethod
    def calculate_remaining_time(deadline: datetime, current_time: Optional[datetime] = None) -> timedelta:
        """Calculate remaining time until deadline."""
        if current_time is None:
            current_time = datetime.now(timezone.utc)
        
        return deadline - current_time
    
    @staticmethod
    def calculate_remaining_percentage(remaining_minutes: int, target_minutes: int) -> float:
        """Calculate remaining time as percentage of target."""
        if target_minutes <= 0:
            return 0.0
        
        return (remaining_minutes / target_minutes) * 100
    
    @staticmethod
    def get_sla_status(remaining_minutes: int, target_minutes: int, warning_threshold: float = 0.15, critical_threshold: float = 0.05) -> SLAStatus:
        """Determine SLA status based on remaining time and thresholds."""
        if remaining_minutes <= 0:
            return SLAStatus.BREACHED
        
        remaining_percentage = SLACalculator.calculate_remaining_percentage(remaining_minutes, target_minutes)
        
        if remaining_percentage <= (critical_threshold * 100):
            return SLAStatus.CRITICAL
        elif remaining_percentage <= (warning_threshold * 100):
            return SLAStatus.WARNING
        else:
            return SLAStatus.COMPLIANT
    
    @staticmethod
    def is_sla_breached(deadline: datetime, current_time: Optional[datetime] = None) -> bool:
        """Check if SLA deadline has been breached."""
        if current_time is None:
            current_time = datetime.now(timezone.utc)
        
        return current_time >= deadline
    
    @staticmethod
    def should_generate_alert(remaining_minutes: int, target_minutes: int, threshold_percentage: float = 15.0) -> bool:
        """Check if an alert should be generated based on remaining time."""
        if target_minutes <= 0:
            return False
        
        remaining_percentage = SLACalculator.calculate_remaining_percentage(remaining_minutes, target_minutes)
        return remaining_percentage <= threshold_percentage
    
    @staticmethod
    def format_duration(minutes: int) -> str:
        """Format duration in minutes to human readable string."""
        if minutes < 60:
            return f"{minutes}m"
        
        hours = minutes // 60
        remaining_minutes = minutes % 60
        
        if hours < 24:
            if remaining_minutes > 0:
                return f"{hours}h {remaining_minutes}m"
            else:
                return f"{hours}h"
        
        days = hours // 24
        remaining_hours = hours % 24
        
        if remaining_hours > 0:
            return f"{days}d {remaining_hours}h"
        else:
            return f"{days}d"
    
    @staticmethod
    def calculate_business_hours_elapsed(start_time: datetime, end_time: datetime) -> int:
        """Calculate elapsed business hours (simplified - 9 AM to 5 PM, Monday to Friday)."""
        current = start_time
        business_minutes = 0
        
        while current < end_time:
            # Skip weekends
            if current.weekday() >= 5:  # Saturday = 5, Sunday = 6
                # Move to next Monday
                days_to_add = 7 - current.weekday()
                current = current.replace(hour=9, minute=0, second=0, microsecond=0)
                current += timedelta(days=days_to_add)
                continue
            
            # Skip outside business hours
            if current.hour < 9 or current.hour >= 17:
                # Move to next business hour
                if current.hour >= 17:
                    # Move to next day at 9 AM
                    current = current.replace(hour=9, minute=0, second=0, microsecond=0)
                    current += timedelta(days=1)
                else:
                    # Move to 9 AM
                    current = current.replace(hour=9, minute=0, second=0, microsecond=0)
                continue
            
            # Count this minute
            business_minutes += 1
            current += timedelta(minutes=1)
        
        return business_minutes
    
    @staticmethod
    def get_next_business_time(current_time: datetime) -> datetime:
        """Get next business time (9 AM next business day if outside hours)."""
        # If it's a weekend, move to next Monday
        if current_time.weekday() >= 5:
            days_to_add = 7 - current_time.weekday()
            next_business_time = current_time.replace(hour=9, minute=0, second=0, microsecond=0)
            next_business_time += timedelta(days=days_to_add)
            return next_business_time
        
        # If it's outside business hours, move to next business time
        if current_time.hour < 9:
            # Move to 9 AM today
            return current_time.replace(hour=9, minute=0, second=0, microsecond=0)
        elif current_time.hour >= 17:
            # Move to 9 AM next business day
            next_day = current_time + timedelta(days=1)
            # Skip weekend if needed
            while next_day.weekday() >= 5:
                next_day += timedelta(days=1)
            return next_day.replace(hour=9, minute=0, second=0, microsecond=0)
        
        # Within business hours, return current time
        return current_time
