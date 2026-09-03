from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Team, User, RoleEnum, Lead, FollowUp
from app.schemas import TeamOut, TeamCreate, TeamUpdate
from app.deps import get_current_user, require_roles, log_action, MANAGERS_UP, ADMINS

router = APIRouter(prefix="/api/teams", tags=["teams"])


@router.get("", response_model=List[TeamOut])
def list_teams(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    teams = db.query(Team).order_by(Team.name).all()
    out = []
    for t in teams:
        member_count = db.query(func.count(User.id)).filter(User.team_id == t.id).scalar()
        item = TeamOut.model_validate(t)
        item.member_count = member_count
        out.append(item)
    return out


@router.post("", response_model=TeamOut)
def create_team(
    payload: TeamCreate,
    request: Request,
    current_user: User = Depends(require_roles(*MANAGERS_UP)),
    db: Session = Depends(get_db),
):
    if db.query(Team).filter(Team.name == payload.name).first():
        raise HTTPException(400, "Team name already exists")
    team = Team(**payload.dict())
    db.add(team)
    db.commit()
    db.refresh(team)
    log_action(db, current_user, "create_team", "team", team.id, {"name": team.name}, request)
    return team


@router.put("/{team_id}", response_model=TeamOut)
def update_team(
    team_id: int,
    payload: TeamUpdate,
    request: Request,
    current_user: User = Depends(require_roles(*MANAGERS_UP)),
    db: Session = Depends(get_db),
):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(404, "Team not found")
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(team, field, value)
    db.commit()
    db.refresh(team)
    log_action(db, current_user, "update_team", "team", team.id, request=request)
    return team


@router.delete("/{team_id}")
def delete_team(
    team_id: int,
    request: Request,
    current_user: User = Depends(require_roles(*ADMINS)),
    db: Session = Depends(get_db),
):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(404, "Team not found")
    if current_user.role != RoleEnum.super_admin:
        team.is_active = False
        db.commit()
        log_action(db, current_user, "deactivate_team", "team", team.id, request=request)
        return {"detail": "Team deactivated"}
    member_count = db.query(User).filter(User.team_id == team_id).count()
    lead_count = db.query(Lead).filter(Lead.team_id == team_id).count()
    if member_count or lead_count:
        raise HTTPException(409, f"Team has {member_count} user(s) and {lead_count} lead(s); move them before deleting the team")
    db.delete(team); db.commit()
    log_action(db, current_user, "delete_team", "team", team_id, {"name": team.name}, request=request)
    return {"detail": "Team deleted"}
