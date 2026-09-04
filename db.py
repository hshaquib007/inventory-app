"""
Database models and connection layer for the Streamlit Inventory app.

The app connects to a hosted Turso/libSQL database (free tier) so that all
PCs/networks share the same live data. If no Turso credentials are configured,
it falls back to a local SQLite file for offline development/testing.

On Streamlit Community Cloud, put the credentials in
`.streamlit/secrets.toml`:

    [turso]
    database_url = "libsql://your-db-org.turso.io"
    auth_token   = "eyJhbGciOi..."

On your own PC, you can also set these environment variables:
    TURSO_DATABASE_URL
    TURSO_AUTH_TOKEN
    INVENTORY_DB_PATH   (optional local SQLite fallback path)
"""

import os

from sqlalchemy import create_engine, Column, Integer, String, Float, Date, DateTime, func, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, relationship

from datetime import datetime

Base = declarative_base()


# ---------------------------------------------------------------------------
# Models (identical schema to the Flask app)
# ---------------------------------------------------------------------------

class ItemMaster(Base):
    __tablename__ = 'item_master'

    id = Column(Integer, primary_key=True)
    item_code = Column(String(50), unique=True, nullable=False)
    product_code = Column(String(50), nullable=False)
    item_name = Column(String(200), nullable=False)
    uom = Column(String(20), nullable=False)
    opening_stock = Column(Float, default=0.0)
    grn_qty = Column(Float, default=0.0)
    issued_qty = Column(Float, default=0.0)
    group = Column(String(100))
    sub_group = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def stock_quantity(self):
        return (self.opening_stock or 0.0) + (self.grn_qty or 0.0) - (self.issued_qty or 0.0)


class BOM(Base):
    __tablename__ = 'bom'

    id = Column(Integer, primary_key=True)
    bom_no = Column(String(50), nullable=False, index=True)
    job_no = Column(String(50), nullable=False, index=True)
    job_group = Column(String(50))
    date = Column(Date, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    lines = relationship('BOMLine', backref='bom', cascade='all, delete-orphan')


class BOMLine(Base):
    __tablename__ = 'bom_lines'

    id = Column(Integer, primary_key=True)
    bom_id = Column(Integer, ForeignKey("bom.id"), nullable=False, index=True)
    bom_sr_no = Column(String(20))
    job_no = Column(String(50), index=True)
    item_code = Column(String(50), nullable=False, index=True)
    product_code = Column(String(50), nullable=False, index=True)
    item_name = Column(String(200), nullable=False)
    uom = Column(String(20), nullable=False)
    quantity = Column(Float, nullable=False)
    group = Column(String(100))
    sub_group = Column(String(100))
    revision = Column(String(10), default='0')
    baseline_item_name = Column(String(200))
    baseline_quantity = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class JobMaster(Base):
    __tablename__ = 'job_master'

    id = Column(Integer, primary_key=True)
    job_no = Column(String(50), unique=True, nullable=False)
    job_detail = Column(String(500), nullable=False)
    customer = Column(String(200), nullable=False)
    job_group = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PRN(Base):
    __tablename__ = 'prn'

    id = Column(Integer, primary_key=True)
    prn_no = Column(String(50), unique=True, nullable=False)
    prn_date = Column(Date, nullable=False)
    job_no = Column(String(50), nullable=False)
    job_group = Column(String(50))
    status = Column(String(20), default='Pending')
    remarks = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    lines = relationship('PRNLine', backref='prn', cascade='all, delete-orphan')


class PRNLine(Base):
    __tablename__ = 'prn_lines'

    id = Column(Integer, primary_key=True)
    prn_id = Column(Integer, ForeignKey("prn.id"), nullable=False)
    bom_no = Column(String(50))
    bom_sr_no = Column(String(20))
    item_code = Column(String(50), nullable=False)
    product_code = Column(String(50), nullable=False)
    item_name = Column(String(200), nullable=False)
    uom = Column(String(20), nullable=False)
    job_no = Column(String(50))
    required_qty = Column(Float, nullable=False)
    prn_qty = Column(Float, nullable=False)
    reserved_qty = Column(Float, default=0.0)
    stock_qty = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class GRN(Base):
    __tablename__ = 'grn'

    id = Column(Integer, primary_key=True)
    grn_no = Column(String(50), unique=True, nullable=False)
    grn_date = Column(Date, nullable=False)
    supplier_name = Column(String(200))
    invoice_no = Column(String(50))
    invoice_date = Column(Date)
    job_group = Column(String(50))
    remarks = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    lines = relationship('GRNLine', backref='grn', cascade='all, delete-orphan')


class GRNLine(Base):
    __tablename__ = 'grn_lines'

    id = Column(Integer, primary_key=True)
    grn_id = Column(Integer, ForeignKey("grn.id"), nullable=False)
    item_code = Column(String(50), nullable=False)
    product_code = Column(String(50), nullable=False)
    item_name = Column(String(200), nullable=False)
    uom = Column(String(20), nullable=False)
    received_qty = Column(Float, nullable=False)
    date = Column(Date, nullable=False)
    po_number = Column(String(50))
    job_no = Column(String(50))
    last_purchase_price = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PMI(Base):
    __tablename__ = 'pmi'

    id = Column(Integer, primary_key=True)
    pmi_no = Column(String(50), unique=True, nullable=False)
    pmi_date = Column(Date, nullable=False)
    supplier_name = Column(String(200))
    invoice_no = Column(String(50))
    invoice_date = Column(Date)
    job_group = Column(String(50))
    remarks = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    lines = relationship('PMILine', backref='pmi', cascade='all, delete-orphan')


class PMILine(Base):
    __tablename__ = 'pmi_lines'

    id = Column(Integer, primary_key=True)
    pmi_id = Column(Integer, ForeignKey("pmi.id"), nullable=False)
    item_code = Column(String(50), nullable=False)
    product_code = Column(String(50), nullable=False)
    item_name = Column(String(200), nullable=False)
    uom = Column(String(20), nullable=False)
    received_qty = Column(Float, nullable=False)
    date = Column(Date, nullable=False)
    job_no = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


ALL_MODELS = [ItemMaster, BOM, BOMLine, JobMaster, PRN, PRNLine, GRN, GRNLine, PMI, PMILine]


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def _get_connection_params():
    """Return (url, token, is_turso). Prefers Streamlit secrets, then env vars."""
    url = None
    token = None
    try:
        import streamlit as st
        secrets = st.secrets
        if secrets and 'turso' in secrets:
            url = secrets['turso'].get('database_url')
            token = secrets['turso'].get('auth_token')
    except Exception:
        pass

    if not url:
        url = os.environ.get('TURSO_DATABASE_URL')
    if not token:
        token = os.environ.get('TURSO_AUTH_TOKEN')

    return url, token


def build_engine():
    """Create a SQLAlchemy engine for Turso (or local SQLite fallback)."""
    url, token = _get_connection_params()

    if url:
        connect_args = {}
        if token:
            # Turso uses the token as the SQLAlchemy URL password.
            if '://' in url and not url.rstrip('/').split('://', 1)[1]:
                url = f"{url.rstrip('/')}:{token}"
            else:
                # sqlalchemy-libsql accepts a token via a query param
                connect_args = {'token': token}
        try:
            from sqlalchemy_libsql import LibSQLDialect  # noqa: F401  ensure installed
            engine = create_engine(url, connect_args=connect_args)
            return engine
        except Exception as e:
            raise RuntimeError(
                "sqlalchemy-libsql is required for Turso. Install it via "
                f"'pip install sqlalchemy-libsql' (error: {e})"
            )

    # Local SQLite fallback (offline dev / testing)
    db_path = os.environ.get('INVENTORY_DB_PATH', 'inventory_local.db')
    db_path = os.path.abspath(db_path)
    return create_engine(f'sqlite:///{db_path}')


engine = None
SessionLocal = None


def init_db():
    """Create/verify all tables and return a session factory."""
    global engine, SessionLocal
    if SessionLocal is not None:
        return SessionLocal

    engine = build_engine()
    try:
        # Create any missing tables; ignore "already exists" errors because
        # a migrated Turso DB already has them (with data).
        Base.metadata.create_all(engine)
    except Exception:
        pass
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal


def get_session():
    """Get a new database session (creates connection on first call)."""
    return init_db()()


def row_to_dict(row):
    """Convert any model instance to a plain dict (for display/export)."""
    if row is None:
        return None
    d = {}
    for col in row.__table__.columns:
        val = getattr(row, col.name)
        if isinstance(val, datetime):
            d[col.name] = val.strftime('%Y-%m-%d %H:%M:%S')
        elif hasattr(val, 'isoformat') and not isinstance(val, (int, float, str)):
            d[col.name] = val.isoformat()
        else:
            d[col.name] = val
    return d
