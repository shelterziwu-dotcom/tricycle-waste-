from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DumpingReport, User
from app.schemas import DumpingReportIn, DumpingReportOut
from app.security import get_current_user

router = APIRouter(prefix="/dumping-reports", tags=["dumping reports"])


@router.post("", response_model=DumpingReportOut, status_code=201)
def report_dumping(data: DumpingReportIn, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    report = DumpingReport(user_id=user.id, **data.model_dump())
    db.add(report)
    db.commit()
    return report


@router.get("/mine", response_model=list[DumpingReportOut])
def my_reports(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(DumpingReport).filter_by(user_id=user.id).order_by(DumpingReport.created_at.desc()).all()
