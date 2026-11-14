"""Pydantic models for authentication endpoints."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


class SignupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=64)
    confirmPassword: str
    terms: bool

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Enter your full name.")
        return v

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: EmailStr) -> str:
        return str(v).strip().lower()

    @model_validator(mode="after")
    def validate_signup(self):
        if self.password != self.confirmPassword:
            raise ValueError("Passwords do not match.")
        if self.terms is not True:
            raise ValueError("Please accept the terms to continue.")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: EmailStr) -> str:
        return str(v).strip().lower()


class ForgotRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: EmailStr) -> str:
        return str(v).strip().lower()


class CodeRequest(BaseModel):
    code: str = Field(..., pattern=r"^\d{6}$")


class ResetPasswordRequest(BaseModel):
    password: str = Field(..., min_length=8, max_length=64)
    confirmPassword: str

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.confirmPassword:
            raise ValueError("Passwords do not match.")
        return self
