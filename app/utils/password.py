"""
Password validation utilities for the mdraft application.

This module provides password strength validation with configurable policies
and human-readable feedback for users.
"""
import re
import string
from typing import List, Tuple, Dict, Any
from dataclasses import dataclass


@dataclass
class PasswordValidationResult:
    """Result of password validation with detailed feedback."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    score: int  # 0-100 password strength score
    
    def __bool__(self) -> bool:
        return self.is_valid


class PasswordValidator:
    """Password validator with configurable policies."""
    
    def __init__(self, config):
        """Initialize validator with configuration."""
        self.config = config
        self.security_config = config.security
    
    def validate_password(self, password: str) -> PasswordValidationResult:
        """
        Validate a password against the configured policy.
        
        Args:
            password: The password to validate
            
        Returns:
            PasswordValidationResult with validation status and feedback
        """
        errors = []
        warnings = []
        score = 0
        
        # Check minimum length
        if len(password) < self.security_config.PASSWORD_MIN_LENGTH:
            errors.append(f"Password must be at least {self.security_config.PASSWORD_MIN_LENGTH} characters long")
        
        # Check character class requirements
        char_classes = self._get_character_classes(password)
        required_classes = []
        
        if self.security_config.PASSWORD_REQUIRE_UPPERCASE:
            required_classes.append("uppercase")
        if self.security_config.PASSWORD_REQUIRE_LOWERCASE:
            required_classes.append("lowercase")
        if self.security_config.PASSWORD_REQUIRE_DIGITS:
            required_classes.append("digits")
        if self.security_config.PASSWORD_REQUIRE_SYMBOLS:
            required_classes.append("symbols")
        
        # Check which character classes are present
        present_classes = []
        if char_classes["uppercase"] > 0:
            present_classes.append("uppercase")
        if char_classes["lowercase"] > 0:
            present_classes.append("lowercase")
        if char_classes["digits"] > 0:
            present_classes.append("digits")
        if char_classes["symbols"] > 0:
            present_classes.append("symbols")
        
        # Check minimum character classes requirement
        if len(present_classes) < self.security_config.PASSWORD_MIN_CHARACTER_CLASSES:
            errors.append(f"Password must contain at least {self.security_config.PASSWORD_MIN_CHARACTER_CLASSES} of the following: uppercase letters, lowercase letters, digits, symbols")
        
        # Check specific character class requirements
        for required_class in required_classes:
            if required_class not in present_classes:
                class_name = required_class.replace("_", " ")
                errors.append(f"Password must contain at least one {class_name} character")
        
        # Calculate password strength score
        score = self._calculate_password_score(password, char_classes)
        
        # Add warnings for weak passwords (even if they pass minimum requirements)
        if score < 50:
            warnings.append("Consider using a stronger password for better security")
        elif score < 70:
            warnings.append("This password meets minimum requirements but could be stronger")
        
        # Check for common patterns that make passwords weak
        if self._has_common_patterns(password):
            warnings.append("Avoid common patterns like sequential characters or repeated sequences")
        
        return PasswordValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            score=score
        )
    
    def _get_character_classes(self, password: str) -> Dict[str, int]:
        """Count characters in each character class."""
        return {
            "uppercase": len(re.findall(r'[A-Z]', password)),
            "lowercase": len(re.findall(r'[a-z]', password)),
            "digits": len(re.findall(r'\d', password)),
            "symbols": len(re.findall(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?]', password))
        }
    
    def _calculate_password_score(self, password: str, char_classes: Dict[str, int]) -> int:
        """
        Calculate password strength score (0-100).
        
        Scoring criteria:
        - Length: up to 25 points
        - Character variety: up to 25 points
        - Character distribution: up to 25 points
        - Complexity: up to 25 points
        """
        score = 0
        
        # Length score (0-25 points)
        length_score = min(25, len(password) * 2)
        score += length_score
        
        # Character variety score (0-25 points)
        variety_score = len([c for c in char_classes.values() if c > 0]) * 6.25
        score += variety_score
        
        # Character distribution score (0-25 points)
        total_chars = sum(char_classes.values())
        if total_chars > 0:
            distribution = sum(abs(c / total_chars - 0.25) for c in char_classes.values())
            distribution_score = max(0, 25 - distribution * 50)
            score += distribution_score
        
        # Complexity score (0-25 points)
        complexity_bonus = 0
        
        # Bonus for mixed case
        if char_classes["uppercase"] > 0 and char_classes["lowercase"] > 0:
            complexity_bonus += 5
        
        # Bonus for numbers and symbols
        if char_classes["digits"] > 0:
            complexity_bonus += 5
        if char_classes["symbols"] > 0:
            complexity_bonus += 5
        
        # Bonus for no repeated characters
        if len(set(password)) == len(password):
            complexity_bonus += 5
        
        # Bonus for no sequential characters
        if not self._has_sequential_chars(password):
            complexity_bonus += 5
        
        score += complexity_bonus
        
        return min(100, int(score))
    
    def _has_common_patterns(self, password: str) -> bool:
        """Check for common weak patterns in passwords."""
        # Check for sequential characters
        if self._has_sequential_chars(password):
            return True
        
        # Check for repeated sequences
        for i in range(2, len(password) // 2 + 1):
            for j in range(len(password) - i + 1):
                pattern = password[j:j+i]
                if password.count(pattern) > 1:
                    return True
        
        # Check for keyboard patterns
        keyboard_patterns = [
            "qwerty", "asdfgh", "zxcvbn",
            "123456", "abcdef", "password"
        ]
        password_lower = password.lower()
        for pattern in keyboard_patterns:
            if pattern in password_lower:
                return True
        
        return False
    
    def _has_sequential_chars(self, password: str) -> bool:
        """Check for sequential characters (e.g., abc, 123, etc.)."""
        for i in range(len(password) - 2):
            # Check alphabetic sequences
            if (password[i].isalpha() and password[i+1].isalpha() and password[i+2].isalpha()):
                if (ord(password[i+1]) == ord(password[i]) + 1 and 
                    ord(password[i+2]) == ord(password[i]) + 2):
                    return True
            
            # Check numeric sequences
            if (password[i].isdigit() and password[i+1].isdigit() and password[i+2].isdigit()):
                if (int(password[i+1]) == int(password[i]) + 1 and 
                    int(password[i+2]) == int(password[i]) + 2):
                    return True
        
        return False


def validate_password_strength(password: str, config) -> PasswordValidationResult:
    """
    Convenience function to validate password strength.
    
    Args:
        password: The password to validate
        config: Application configuration object
        
    Returns:
        PasswordValidationResult with validation status and feedback
    """
    validator = PasswordValidator(config)
    return validator.validate_password(password)
