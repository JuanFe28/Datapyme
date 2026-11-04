import re
import unicodedata
from datetime import datetime, timezone
from sqlalchemy import Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey, Integer, JSON, LargeBinary, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()
def utcnow(): return datetime.now(timezone.utc)
def normalized(value):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD',value) if not unicodedata.combining(c)).casefold().split())

class User(Base):
    __tablename__='users'
    id=Column(Integer,primary_key=True)
    username=Column(String(60),unique=True,nullable=False)
    password_hash=Column(String(255),nullable=False)
    role=Column(String(20),nullable=False)
    active=Column(Boolean,nullable=False,default=True)
    created_at=Column(DateTime(timezone=True),default=utcnow,nullable=False)
    __table_args__=(CheckConstraint("role IN ('admin','campo')",name='ck_user_role'),)

class LoginSession(Base):
    __tablename__='login_sessions'
    id=Column(Integer,primary_key=True)
    token_hash=Column(String(64),nullable=False,unique=True)
    user_id=Column(Integer,ForeignKey('users.id'),nullable=False,index=True)
    expires_at=Column(DateTime(timezone=True),nullable=False)
    user=relationship(User)

class LoginAttempt(Base):
    __tablename__='login_attempts'
    key=Column(String(64),primary_key=True)
    failures=Column(Integer,nullable=False,default=0)
    since=Column(DateTime(timezone=True),nullable=False,default=utcnow)

class Company(Base):
    __tablename__='companies'
    id=Column(Integer,primary_key=True)
    name=Column(String(180),nullable=False)
    duplicate_key=Column(String(64),nullable=True,unique=True)
    barrio=Column(String(120),nullable=False,default='')
    city=Column(String(60),nullable=False,default='Bucaramanga')
    activity=Column(String(90),nullable=False)
    ciiu=Column(String(20),default='')
    size=Column(String(30),nullable=False)
    source=Column(String(120),default='')
    verification_status=Column(String(20),nullable=False,default='pendiente',server_default='pendiente')
    operating_status=Column(String(20),nullable=False,default='pendiente',server_default='pendiente')
    has_records=Column(String(40),default='')
    respondent_role=Column(String(90),default='')
    willing=Column(String(30),default='')
    notes=Column(Text,default='')
    owner=Column(String(60),nullable=False)
    created_at=Column(DateTime(timezone=True),default=utcnow)
    updated_at=Column(DateTime(timezone=True),default=utcnow)
    responses=relationship('Response',back_populates='company')
    contact=relationship('CompanyContact',uselist=False,back_populates='company')
    @property
    def code(self): return f'DP-{self.id:05d}'
    @property
    def eligible(self):
        return (normalized(self.city)=='bucaramanga' and self.activity in ('Comercio minorista','Comercio mayorista') and self.size in ('Pequeña','Mediana') and self.verification_status=='verificada' and bool((self.source or '').strip()) and self.operating_status=='activa' and self.has_records=='Sí, ambos' and self.respondent_role in ('Propietario','Propietario o socio','Gerente o administrador','Administrador','Responsable de ventas','Responsable de inventarios') and self.willing=='Sí')
    @property
    def eligibility_status(self):
        if self.eligible: return 'elegible'
        if self.size in ('Microempresa','Grande') or self.activity in ('Servicios','Manufactura') or self.city=='Otro / por verificar' or self.operating_status=='inactiva' or self.willing=='No': return 'fuera'
        return 'pendiente'

class CompanyContact(Base):
    __tablename__='company_contacts'
    id=Column(Integer,primary_key=True)
    company_id=Column(Integer,ForeignKey('companies.id'),nullable=False,unique=True)
    name=Column(String(120),default='')
    detail=Column(String(250),default='')
    company=relationship(Company,back_populates='contact')

class Consent(Base):
    __tablename__='consents'
    id=Column(Integer,primary_key=True)
    company_id=Column(Integer,ForeignKey('companies.id'),nullable=False)
    participant_code=Column(String(40),nullable=False)
    instrument=Column(String(20),nullable=False)
    version=Column(String(30),nullable=False)
    statement=Column(Text,nullable=False)
    recorded_by=Column(String(60),nullable=False)
    recorded_at=Column(DateTime(timezone=True),default=utcnow,nullable=False)

class Response(Base):
    __tablename__='responses'
    id=Column(Integer,primary_key=True)
    company_id=Column(Integer,ForeignKey('companies.id'),nullable=False,index=True)
    category=Column(String(20),nullable=False,index=True)
    data=Column(JSON,nullable=False)
    author=Column(String(60),nullable=False)
    created_at=Column(DateTime(timezone=True),default=utcnow)
    updated_at=Column(DateTime(timezone=True),default=utcnow)
    status=Column(String(25),nullable=False,default='draft',server_default='legacy_pending')
    participant_code=Column(String(40),nullable=True)
    consent_id=Column(Integer,ForeignKey('consents.id'),nullable=True)
    survey_key=Column(String(64),nullable=True,unique=True)
    instrument_version=Column(String(30),nullable=True)
    prototype_reference=Column(String(500),nullable=True)
    company=relationship(Company,back_populates='responses')
    consent=relationship(Consent)
    answers=relationship('Answer',cascade='all,delete-orphan',back_populates='response')

class Answer(Base):
    __tablename__='answers'
    id=Column(Integer,primary_key=True)
    response_id=Column(Integer,ForeignKey('responses.id'),nullable=False,index=True)
    question_code=Column(String(20),nullable=False)
    value=Column(JSON,nullable=False)
    response=relationship(Response,back_populates='answers')
    __table_args__=(UniqueConstraint('response_id','question_code',name='uq_answer_question'),)

class InstrumentQuestion(Base):
    __tablename__='instrument_questions'
    id=Column(Integer,primary_key=True)
    category=Column(String(20),nullable=False)
    version=Column(String(30),nullable=False)
    code=Column(String(20),nullable=False)
    definition=Column(JSON,nullable=False)
    __table_args__=(UniqueConstraint('category','version','code',name='uq_instrument_question'),)

class Task(Base):
    __tablename__='tasks'
    id=Column(Integer,primary_key=True)
    phase=Column(String(5),nullable=False)
    title=Column(String(180),nullable=False,unique=True)
    completed=Column(Boolean,default=False)
    status=Column(String(20),nullable=False,default='planificada',server_default='planificada')
    assignee=Column(String(120),default='')
    evidence=Column(String(300),default='')
    due_date=Column(Date,nullable=True)
    updated_at=Column(DateTime(timezone=True),default=utcnow)

class Evidence(Base):
    __tablename__='evidence'
    id=Column(Integer,primary_key=True)
    title=Column(String(180),nullable=False)
    filename=Column(String(180),nullable=False)
    mime_type=Column(String(100),nullable=False)
    size=Column(Integer,nullable=False)
    sha256=Column(String(64),nullable=False)
    uploader=Column(String(60),nullable=False,index=True)
    company_id=Column(Integer,ForeignKey('companies.id'),nullable=True)
    response_id=Column(Integer,ForeignKey('responses.id'),nullable=True)
    task_id=Column(Integer,ForeignKey('tasks.id'),nullable=True)
    notes=Column(Text,default='')
    created_at=Column(DateTime(timezone=True),default=utcnow,nullable=False)
    blob=relationship('EvidenceBlob',uselist=False,back_populates='evidence')

class EvidenceBlob(Base):
    __tablename__='evidence_blobs'
    evidence_id=Column(Integer,ForeignKey('evidence.id'),primary_key=True)
    content=Column(LargeBinary,nullable=False)
    evidence=relationship(Evidence,back_populates='blob')

class AuditLog(Base):
    __tablename__='audit_logs'
    id=Column(Integer,primary_key=True)
    actor=Column(String(60),nullable=False)
    action=Column(String(60),nullable=False)
    entity_type=Column(String(40),nullable=False,index=True)
    entity_id=Column(Integer,nullable=True)
    changes=Column(JSON,nullable=False)
    created_at=Column(DateTime(timezone=True),default=utcnow,nullable=False)

class CanvasVersion(Base):
    __tablename__='canvas_versions'
    id=Column(Integer,primary_key=True)
    title=Column(String(180),nullable=False)
    blocks=Column(JSON,nullable=False)
    hypothesis_status=Column(String(20),nullable=False,default='pendiente')
    evidence_id=Column(Integer,ForeignKey('evidence.id'),nullable=True)
    conclusion=Column(Text,default='')
    author=Column(String(60),nullable=False)
    created_at=Column(DateTime(timezone=True),default=utcnow,nullable=False)

class FinancialScenario(Base):
    __tablename__='financial_scenarios'
    id=Column(Integer,primary_key=True)
    name=Column(String(180),nullable=False)
    inputs=Column(JSON,nullable=False)
    source=Column(Text,nullable=False)
    assumptions=Column(Text,nullable=False)
    author=Column(String(60),nullable=False)
    created_at=Column(DateTime(timezone=True),default=utcnow,nullable=False)

class ResearchNote(Base):
    __tablename__='research_notes'
    id=Column(Integer,primary_key=True)
    kind=Column(String(30),nullable=False)
    title=Column(String(180),nullable=False)
    content=Column(Text,nullable=False)
    source=Column(Text,nullable=False)
    author=Column(String(60),nullable=False)
    created_at=Column(DateTime(timezone=True),default=utcnow,nullable=False)
