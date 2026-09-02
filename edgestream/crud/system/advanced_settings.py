"""
Project:   edgestream-api
File:      edgestream/crud/system/advanced_settings.py
Language:  Python

License:   BUSL-1.1
Copyright: (c) 2026 HYPERI PTY LIMITED
"""

from typing import List, Optional, Dict
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from edgestream.core.config import Logger
from edgestream.crud.base import CRUDBase
from edgestream.models.system.advanced_setting import AdvancedSetting
from edgestream.schemas.system.advanced_setting import (
    AdvancedSettingCreate,
    AdvancedSettingUpdate,
    AdvancedSettingBase,
)

class CRUDAdvancedSetting(CRUDBase[AdvancedSetting, AdvancedSettingCreate, AdvancedSettingUpdate]):

    def export(self, db: Session) -> Dict[str, str]:
        """
        Unified export method for the Configuration Exporter.
        Returns a flat dictionary of {label: value} for Ansible consumption.
        If a value is empty, it falls back to the default_value.
        """
        rows = db.execute(
            select(AdvancedSetting).order_by(AdvancedSetting.label.asc())
        ).scalars().all()

        return {
            r.label: (r.value if r.value and r.value.strip() else r.default_value)
            for r in rows
        }

    def get(self, db: Session, label: str) -> Optional[AdvancedSetting]:
        return db.execute(
            select(AdvancedSetting).where(AdvancedSetting.label == label)
        ).scalar_one_or_none()

    def update_bulk(
            self,
            db: Session,
            *,
            obj_in: List[AdvancedSettingBase],
    ) -> List[AdvancedSetting]:
        """Update multiple advanced settings at once using Upsert logic."""
        try:
            for entry in obj_in:
                adv = self.get(db, entry.label)

                if adv:
                    if entry.value is not None:
                        adv.value = entry.value
                    if entry.description is not None:
                        adv.description = entry.description
                    if entry.default_value is not None:
                        adv.default_value = entry.default_value
                else:
                    adv = AdvancedSetting(
                        label=entry.label,
                        value=entry.value,
                        description=entry.description,
                        default_value=entry.default_value,
                    )
                    db.add(adv)

            db.commit()
        except IntegrityError as error:
            db.rollback()
            Logger.logger.error(f"Integrity error during bulk settings update: {error}")
            raise HTTPException(status_code=400, detail="Update failed due to data constraints.")

        return list(db.execute(select(AdvancedSetting).order_by(AdvancedSetting.label.asc())).scalars().all())

    def delete_by_label(self, db: Session, *, label: str) -> Optional[AdvancedSetting]:
        obj = self.get(db, label)
        if not obj:
            raise HTTPException(status_code=404, detail=f"Setting '{label}' not found.")

        db.delete(obj)
        db.commit()
        return obj

    def create(self, db: Session, *, obj_in: AdvancedSettingCreate) -> AdvancedSetting:
        db_obj = AdvancedSetting(
            label=obj_in.label,
            value=obj_in.value,
            description=obj_in.description,
            default_value=obj_in.default_value,
        )
        try:
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=400, detail=f"Label '{obj_in.label}' already exists.")

advanced_setting = CRUDAdvancedSetting(AdvancedSetting)
