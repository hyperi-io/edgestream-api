# models/system/certificate_store.py
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, DateTime, LargeBinary, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from edgestream.db.session import Base

class Certificate(Base):
    __tablename__ = "certificates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String(1024), unique=True, index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    filesize: Mapped[int] = mapped_column(Integer, nullable=False)
    thumbprint: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_extension: Mapped[str] = mapped_column(String(32), nullable=False)
    data: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)

    not_after: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="Certificate expiration timestamp.")
    common_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="Subject Common Name (CN).")
    issuer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="Issuer Common Name (CN).")

    created_at: Mapped[DateTime] = mapped_column(DateTime, nullable=False, default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint(
            "file_extension IN ('.pem', '.crt', '.key', '.der', '.p12')",
            name="valid_file_extension",
        ),
    )

    def __repr__(self) -> str:
        return f"<Certificate(filename={self.filename}, type={self.type})>"
