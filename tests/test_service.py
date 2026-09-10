import plistlib

import pytest

from shetty.service import LABEL, agent_definition, manage_service


def test_service_uses_venv_absolute_path_and_loopback_default(config):
    path = '/Users/me/SHETTY/.venv/bin/python'
    agent = agent_definition(config, executable=path)
    assert agent['Label'] == LABEL
    assert agent['ProgramArguments'] == [path, '-m', 'shetty', 'serve']
    assert agent['RunAtLoad'] and agent['KeepAlive']
    assert '--preview' not in agent['ProgramArguments']
    assert 'sudo' not in str(agent)
    assert 'caffeinate' not in str(agent)
    restored = plistlib.loads(plistlib.dumps(agent))
    assert restored['ProgramArguments'][0] == path


def test_service_is_macos_only(config, monkeypatch):
    monkeypatch.setattr('shetty.service.platform.system', lambda: 'Linux')
    with pytest.raises(ValueError, match='macOS-only'):
        manage_service('install', config)
