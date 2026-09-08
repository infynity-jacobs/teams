import enum
import datetime as dt

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Enum, JSON, UniqueConstraint
)
from sqlalchemy.orm import relationship

from app.database import Base


def utcnow():
    return dt.datetime.utcnow()


class RoleEnum(str, enum.Enum):
    super_admin = "super_admin"
    site_admin = "site_admin"
    marketing_manager = "marketing_manager"
    team_leader = "team_leader"
    marketing_staff = "marketing_staff"


class LeadStatusEnum(str, enum.Enum):
    new = "new"
    contacted = "contacted"
    follow_up = "follow_up"
    pending = "pending"
    converted = "converted"
    lost = "lost"
    closed = "closed"


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    leader_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)

    members = relationship("User", back_populates="team", foreign_keys="User.team_id")
    leader = relationship("User", foreign_keys=[leader_id], post_update=True)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(200), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(RoleEnum), nullable=False, default=RoleEnum.marketing_staff)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    session_version = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=utcnow)

    team = relationship("Team", back_populates="members", foreign_keys=[team_id])

    def can_manage_all_leads(self):
        return self.role in (RoleEnum.super_admin, RoleEnum.site_admin, RoleEnum.marketing_manager)

    def can_manage_team(self, team_id):
        if self.can_manage_all_leads():
            return True
        if self.role == RoleEnum.team_leader and self.team_id == team_id:
            return True
        return False


class Lead(Base):
    """A marketing lead / customer record, tracked through its lifecycle."""
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(120), nullable=False)
    last_name = Column(String(120), nullable=True)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(50), nullable=True, index=True)
    company = Column(String(200), nullable=True)
    source = Column(String(100), nullable=True)  # e.g. website, referral, campaign name
    place_area = Column(String(200), nullable=True, index=True)  # e.g. city/neighborhood/territory
    referred_by = Column(String(200), nullable=True, index=True)  # value chosen from Settings-managed list
    status = Column(Enum(LeadStatusEnum), nullable=False, default=LeadStatusEnum.new, index=True)
    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True, index=True)
    notes = Column(Text, nullable=True)
    dedup_key = Column(String(320), nullable=True, index=True)  # normalized email or phone for dedup
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    converted_at = Column(DateTime, nullable=True)
    lost_reason = Column(String(255), nullable=True)

    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
    team = relationship("Team", foreign_keys=[team_id])
    history = relationship("LeadStatusHistory", back_populates="lead", cascade="all, delete-orphan")
    follow_ups = relationship("FollowUp", back_populates="lead", cascade="all, delete-orphan")
    products = relationship("LeadProduct", back_populates="lead", cascade="all, delete-orphan")
    conversion = relationship("Conversion", back_populates="lead", uselist=False, cascade="all, delete-orphan")


class LeadStatusHistory(Base):
    __tablename__ = "lead_status_history"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False, index=True)
    old_status = Column(String(50), nullable=True)
    new_status = Column(String(50), nullable=False)
    changed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    note = Column(Text, nullable=True)
    changed_at = Column(DateTime, default=utcnow)

    lead = relationship("Lead", back_populates="history")
    changed_by = relationship("User")


class FollowUp(Base):
    __tablename__ = "follow_ups"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False, index=True)
    staff_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    follow_up_type = Column(String(50), nullable=False, default="call")  # call, email, meeting, other
    scheduled_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    outcome = Column(String(120), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    lead = relationship("Lead", back_populates="follow_ups")
    staff = relationship("User")


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    imported_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    column_mapping = Column(JSON, nullable=True)
    total_rows = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    duplicate_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    error_detail = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    imported_by = relationship("User")


class SystemSetting(Base):
    """Key/value system configuration. Sensitive values are encrypted at rest."""
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(120), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)
    is_secret = Column(Boolean, default=False, nullable=False)
    updated_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    updated_by = relationship("User")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User")


class SettingOption(Base):
    """
    Admin-managed dropdown values used elsewhere in the app (e.g. the
    'Referred By' list on leads). Grouped by 'category' so this table can
    back more than one managed list without a schema change - only
    Super Admins and Site Admins may create/edit/deactivate entries
    (see app/routers/settings.py); any authenticated user may read the
    active options to populate a dropdown.
    """
    __tablename__ = "setting_options"
    __table_args__ = (UniqueConstraint("category", "value", name="uq_setting_option_category_value"),)

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(50), nullable=False, index=True)  # e.g. "referred_by"
    value = Column(String(200), nullable=False)
    is_active = Column(Boolean, default=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow)

    created_by = relationship("User")


class ProductCategory(Base):
    __tablename__ = "product_categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utcnow)
    products = relationship("Product", back_populates="category")


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    sku = Column(String(100), unique=True, nullable=True, index=True)
    description = Column(Text, nullable=True)
    category_id = Column(Integer, ForeignKey("product_categories.id"), nullable=True, index=True)
    price = Column(Integer, nullable=False, default=0)
    currency = Column(String(10), nullable=False, default="INR")
    tax_percent = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    category = relationship("ProductCategory", back_populates="products")


class LeadProduct(Base):
    __tablename__ = "lead_products"
    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    quantity = Column(Integer, nullable=False, default=1)
    interest_status = Column(String(30), nullable=False, default="interested")
    quoted_price = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    lead = relationship("Lead", back_populates="products")
    product = relationship("Product")


class Conversion(Base):
    __tablename__ = "conversions"
    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    converted_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # Incentive attribution is captured at conversion time. The snapshot fields
    # preserve the seller identity even if the lead is reassigned or the user
    # is later deactivated/deleted.
    sold_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    sold_by_name = Column(String(200), nullable=True)
    sold_by_username = Column(String(80), nullable=True)
    sold_by_team_name = Column(String(120), nullable=True)
    conversion_date = Column(DateTime, default=utcnow)
    subtotal = Column(Integer, nullable=False, default=0)
    discount = Column(Integer, nullable=False, default=0)
    tax = Column(Integer, nullable=False, default=0)
    total = Column(Integer, nullable=False, default=0)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    lead = relationship("Lead", back_populates="conversion")
    converted_by = relationship("User", foreign_keys=[converted_by_id])
    sold_by = relationship("User", foreign_keys=[sold_by_id])
    items = relationship("ConversionItem", back_populates="conversion", cascade="all, delete-orphan")


class ConversionItem(Base):
    __tablename__ = "conversion_items"
    id = Column(Integer, primary_key=True, index=True)
    conversion_id = Column(Integer, ForeignKey("conversions.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    product_name = Column(String(200), nullable=False)
    sku = Column(String(100), nullable=True)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Integer, nullable=False, default=0)
    tax_percent = Column(Integer, nullable=False, default=0)
    line_total = Column(Integer, nullable=False, default=0)
    conversion = relationship("Conversion", back_populates="items")
    product = relationship("Product")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    actor_name = Column(String(200), nullable=True)
    actor_username = Column(String(80), nullable=True)
    actor_role = Column(String(50), nullable=True)
    action = Column(String(100), nullable=False)
    entity_type = Column(String(100), nullable=True)
    entity_id = Column(Integer, nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=utcnow, index=True)

    user = relationship("User")
