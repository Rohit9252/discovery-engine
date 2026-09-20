"""Shared request pacing and provider cooldown across analysis workers."""
import threading
import time


class ProviderQuotaError(RuntimeError):
    """Account quota is exhausted; retrying cannot make progress."""


class RequestPacer:
    def __init__(self, tokens_per_minute, clock=time.monotonic, sleep=time.sleep):
        self.tokens_per_minute = tokens_per_minute
        self.clock, self.sleep = clock, sleep
        self.lock = threading.Lock()
        self.next_request = 0
        self.blocked_until = 0

    def wait(self, estimated_tokens):
        interval = max(0.5, 60 * estimated_tokens / self.tokens_per_minute)
        while True:
            with self.lock:
                now = self.clock()
                delay = max(self.next_request, self.blocked_until) - now
                if delay <= 0:
                    self.next_request = now + interval
                    return
            self.sleep(delay)

    def cooldown(self, seconds):
        with self.lock:
            self.blocked_until = max(self.blocked_until, self.clock() + seconds)


class PacedStructuredLLM:
    def __init__(self, chain, model):
        self.chain = chain
        self.pacer = RequestPacer(20000 if model == 'gpt-4.1' else 120000)

    def invoke(self, messages):
        # Include the output allowance; provider token limits can reserve it upfront.
        estimated_tokens = sum(len(text) for role, text in messages) / 3 + 3500
        self.pacer.wait(estimated_tokens)
        try:
            return self.chain.invoke(messages)
        except Exception as exc:
            if getattr(exc, 'status_code', None) == 429:
                body = getattr(exc, 'body', {}) or {}
                body = body.get('error', body)
                if body.get('code') == 'insufficient_quota':
                    raise ProviderQuotaError('OpenAI account quota is exhausted') from None
                headers = getattr(getattr(exc, 'response', None), 'headers', {})
                try:
                    wait = float(headers.get('retry-after', 30))
                except (TypeError, ValueError):
                    wait = 30
                self.pacer.cooldown(max(5, min(wait, 180)))
            raise
