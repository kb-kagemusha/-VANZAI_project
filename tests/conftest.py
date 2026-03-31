"""
Test fixtures for VANZAI project
"""
import pytest
from datetime import date, time
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from src.models.base import Base, generate_ulid
from src.models.master import Worker, Client, Site, ProjectType, Role
from src.models.transaction import Project, ShiftSlot, Assignment
from src.models.enums import AssignmentStatus
from src.api.main import app
from src.api.deps import get_db


@pytest.fixture(scope="function")
def engine():
    """Create in-memory SQLite database for testing"""
    engine = create_engine(
        "sqlite://",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def session(engine):
    """Create database session"""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture(scope="function")
def db_session(session):
    """Alias for session (for compatibility)"""
    return session


@pytest.fixture(scope="function")
def api_client(session: Session):
    """FastAPI TestClient with DB override"""
    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def client(session: Session) -> Client:
    """Create test client"""
    client = Client(
        id=generate_ulid(),
        name="Test Client",
        code="TC001",
    )
    session.add(client)
    session.flush()
    return client


@pytest.fixture
def site(session: Session) -> Site:
    """Create test site"""
    site = Site(
        id=generate_ulid(),
        name="Test Site",
        code="TS001",
    )
    session.add(site)
    session.flush()
    return site


@pytest.fixture
def role(session: Session) -> Role:
    """Create test role"""
    role = Role(
        id=generate_ulid(),
        name="Staff",
        code="STAFF",
    )
    session.add(role)
    session.flush()
    return role


@pytest.fixture
def worker(session: Session) -> Worker:
    """Create test worker"""
    worker = Worker(
        id=generate_ulid(),
        name="Test Worker",
        email="test@example.com",
    )
    session.add(worker)
    session.flush()
    return worker


@pytest.fixture
def project(session: Session, client: Client) -> Project:
    """Create test project with default time calc settings"""
    project = Project(
        id=generate_ulid(),
        name="Test Project",
        code="TP001",
        client_id=client.id,
        rounding_unit_minutes=15,
        rounding_method="ceil",
        break_deduction_rule="auto",
        time_calc_mode="system_first",
        night_window_start=time(22, 0),
        night_window_end=time(5, 0),
    )
    session.add(project)
    session.flush()
    return project


@pytest.fixture
def shift_slot(session: Session, project: Project) -> ShiftSlot:
    """Create test shift slot for 2026-01-15"""
    slot = ShiftSlot(
        id=generate_ulid(),
        project_id=project.id,
        work_date=date(2026, 1, 15),
        start_time=time(9, 0),
        end_time=time(18, 0),
        shift_label="日勤",
    )
    session.add(slot)
    session.flush()
    return slot


@pytest.fixture
def assignment(
    session: Session,
    shift_slot: ShiftSlot,
    worker: Worker,
    role: Role,
) -> Assignment:
    """Create test assignment (confirmed)"""
    assignment = Assignment(
        id=generate_ulid(),
        shift_slot_id=shift_slot.id,
        worker_id=worker.id,
        role_id=role.id,
        status=AssignmentStatus.CONFIRMED.value,
    )
    session.add(assignment)
    session.flush()
    return assignment


def create_shift_and_assignment(
    session: Session,
    project: Project,
    worker: Worker,
    role: Role,
    work_date: date,
    status: AssignmentStatus = AssignmentStatus.CONFIRMED,
) -> tuple[ShiftSlot, Assignment]:
    """Helper to create shift slot and assignment for a specific date"""
    slot = ShiftSlot(
        id=generate_ulid(),
        project_id=project.id,
        work_date=work_date,
        start_time=time(9, 0),
        end_time=time(18, 0),
    )
    session.add(slot)
    session.flush()
    
    assignment = Assignment(
        id=generate_ulid(),
        shift_slot_id=slot.id,
        worker_id=worker.id,
        role_id=role.id,
        status=status.value,
    )
    session.add(assignment)
    session.flush()
    
    return slot, assignment
