import asyncio

import pytest

from barn_compute import server


@pytest.mark.parametrize("fails", [False, True])
def test_one_listener_stopping_shuts_down_the_other(monkeypatch, fails):
    instances = []

    class Listener:
        def __init__(self, configuration):
            self.configuration = configuration
            self.should_exit = False
            self.stopped = False
            instances.append(self)

        async def serve(self):
            try:
                if self.configuration == "first":
                    if fails:
                        raise RuntimeError("Listener failed")
                    return
                while not self.should_exit:
                    await asyncio.sleep(0.001)
            finally:
                self.stopped = True

    monkeypatch.setattr(server.uvicorn, "Server", Listener)
    if fails:
        with pytest.raises(RuntimeError, match="Listener failed"):
            asyncio.run(server._serve(["first", "second"]))
    else:
        asyncio.run(server._serve(["first", "second"]))
    assert all(listener.stopped and listener.should_exit for listener in instances)
