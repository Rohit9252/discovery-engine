from types import SimpleNamespace

import pytest

from src.process.research_rate_limit import RequestPacer, PacedStructuredLLM, ProviderQuotaError


def test_shared_pacing_reserves_time_and_honors_cooldown():
    now=[100.0]
    sleeps=[]
    def sleep(seconds):
        sleeps.append(seconds);now[0]+=seconds
    pacer=RequestPacer(60000,clock=lambda:now[0],sleep=sleep)
    pacer.wait(2000)
    pacer.wait(2000)
    assert sleeps==[2]
    pacer.cooldown(20)
    pacer.wait(2000)
    assert sleeps[-1]==20


def test_rate_limit_cools_all_workers_and_quota_exhaustion_is_terminal():
    class ProviderError(Exception):
        status_code=429
        body={'code':'rate_limit_exceeded'}
        response=SimpleNamespace(headers={'retry-after':'12'})
    class Fake:
        def invoke(self,messages):raise ProviderError()
    llm=PacedStructuredLLM(Fake(),'gpt-4.1-mini')
    waits=[]
    llm.pacer=SimpleNamespace(wait=lambda tokens:waits.append(tokens),cooldown=lambda seconds:waits.append(seconds))
    with pytest.raises(ProviderError):llm.invoke([('human','Source text')])
    assert waits[-1]==12
    ProviderError.body={'code':'insufficient_quota'}
    with pytest.raises(ProviderQuotaError):llm.invoke([('human','Source text')])
