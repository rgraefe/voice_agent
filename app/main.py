from __future__ import annotations
from collections.abc import Callable
from starlette.middleware.base import RequestResponseEndpoint
from app.analysis import AnalysisReport
from app.types import Document
from datetime import datetime, timezone

from app.analysis import analyze

from app.goals import GoalAnswer

import secrets

import time

from pathlib import Path

from typing import Literal

from uuid import uuid4, uuid5, NAMESPACE_URL



from fastapi import FastAPI, Request, Response

from fastapi.exceptions import RequestValidationError

from fastapi.responses import FileResponse, JSONResponse

from fastapi.staticfiles import StaticFiles

from pydantic import AwareDatetime, Field

from starlette.concurrency import run_in_threadpool



from app.auth import Auth, fingerprint

from app.config import Settings

from app.errors import ServiceError

from app.interview import apply_turn, create_interview, stop_interview, summary

from app.models import AgentConfig, Extraction, Interview, StrictModel, TranscriptItem, Turn, now

from app.providers import close_room, room_access, voice_preview

from app.store import FirestoreStore, SqliteStore





class Login(StrictModel):

    password: str = Field(default='', max_length=300)

    invite: str = Field(default='', max_length=2000)

    demo_role: Literal['admin', 'founder'] | None = None





class Start(StrictModel):

    mode: Literal['voice', 'simulation'] = 'voice'

    request_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{8,80}$')





class SimulationTurn(StrictModel):

    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,100}$')

    text: str = Field(min_length=1, max_length=10000)

    clear: bool = True

    confirm: bool = False

    goal_key: str | None = None

    choice_value: str | None = None

    number_value: float | None = None

    answer_status: Literal["answered", "partial", "unknown"] | None = None





class Speech(StrictModel):

    role: Literal['user', 'assistant'] = 'assistant'

    id: str = Field(min_length=1, max_length=100)

    text: str = Field(max_length=12000)

    interrupted: bool = False

    timestamp: AwareDatetime | None = None





class Metric(StrictModel):

    id: str = Field(min_length=1, max_length=100)

    kind: Literal['llm', 'tts', 'eou', 'stt', 'latency', 'error']

    values: dict[str, float] = Field(max_length=20)





# Inject settings to isolate test databases and credentials from the local environment.
def create_app(settings: Settings | None = None) -> FastAPI:

    settings = settings or Settings()

    store = (FirestoreStore(settings.firestore_project, settings.firestore_database)

             if settings.persistence_backend == 'firestore' else SqliteStore(settings.database_path))

    auth = Auth(settings)

    app = FastAPI(title='Founder Interview', version='0.1.0')

    app.state.store, app.state.settings, app.state.auth = store, settings, auth

    # Initialize once; publishing and interview snapshots retain their own versions.
    def initialize_config(old: Document | None) -> Document:
        return old or {'config': AgentConfig().model_dump(), 'versions': []}

    store.update('config', 'published', initialize_config)

    @app.middleware('http')

    async def boundary(request: Request, call_next: RequestResponseEndpoint) -> Response:

        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE') and not request.url.path.startswith('/api/internal/'):

            if request.headers.get('x-requested-with') != 'founder-app':

                return JSONResponse({'error': {'code': 'CSRF_REJECTED', 'message': 'Ungültige Anfrage.', 'retryable': False}}, status_code=403)

            origin = request.headers.get('origin')

            if origin and origin.rstrip('/') != settings.public_origin.rstrip('/'):

                return JSONResponse({'error': {'code': 'ORIGIN_REJECTED', 'message': 'Ungültiger Ursprung.', 'retryable': False}}, status_code=403)

        try:

            response = await call_next(request)

        except Exception:

            # No exception details, request bodies, or provider credentials are logged or returned.

            return JSONResponse({'error': {'code': 'SERVICE_UNAVAILABLE', 'message': 'Der Dienst ist vorübergehend nicht verfügbar.', 'retryable': True}}, status_code=503)

        response.headers['X-Content-Type-Options'] = 'nosniff'

        response.headers['Referrer-Policy'] = 'no-referrer'

        response.headers['X-Frame-Options'] = 'DENY'

        if request.url.path.startswith('/api/'):

            response.headers['Cache-Control'] = 'no-store'

        return response



    @app.exception_handler(ServiceError)

    async def service_error(request: Request, exc: ServiceError) -> JSONResponse:

        return JSONResponse({'error': {'code': exc.code, 'message': exc.message, 'retryable': exc.retryable}}, status_code=exc.status)



    @app.exception_handler(RequestValidationError)

    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:

        return JSONResponse({'error': {'code': 'VALIDATION_ERROR', 'message': 'Bitte Eingaben und Wertebereiche prüfen.', 'retryable': False}}, status_code=422)



    def local_demo(request: Request) -> bool:

        return settings.environment == 'development' and request.client is not None and request.client.host in ('127.0.0.1', '::1', 'testclient')



    def config() -> AgentConfig:

        published = store.get('config', 'published')
        assert published is not None  # Created by initialize_config during startup.
        return AgentConfig.model_validate(published['config'])



    # Hide the existence of records owned by another founder behind the same not-found response.
    def load(interview_id: str, user: Document | None=None) -> Interview:

        data = store.get('interviews', interview_id)

        if not data or (user and user['role'] != 'admin' and data['owner'] != user['sub']):

            raise ServiceError('NOT_FOUND', 'Gespräch nicht gefunden.', 404)

        return Interview.model_validate(data)



    # Run state changes inside the repository transaction to avoid lost concurrent updates.
    def mutate_interview(interview_id: str, fn: Callable[[Interview], Interview]) -> Document:

        def mutate(data: Document | None) -> Document:

            if not data:

                raise ServiceError('NOT_FOUND', 'Gespräch nicht gefunden.', 404)

            return fn(Interview.model_validate(data)).model_dump()

        return store.update('interviews', interview_id, mutate)



    @app.get('/api/health', response_model=None)

    def health() -> dict[str, str]:

        return {'status': 'ok'}



    @app.get('/api/bootstrap', response_model=None)

    def bootstrap(request: Request) -> Document:

        try:

            user = auth.user(request)

        except ServiceError:

            user = None

        cfg = config()

        missing = settings.missing_voice() + ([] if cfg.voice_id else ['VOICE_ID'])

        return {'user': {'role': user['role']} if user else None, 'local_demo': local_demo(request) and not settings.admin_password,

                'voice_ready': not missing, 'missing': missing if user and user['role'] == 'admin' else [],

                'agent': {'name': cfg.name, 'language': cfg.language, 'max_minutes': cfg.max_minutes},

                'topics': [{'key': t.key, 'title': t.title} for t in cfg.topics]}



    @app.post('/api/login', response_model=None)

    def login(body: Login, request: Request, response: Response) -> dict[str, str]:

        if body.demo_role:

            if not local_demo(request) or settings.admin_password:

                raise ServiceError('FORBIDDEN', 'Lokaler Demozugang ist deaktiviert.', 403)

            subject, role = ('local-admin', 'admin') if body.demo_role == 'admin' else ('local-founder', 'founder')

        elif body.invite:

            data = auth.read(body.invite)

            if data['role'] != 'invite':

                raise ServiceError('UNAUTHORIZED', 'Ungültige Einladung.', 401)

            subject, role = data['sub'], 'founder'

        else:

            # Persistent attempt counter works across API replicas. No submitted secrets stored.

            key = fingerprint(request.client.host if request.client else 'unknown')

            def attempt(old: Document | None) -> Document:

                old = old or {'count': 0, 'until': time.time() + 300}

                if old['until'] < time.time():

                    old = {'count': 0, 'until': time.time() + 300}

                old['count'] += 1

                return old

            counter = store.update('login_attempts', key, attempt)

            if counter['count'] > 10:

                raise ServiceError('RATE_LIMITED', 'Bitte in fünf Minuten erneut versuchen.', 429, True)

            if not settings.admin_password or not secrets.compare_digest(body.password, settings.admin_password):

                raise ServiceError('UNAUTHORIZED', 'Anmeldung fehlgeschlagen.', 401)

            subject, role = 'administrator', 'admin'

        auth.cookie(response, subject, role)

        return {'role': role}



    @app.post('/api/logout', response_model=None)

    def logout(response: Response) -> dict[str, bool]:

        response.delete_cookie('founder_session')

        return {'ok': True}



    @app.post('/api/admin/invites', response_model=None)

    def invite(request: Request) -> Document:

        auth.admin(request)

        token = auth.token(uuid4().hex, 'invite', 7 * 86400)

        return {'url': settings.public_origin + '/#invite=' + token, 'expires_in_days': 7}



    @app.get('/api/admin/config', response_model=None)

    def get_config(request: Request) -> AgentConfig:

        auth.admin(request)

        return config()



    @app.post('/api/admin/config/validate', response_model=None)
    def validate_config(body: AgentConfig, request: Request) -> AgentConfig:
        auth.admin(request)
        if not {'name', 'goals', 'topics', 'voice_id'}.issubset(body.model_fields_set):
            raise ServiceError('INVALID_CONFIG_FILE', 'Bitte eine vollständige gespeicherte Agent-Konfiguration laden.', 422)
        # Imported files are drafts; publishing still uses optimistic concurrency.
        return body.model_copy(update={'version': config().version})


    @app.put('/api/admin/config', response_model=None)

    # Reject stale versions instead of silently overwriting another administrator's changes.
    def publish(body: AgentConfig, request: Request) -> Document:

        auth.admin(request)

        def change(old: Document | None) -> Document:

            assert old is not None  # Published configuration exists after startup.

            if body.version != old['config']['version']:

                raise ServiceError('CONFIG_CONFLICT', 'Die Konfiguration wurde inzwischen geändert. Bitte neu laden.', 409)

            updated = body.model_copy(update={'version': body.version + 1}).model_dump()

            return {'config': updated, 'versions': (old['versions'] + [old['config']])[-100:]}

        return store.update('config', 'published', change)['config']



    @app.post('/api/admin/voice-preview', response_model=None)

    async def preview(body: AgentConfig, request: Request) -> Response:

        auth.admin(request)

        audio = await voice_preview(settings, body)

        return Response(audio, media_type='audio/mpeg')



    @app.get('/api/interviews', response_model=None)

    def history(request: Request) -> list[Document]:

        user = auth.user(request)

        records = store.list('interviews', None if user['role'] == 'admin' else user['sub'])

        return sorted([{'id': r['id'], 'created_at': r['created_at'], 'status': r['status'], 'mode': r['mode'],

                        'title': r.get('goals', {}).get('startup_name', {}).get('value') or 'Neues Startup',

                        'config_version': r['config']['version']} for r in records], key=lambda r: r['created_at'], reverse=True)[:100]



    @app.post('/api/interviews', response_model=None)

    def start(body: Start, request: Request) -> Document:

        user = auth.user(request)

        cfg = config()

        if body.mode == 'simulation' and not local_demo(request):

            raise ServiceError('FORBIDDEN', 'Die Simulation ist nur lokal verfügbar.', 403)

        if body.mode == 'voice' and (settings.missing_voice() or not cfg.voice_id):

            raise ServiceError('VOICE_NOT_CONFIGURED', 'Bitte zuerst die Voice-Zugänge und eine Stimme konfigurieren.', 503)

        interview_id = uuid5(NAMESPACE_URL, user['sub'] + ':' + body.request_id).hex

        def create(old: Document | None) -> Document:

            if old:

                if old['mode'] != body.mode:

                    raise ServiceError('IDEMPOTENCY_CONFLICT', 'Die Anfrage existiert mit einem anderen Modus.', 409)

                return old

            interview = create_interview(user['sub'], cfg, body.mode)

            interview.id = interview_id

            if body.mode == 'simulation':

                interview.transcript.append(TranscriptItem(id='greeting', role='assistant', text=interview.last_reply))

            return interview.model_dump()

        return store.update('interviews', interview_id, create)



    @app.get('/api/interviews/{interview_id}', response_model=None)

    def detail(interview_id: str, request: Request) -> Interview:

        return load(interview_id, auth.user(request))



    @app.post('/api/interviews/{interview_id}/connection', response_model=None)

    async def connection(interview_id: str, request: Request) -> dict[str, str]:

        interview = await run_in_threadpool(load, interview_id, auth.user(request))

        if interview.mode != 'voice' or interview.status not in ('active', 'review'):

            raise ServiceError('INVALID_STATE', 'Dieses Gespräch kann nicht verbunden werden.', 409)

        return await room_access(settings, interview)



    @app.post('/api/interviews/{interview_id}/stop', response_model=None)

    async def stop(interview_id: str, request: Request) -> Document:

        interview = await run_in_threadpool(load, interview_id, auth.user(request))

        result = await run_in_threadpool(mutate_interview, interview_id, stop_interview)

        if interview.mode == 'voice':

            await close_room(settings, interview_id)

        return result



    @app.post('/api/interviews/{interview_id}/simulation-turn', response_model=None)

    # The text simulator uses explicit classifications supplied by the user, not LLM inference.
    def simulation(interview_id: str, body: SimulationTurn, request: Request) -> Document:

        interview = load(interview_id, auth.user(request))

        if not local_demo(request) or interview.mode != 'simulation':

            raise ServiceError('FORBIDDEN', 'Keine Simulationssitzung.', 403)

        def update(current: Interview) -> Interview:

            digest = fingerprint(body.model_dump_json())

            if body.id in current.simulation_requests:

                if current.simulation_requests[body.id] != digest:

                    raise ServiceError('IDEMPOTENCY_CONFLICT', 'Die Nachricht existiert mit anderem Inhalt.', 409)

                return current

            answers: list[GoalAnswer] = []
            key = body.goal_key or current.current_goal
            if key and not body.confirm:
                goal = next((g for g in current.config.goals if g.key == key), None)
                if not goal:
                    raise ServiceError('INVALID_ANSWER', 'Unbekanntes Antwortziel.', 422)
                choice = body.choice_value or (body.text if body.text in goal.choices else None)
                answers = [GoalAnswer(
                    goal_key=key, value=body.text, quote=body.text,
                    status=body.answer_status or ('answered' if body.clear else 'partial'),
                    choice_value=choice, number_value=body.number_value,
                )]
            turn = Turn(id=body.id, text=body.text, extraction=Extraction(
                answers=answers, confirmed_summary=body.confirm,
            ))

            current = apply_turn(current, turn)

            current.simulation_requests[body.id] = digest

            if not any(t.id == body.id + '-reply' for t in current.transcript):

                current.transcript.append(TranscriptItem(id=body.id + '-reply', role='assistant', text=current.last_reply))

            return current

        return mutate_interview(interview_id, update)



    @app.get('/api/interviews/{interview_id}/analysis', response_model=None)

    def analysis(interview_id: str, request: Request) -> AnalysisReport:

        return analyze(load(interview_id, auth.user(request)))



    @app.get('/api/interviews/{interview_id}/export', response_model=None)

    def export(interview_id: str, request: Request) -> Document:

        interview = load(interview_id, auth.user(request))

        return {'id': interview.id, 'status': interview.status, 'created_at': interview.created_at,

                'configuration_version': interview.config.version, 'summary': summary(interview),

                'goals': interview.goals, 'topics': interview.topics, 'transcript': interview.transcript, 'analysis': analyze(interview),

                'open_topics': [k for k, v in interview.topics.items() if v.status != 'clear']}



    @app.get('/api/internal/interviews/{interview_id}', response_model=None)

    def worker_detail(interview_id: str, request: Request) -> Interview:

        auth.worker(request)

        return load(interview_id)



    @app.post('/api/internal/interviews/{interview_id}/turns', response_model=None)

    # Return the canonical persisted state that the worker may safely speak from.
    def worker_turn(interview_id: str, body: Turn, request: Request) -> Document:

        auth.worker(request)

        return mutate_interview(interview_id, lambda interview: apply_turn(interview, body))



    @app.post('/api/internal/interviews/{interview_id}/speech', response_model=None)

    def worker_speech(interview_id: str, body: Speech, request: Request) -> Document:

        auth.worker(request)

        def record(interview: Interview) -> Interview:

            if body.role == 'assistant' and body.interrupted and interview.current_topic:

                expected = interview.current_prompt

                if expected not in body.text:

                    interview.interrupted_question = expected

            existing = next((t for t in interview.transcript if t.id == body.id), None)

            if existing and existing.role != body.role:

                raise ServiceError('IDEMPOTENCY_CONFLICT', 'Sprecher einer Nachricht darf nicht geändert werden.', 409)

            interview.transcript = [t for t in interview.transcript if t.id != body.id]

            if body.text:

                interview.transcript.append(TranscriptItem(id=body.id, role=body.role, text=body.text, interrupted=body.interrupted, timestamp=existing.timestamp if existing else (body.timestamp.astimezone(timezone.utc).isoformat() if body.timestamp else now())))

            interview.transcript.sort(key=lambda t: datetime.fromisoformat(t.timestamp))

            return interview

        return mutate_interview(interview_id, record)



    @app.post('/api/internal/interviews/{interview_id}/metrics', response_model=None)

    def worker_metrics(interview_id: str, body: Metric, request: Request) -> dict[str, bool]:

        auth.worker(request)

        def record(interview: Interview) -> Interview:

            if not any(m['id'] == body.id for m in interview.metrics):

                interview.metrics = (interview.metrics + [body.model_dump()])[-300:]

            return interview

        mutate_interview(interview_id, record)

        return {'ok': True}



    @app.post('/api/internal/interviews/{interview_id}/stop', response_model=None)

    def worker_stop(interview_id: str, request: Request) -> Document:

        auth.worker(request)

        return mutate_interview(interview_id, stop_interview)



    dist = Path(__file__).resolve().parent.parent / 'frontend' / 'dist'

    if dist.exists():

        app.mount('/assets', StaticFiles(directory=dist / 'assets'), name='assets')

        @app.get('/', response_model=None)

        def index() -> FileResponse:

            return FileResponse(dist / 'index.html')

    return app





app = create_app()

