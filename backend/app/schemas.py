import datetime as dt
from typing import Optional, List, Any, Dict

from pydantic import BaseModel, EmailStr, ConfigDict

from app.models import RoleEnum, LeadStatusEnum


# ---------- Auth ----------
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    full_name: str
    user_id: int


class LoginRequest(BaseModel):
    username: str
    password: str


# ---------- Team ----------
class TeamBase(BaseModel):
    name: str
    description: Optional[str] = None
    leader_id: Optional[int] = None


class TeamCreate(TeamBase):
    pass


class TeamUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    leader_id: Optional[int] = None
    is_active: Optional[bool] = None


class TeamOut(TeamBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_active: bool
    created_at: dt.datetime
    member_count: Optional[int] = 0


# ---------- User ----------
class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: str
    role: RoleEnum
    team_id: Optional[int] = None


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[RoleEnum] = None
    team_id: Optional[int] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    email: str
    full_name: str
    role: RoleEnum
    team_id: Optional[int] = None
    is_active: bool
    created_at: dt.datetime


# ---------- Lead ----------
class LeadBase(BaseModel):
    first_name: str
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    source: Optional[str] = None
    place_area: Optional[str] = None
    referred_by: Optional[str] = None
    notes: Optional[str] = None


class LeadCreate(LeadBase):
    assigned_to_id: Optional[int] = None
    team_id: Optional[int] = None
    status: Optional[LeadStatusEnum] = LeadStatusEnum.new


class LeadUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    source: Optional[str] = None
    place_area: Optional[str] = None
    referred_by: Optional[str] = None
    notes: Optional[str] = None
    assigned_to_id: Optional[int] = None
    team_id: Optional[int] = None


class LeadStatusChange(BaseModel):
    status: LeadStatusEnum
    note: Optional[str] = None
    lost_reason: Optional[str] = None


class LeadAssign(BaseModel):
    assigned_to_id: int


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    first_name: str
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    source: Optional[str] = None
    place_area: Optional[str] = None
    referred_by: Optional[str] = None
    status: LeadStatusEnum
    assigned_to_id: Optional[int] = None
    team_id: Optional[int] = None
    notes: Optional[str] = None
    created_at: dt.datetime
    updated_at: dt.datetime
    converted_at: Optional[dt.datetime] = None
    lost_reason: Optional[str] = None
    assigned_to_name: Optional[str] = None
    team_name: Optional[str] = None


class LeadListOut(BaseModel):
    total: int
    items: List[LeadOut]


# ---------- Follow Up ----------
class FollowUpCreate(BaseModel):
    follow_up_type: str = "call"
    scheduled_at: Optional[dt.datetime] = None
    completed_at: Optional[dt.datetime] = None
    outcome: Optional[str] = None
    notes: Optional[str] = None


class FollowUpOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    lead_id: int
    staff_id: Optional[int] = None
    follow_up_type: str
    scheduled_at: Optional[dt.datetime] = None
    completed_at: Optional[dt.datetime] = None
    outcome: Optional[str] = None
    notes: Optional[str] = None
    created_at: dt.datetime


class LeadHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    old_status: Optional[str] = None
    new_status: str
    note: Optional[str] = None
    changed_at: dt.datetime
    changed_by_id: Optional[int] = None


class LeadDetailOut(LeadOut):
    history: List[LeadHistoryOut] = []
    follow_ups: List[FollowUpOut] = []


# ---------- Import ----------
class ImportMappingRequest(BaseModel):
    # maps application field name -> excel column header
    mapping: Dict[str, str]
    default_team_id: Optional[int] = None
    default_assigned_to_id: Optional[int] = None
    default_source: Optional[str] = None


class ImportResultOut(BaseModel):
    batch_id: int
    total_rows: int
    success_count: int
    duplicate_count: int
    error_count: int
    errors: List[Dict[str, Any]] = []


# ---------- Settings (admin-managed dropdown options, e.g. Referred By) ----------
class SettingOptionCreate(BaseModel):
    category: str
    value: str


class SettingOptionUpdate(BaseModel):
    value: Optional[str] = None
    is_active: Optional[bool] = None


class SettingOptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    category: str
    value: str
    is_active: bool
    created_at: dt.datetime




# ---------- System Settings / Password Management ----------
class SystemSettingOut(BaseModel):
    key: str
    value: Optional[str] = None
    is_secret: bool = False
    updated_at: Optional[dt.datetime] = None


class SystemSettingsUpdate(BaseModel):
    values: Dict[str, Any]


class TestEmailRequest(BaseModel):
    recipient: EmailStr


class PasswordResetRequest(BaseModel):
    identifier: str


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


class AdminPasswordResetRequest(BaseModel):
    user_id: int


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class ReportEmailRequest(BaseModel):
    report_type: str
    recipients: List[EmailStr]
    date_from: Optional[dt.date] = None
    date_to: Optional[dt.date] = None
    team_id: Optional[int] = None
    staff_id: Optional[int] = None
    source: Optional[str] = None
    status: Optional[LeadStatusEnum] = None
    subject: Optional[str] = None
    message: Optional[str] = None
    attachments: List[str] = ["pdf", "xlsx"]

# ---------- Reports ----------
class ReportFilter(BaseModel):
    date_from: Optional[dt.date] = None
    date_to: Optional[dt.date] = None
    team_id: Optional[int] = None
    staff_id: Optional[int] = None
    source: Optional[str] = None
    status: Optional[LeadStatusEnum] = None


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: Optional[int] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    details: Optional[Any] = None
    ip_address: Optional[str] = None
    created_at: dt.datetime
