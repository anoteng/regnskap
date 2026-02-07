from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from backend.database import get_db
from ..models import CSVMapping, User, Ledger
from ..schemas import CSVMapping as CSVMappingSchema, CSVMappingCreate
from ..auth import get_current_active_user, get_current_ledger

router = APIRouter(prefix="/csv-mappings", tags=["csv-mappings"])


@router.get("/", response_model=List[CSVMappingSchema])
def get_csv_mappings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    return db.query(CSVMapping).filter(CSVMapping.ledger_id == current_ledger.id).all()


@router.post("/", response_model=CSVMappingSchema)
def create_csv_mapping(
    mapping: CSVMappingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    existing = db.query(CSVMapping).filter(
        CSVMapping.ledger_id == current_ledger.id,
        CSVMapping.name == mapping.name
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Mapping with this name already exists")

    db_mapping = CSVMapping(
        ledger_id=current_ledger.id,
        **mapping.model_dump()
    )
    db.add(db_mapping)
    db.commit()
    db.refresh(db_mapping)
    return db_mapping


@router.get("/{mapping_id}", response_model=CSVMappingSchema)
def get_csv_mapping(
    mapping_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    mapping = db.query(CSVMapping).filter(
        CSVMapping.id == mapping_id,
        CSVMapping.ledger_id == current_ledger.id
    ).first()
    if not mapping:
        raise HTTPException(status_code=404, detail="CSV mapping not found")
    return mapping


@router.delete("/{mapping_id}")
def delete_csv_mapping(
    mapping_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    current_ledger: Ledger = Depends(get_current_ledger)
):
    mapping = db.query(CSVMapping).filter(
        CSVMapping.id == mapping_id,
        CSVMapping.ledger_id == current_ledger.id
    ).first()
    if not mapping:
        raise HTTPException(status_code=404, detail="CSV mapping not found")

    db.delete(mapping)
    db.commit()
    return {"message": "CSV mapping deleted"}
