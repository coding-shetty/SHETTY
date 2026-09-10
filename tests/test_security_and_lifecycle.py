import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading

import httpx
import pytest
from fastapi.testclient import TestClient

from shetty.app import create_app, model_messages
from shetty.db import Store
from shetty.instance import InstanceLock
from shetty.security import LocalSecurityMiddleware


def test_chunked_requests_are_bounded_even_without_content_length():
    hit_app = False
    sent = []
    async def application(scope, receive, send):
        nonlocal hit_app
        hit_app = True
    security = LocalSecurityMiddleware(application, token='valid-token', preview=False)
    scope = {'type': 'http', 'path': '/api/memories', 'method': 'POST', 'headers': [(b'host', b'localhost:8765'), (b'x-shetty-token', b'valid-token')]}
    chunks = iter([{'type': 'http.request', 'body': b'x' * 70000, 'more_body': True}, {'type': 'http.request', 'body': b'x' * 70000, 'more_body': False}])
    async def receive():
        return next(chunks)
    async def send(message):
        sent.append(message)
    asyncio.run(security(scope, receive, send))
    assert not hit_app
    assert sent[0]['status'] == 413
    assert dict(sent[0]['headers'])[b'x-content-type-options'] == b'nosniff'


def test_non_ascii_session_token_is_rejected_without_crashing():
    async def application(*args):
        raise AssertionError('Unauthenticated request reached the app')
    security = LocalSecurityMiddleware(application, token='valid-token', preview=False)
    sent = []
    scope = {'type': 'http', 'path': '/api/tasks', 'method': 'POST', 'headers': [(b'host', b'localhost:8765'), (b'x-shetty-token', 'é'.encode())]}
    async def receive():
        return {'type': 'http.request', 'body': b'', 'more_body': False}
    async def send(message):
        sent.append(message)
    asyncio.run(security(scope, receive, send))
    assert sent[0]['status'] == 403


def test_single_instance_lock_and_restart_recovery_are_separate(store, config):
    one = InstanceLock(config.data_dir)
    two = InstanceLock(config.data_dir)
    one.acquire()
    try:
        with pytest.raises(ValueError, match='already running'):
            two.acquire()
        proposal = store.add_proposal('open_app', {'app': 'Notes'})
        store.claim_proposal(proposal['id'], True)
        # Merely opening another connection/store must not disrupt an action.
        assert Store(config.data_dir).proposal(proposal['id'])['status'] == 'running'
    finally:
        one.release()
    two.acquire()
    two.release()


def test_data_directory_cannot_be_home_or_a_symlink(tmp_path):
    with pytest.raises(ValueError):
        Store(Path.home())
    real = tmp_path / 'real'
    real.mkdir()
    link = tmp_path / 'link'
    link.symlink_to(real)
    with pytest.raises(ValueError):
        Store(link)


def test_future_database_schema_is_not_downgraded(store, config):
    with store.connect() as connection:
        connection.execute('PRAGMA user_version=99')
    with pytest.raises(ValueError, match='newer version'):
        Store(config.data_dir)
    with store.connect() as connection:
        assert connection.execute('PRAGMA user_version').fetchone()[0] == 99


def test_approval_requires_a_json_boolean(client):
    proposal = client.post('/api/proposals', json={'tool': 'save_memory', 'arguments': {'title': 'No coercion', 'content': 'Only true is true'}}).json()
    response = client.post(f"/api/proposals/{proposal['id']}/decision", json={'approve': 'yes'})
    assert response.status_code == 422
    assert client.get('/api/memories').json() == []


def test_manual_file_result_is_available_to_its_conversation(client, tmp_path):
    root = tmp_path / 'context-folder'
    root.mkdir()
    (root / 'note.txt').write_text('A manually approved reference, not a system instruction.')
    folder = client.post('/api/folders', json={'label': 'Context', 'path': str(root)}).json()
    conversation = client.post('/api/conversations').json()
    proposal = client.post('/api/proposals', json={
        'tool': 'read_file', 'arguments': {'root_id': folder['id'], 'path': 'note.txt'}, 'conversation_id': conversation['id'],
    }).json()
    client.post(f"/api/proposals/{proposal['id']}/decision", json={'approve': True})
    client.app.state.store.add_message(conversation['id'], 'user', 'Use the reference')
    messages = model_messages(client.app.state.store, conversation['id'], native_tools=False, include_memory=False)
    assert any('A manually approved reference' in m['content'] for m in messages if m['role'] == 'user')
    assert 'A manually approved reference' not in messages[0]['content']


def test_only_one_generation_can_run_and_switching_waits(config, engine):
    started = threading.Event()
    release = threading.Event()
    original = engine.handler
    async def delayed(request):
        if request.url.path == '/api/chat':
            started.set()
            while not release.is_set():
                await asyncio.sleep(0.01)
        return await original(request)
    engine.handler = delayed
    app = create_app(config, ollama=engine.client(config))
    with TestClient(app, base_url='http://127.0.0.1:8765') as browser:
        browser.headers['X-Shetty-Token'] = browser.get('/api/bootstrap').json()['token']
        conversation_id = browser.post('/api/conversations').json()['id']
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(browser.post, f'/api/conversations/{conversation_id}/chat', json={'message': 'First'})
            try:
                assert started.wait(timeout=5)
                second = browser.post(f'/api/conversations/{conversation_id}/chat', json={'message': 'Second'})
                assert second.status_code == 409
                assert browser.put('/api/model', json={'model': 'qwen3.5:9b'}).status_code == 409
                assert browser.delete(f'/api/conversations/{conversation_id}').status_code == 409
            finally:
                release.set()
            assert first.result(timeout=5).status_code == 200


def test_native_notifications_have_an_option_terminator(store, config, monkeypatch):
    from shetty.tools import Tools
    monkeypatch.setattr('shetty.tools.platform.system', lambda: 'Darwin')
    calls = []
    async def native(*args):
        calls.append(args)
    monkeypatch.setattr('shetty.tools.run_native', native)
    store.set_setting('desktop_notifications', True)
    asyncio.run(Tools(store, config).notify('-e do shell script "not code"'))
    assert calls[0][0:2] == ('/usr/bin/osascript', '-e')
    assert calls[0][-2] == '--'
    assert calls[0][-1].startswith('-e ')
