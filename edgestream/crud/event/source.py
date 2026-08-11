from typing import List, Dict, Tuple, Any, Optional
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func, select
import json

from edgestream.core.config import Logger
from edgestream.crud.base import CRUDBase
from edgestream.models.event.source import Source, SourceParameter
from edgestream.models.event.transform import Transform
from edgestream.schemas.event.source import SourceCreate, SourceUpdate
from edgestream.schemas.event.source_parameter import SourceParameterBase


def _serialize_value(v: Any) -> Any:
    if isinstance(v, (list, dict)):
        return json.dumps(v)
    return v


class CRUDSource(CRUDBase[Source, SourceCreate, SourceUpdate]):

    def get(self, db: Session, name: str) -> Optional[Source]:
        return db.execute(
            select(Source).where(Source.name.ilike(name))
        ).scalar_one_or_none()

    def get_by_id(self, db: Session, id: int) -> Optional[Source]:
        return db.get(Source, id)

    def count_enabled(self, db: Session) -> int:
        return db.execute(
            select(func.count(Source.id)).where(Source.enabled.is_(True))
        ).scalar() or 0

    def get_by_type(self, db: Session, type_name: str) -> List[Source]:
        return list(
            db.execute(select(Source).where(Source.type.ilike(type_name))).scalars().all()
        )

    def get_all(self, db: Session) -> List[Source]:
        """Returns all sources except the internal syslog-ng source."""
        return list(
            db.execute(
                select(Source)
                .options(selectinload(Source.parameters))
                .where(Source.type != "syslog_ng")
            ).scalars().all()
        )

    def get_all_sources_full(self, db: Session) -> List[Source]:
        """Returns ALL sources including syslog-ng for validation purposes."""
        return list(
            db.execute(
                select(Source).options(selectinload(Source.parameters))
            ).scalars().all()
        )

    def export(self, db: Session) -> List[Dict[str, Any]]:
        """Standardized export for sources and nested parameters."""
        sources = db.execute(
            select(Source).options(selectinload(Source.parameters))
        ).scalars().all()

        return [
            {
                "name": s.name,
                "type": s.type,
                "enabled": bool(s.enabled),
                "system": bool(s.system),
                "settings": {p.key: p.value for p in s.parameters if p.value is not None},
            }
            for s in sources
        ]

    def get_all_syslog(self, db: Session) -> List[Source]:
        return list(
            db.execute(
                select(Source)
                .options(selectinload(Source.parameters))
                .where(Source.type == "syslog_ng")
            ).scalars().all()
        )

    def get_all_sources(self, db: Session) -> List[str]:
        """Returns all source names as routing identifiers."""
        sources = self.get_all(db)

        labels = []
        for source in sources:
            if source.type == "opentelemetry":
                labels.extend([f"{source.name}.{suffix}" for suffix in ("logs", "traces", "metrics")])
            else:
                labels.append(source.name)
        return labels

    def get_syslog_by_port(self, db: Session, port: int) -> Optional[Source]:
        sources = self.get_all_syslog(db)
        for source in sources:
            for s in source.parameters:
                if s.key.lower() == "port":
                    try:
                        if int(s.value) == int(port):
                            return source
                    except (TypeError, ValueError):
                        continue
        return None

    def _normalize_settings(self, settings_list: List[SourceParameterBase]) -> List[SourceParameterBase]:
        """Deduplicate settings based on key."""
        return list({s.key: s for s in (settings_list or [])}.values())

    def create(self, db: Session, *, obj_in: SourceCreate) -> Tuple[Source, Dict[str, Any]]:
        try:
            db_obj = Source(
                name=obj_in.name,
                type=obj_in.type,
                enabled=bool(obj_in.enabled),
                system=bool(obj_in.system),
            )

            settings_list = self._normalize_settings(obj_in.settings)

            for new_setting in settings_list:
                if new_setting.value is None:
                    continue
                if isinstance(new_setting.value, str) and not new_setting.value.strip():
                    continue

                data = new_setting.model_dump()
                data["value"] = _serialize_value(data["value"])
                db_obj.parameters.append(SourceParameter(**data))

            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)

            return db_obj, {"parameters": db_obj.parameters}

        except IntegrityError as e:
            db.rollback()
            Logger.logger.error(f"Integrity error creating source: {e}")
            raise HTTPException(status_code=400, detail="Source or parameter violates a uniqueness constraint.")
        except SQLAlchemyError as e:
            db.rollback()
            Logger.logger.error(f"DB error creating source: {e}")
            raise HTTPException(status_code=500, detail="Database error during source creation.")

    def update(self, db: Session, *, db_obj: Source, obj_in: SourceUpdate) -> Tuple[Source, Dict[str, Any]]:
        if obj_in.type and db_obj.type != obj_in.type:
            raise HTTPException(
                status_code=400,
                detail="Changing source type is unsupported.",
            )

        try:
            if obj_in.system is not None:
                db_obj.system = bool(obj_in.system)
            if obj_in.enabled is not None:
                db_obj.enabled = bool(obj_in.enabled)

            for old_param in list(db_obj.parameters):
                db.delete(old_param)
                db_obj.parameters.remove(old_param)

            db.flush()

            settings_list = self._normalize_settings(obj_in.settings)

            for new_setting in settings_list:
                if new_setting.value is None:
                    continue
                if isinstance(new_setting.value, str) and not new_setting.value.strip():
                    continue

                data = new_setting.model_dump()
                data["value"] = _serialize_value(data["value"])
                db_obj.parameters.append(SourceParameter(**data))

            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)

            return db_obj, {"parameters": db_obj.parameters}

        except IntegrityError as e:
            db.rollback()
            Logger.logger.error(f"Integrity violation updating source: {e}")
            raise HTTPException(status_code=400, detail="Uniqueness violation updating source.")
        except SQLAlchemyError as e:
            db.rollback()
            Logger.logger.error(f"DB error updating source: {e}")
            raise HTTPException(status_code=500, detail="Database error during source update.")

    def delete_by_name(self, db: Session, *, name: str) -> None:
        db_obj = self.get(db, name)
        if not db_obj:
            raise HTTPException(status_code=404, detail="Source not found.")

        # Check for dependencies in transforms
        conflicting_transform = db.execute(
            select(Transform).where(Transform.parent == db_obj.name)
        ).scalar_one_or_none()

        if conflicting_transform:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot delete source '{name}': it is used by filter '{conflicting_transform.name}'."
            )

        try:
            db.delete(db_obj)
            db.commit()
        except Exception as error:
            db.rollback()
            Logger.logger.error(f"Error deleting source: {error}")
            raise HTTPException(status_code=400, detail="Error occurred while deleting the source.")


source = CRUDSource(Source)
