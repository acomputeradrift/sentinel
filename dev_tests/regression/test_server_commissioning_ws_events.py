import json
import unittest
import asyncio
import time
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _require_fastapi():
    try:
        from fastapi.testclient import TestClient  # type: ignore
    except Exception:  # pragma: no cover
        raise unittest.SkipTest("fastapi is not installed")
    return TestClient


def _recv_until(ws, predicate, *, max_messages: int = 30):
    for _ in range(max_messages):
        raw = ws.receive_text()
        msg = json.loads(raw)
        if not isinstance(msg, dict):
            continue
        if predicate(msg):
            return msg
    raise AssertionError("Did not receive expected websocket message.")


class CommissioningWsEventsTest(unittest.TestCase):
    def test_testing_send_timeout_emits_readable_error_code(self):
        from sentinel.server.api import testing as testing_api

        class _HangingWs:
            async def send_text(self, _text):
                await asyncio.sleep(3600)

            async def close(self, code=1000):
                _ = code
                return None

        async def _scenario():
            old_timeout = testing_api.WS_SEND_TIMEOUT_S
            testing_api.WS_SEND_TIMEOUT_S = 0.05
            try:
                with self.assertLogs("uvicorn.error", level="ERROR") as captured:
                    with self.assertRaises(asyncio.TimeoutError):
                        await testing_api._send_text_or_fail(
                            websocket=_HangingWs(),
                            text="{}",
                            project_id="p1",
                            tech_token="tok1",
                        )
            finally:
                testing_api.WS_SEND_TIMEOUT_S = old_timeout
            combined = "\n".join(captured.output)
            self.assertIn("WS-ERR-320 SEND_TIMEOUT", combined)

        asyncio.run(_scenario())

    def test_wait_for_next_timeout_does_not_emit_poll_spam_logs(self):
        import logging
        import queue

        from sentinel.server.services.ws_broker import wait_for_next

        class _Capture(logging.Handler):
            def __init__(self):
                super().__init__()
                self.messages = []

            def emit(self, record):
                self.messages.append(self.format(record))

        async def scenario():
            q: queue.Queue[str] = queue.Queue()
            logger = logging.getLogger("uvicorn.error")
            capture = _Capture()
            capture.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(capture)
            try:
                value = await wait_for_next(q, timeout_s=0.05)
            finally:
                logger.removeHandler(capture)
            self.assertIsNone(value)
            spam = [line for line in capture.messages if "[broker-wait]" in line]
            self.assertEqual(spam, [])

        logging.getLogger("uvicorn.error").setLevel(logging.INFO)
        asyncio.run(scenario())

    def test_commissioning_ws_send_loop_failure_does_not_leave_zombie_stream(self):
        _require_fastapi()
        from types import SimpleNamespace

        from fastapi import WebSocketDisconnect

        from sentinel.server.api import commissioning
        from sentinel.server.api import commissioning_project_ws
        from sentinel.server.services.repositories import InMemoryRepository
        from sentinel.server.services.ws_broker import ProjectEventBroker

        class _FakeWs:
            def __init__(self, app) -> None:
                self.app = app
                self._send_count = 0
                self.closed = asyncio.Event()
                self.accepted = False

            async def accept(self):
                self.accepted = True

            async def send_text(self, _text):
                self._send_count += 1
                # Snapshot send (first) succeeds; event send hangs forever.
                if self._send_count == 1:
                    return
                await asyncio.sleep(3600)

            async def receive_text(self):
                # Keep recv loop alive until websocket is explicitly closed.
                await self.closed.wait()
                raise WebSocketDisconnect()

            async def close(self, code=1000):
                _ = code
                self.closed.set()

        async def _scenario():
            from sentinel.server.services.commissioning_user import COMMISSIONING_STUB_USER_ID

            repo = InMemoryRepository()
            client = repo.create_client(userId=COMMISSIONING_STUB_USER_ID, name="Client A")
            project = repo.create_project(userId=COMMISSIONING_STUB_USER_ID, clientId=client.clientId, name="Project A")
            broker = ProjectEventBroker()

            app = SimpleNamespace(state=SimpleNamespace(repo=repo, project_event_broker=broker))
            ws = _FakeWs(app)

            old_timeout = commissioning_project_ws.WS_SEND_TIMEOUT_S
            commissioning_project_ws.WS_SEND_TIMEOUT_S = 0.05
            try:
                stream_task = asyncio.create_task(commissioning.project_ws(ws, project.projectId))
                await asyncio.sleep(0.02)
                broker.publish(projectId=project.projectId, event={"type": "test_result", "projectId": project.projectId, "targetKey": "t1", "outcome": "FAIL"})
                await asyncio.wait_for(stream_task, timeout=0.8)
            finally:
                commissioning_project_ws.WS_SEND_TIMEOUT_S = old_timeout

            # Stream must exit, not hang forever with a dead send loop.
            self.assertTrue(ws.accepted)
            self.assertTrue(ws.closed.is_set())

        asyncio.run(_scenario())

    def test_wait_for_next_timeout_does_not_block_subsequent_delivery(self):
        import queue

        from sentinel.server.services.ws_broker import wait_for_next

        async def scenario():
            q: queue.Queue[str] = queue.Queue()

            # First call should timeout quickly.
            t0 = asyncio.get_running_loop().time()
            first = await wait_for_next(q, timeout_s=0.05)
            t1 = asyncio.get_running_loop().time()
            self.assertIsNone(first)
            self.assertLess(t1 - t0, 0.5)

            # Then delivery on the same queue must still work immediately.
            q.put_nowait("x")
            t2 = asyncio.get_running_loop().time()
            second = await wait_for_next(q, timeout_s=0.5)
            t3 = asyncio.get_running_loop().time()
            self.assertEqual(second, "x")
            self.assertLess(t3 - t2, 0.25)

        asyncio.run(scenario())

    def test_broker_assigns_seq_and_can_replay_since(self):
        from sentinel.server.services.ws_broker import ProjectEventBroker

        broker = ProjectEventBroker(replay_capacity=4)
        broker.publish(projectId="p1", event={"type": "a", "projectId": "p1"})
        broker.publish(projectId="p1", event={"type": "b", "projectId": "p1"})
        broker.publish(projectId="p1", event={"type": "c", "projectId": "p1"})

        replay = broker.replay_since(projectId="p1", after_seq=1)
        self.assertEqual(replay["latestSeq"], 3)
        self.assertEqual(replay["replayableFromSeq"], 1)
        self.assertEqual([e.get("seq") for e in replay["events"]], [2, 3])
        self.assertEqual([e.get("type") for e in replay["events"]], ["b", "c"])

    def test_broker_transient_publish_does_not_affect_replay_or_seq(self):
        from sentinel.server.services.ws_broker import ProjectEventBroker

        broker = ProjectEventBroker(replay_capacity=4)
        q = broker.subscribe(projectId="p1")
        try:
            broker.publish(projectId="p1", event={"type": "durable", "projectId": "p1"})
            first = json.loads(q.get_nowait())
            self.assertEqual(first.get("type"), "durable")
            self.assertEqual(first.get("seq"), 1)

            transient = broker.publish_transient(projectId="p1", event={"type": "generation_phase", "projectId": "p1"})
            self.assertIsNone(transient.get("seq"))
            second = json.loads(q.get_nowait())
            self.assertEqual(second.get("type"), "generation_phase")
            self.assertIsNone(second.get("seq"))

            replay = broker.replay_since(projectId="p1", after_seq=0)
            self.assertEqual(replay["latestSeq"], 1)
            self.assertEqual([e.get("type") for e in replay["events"]], ["durable"])
        finally:
            broker.unsubscribe(projectId="p1", q=q)

    def test_no_duplicate_commissioning_project_ws_route(self):
        _require_fastapi()

        from sentinel.server.app.main import create_app
        from sentinel.server.services.repositories import InMemoryRepository

        app = create_app(repo=InMemoryRepository())

        try:
            from starlette.routing import WebSocketRoute  # type: ignore
        except Exception:  # pragma: no cover
            raise unittest.SkipTest("starlette is not installed")

        ws_routes = [
            r
            for r in getattr(app.router, "routes", [])
            if isinstance(r, WebSocketRoute) and getattr(r, "path", None) == "/api/v1/commissioning/projects/{projectId}/ws"
        ]
        self.assertEqual(len(ws_routes), 1, "Expected exactly one commissioning project websocket route.")

    def test_ws_emits_test_result_and_fail_tag_updated(self):
        TestClient = _require_fastapi()

        from sentinel.server.app.main import create_app
        from sentinel.server.services.repositories import InMemoryRepository

        app = create_app(repo=InMemoryRepository())
        client = TestClient(app)

        c = client.post("/api/v1/commissioning/clients", json={"name": "Client A"}).json()
        p = client.post(f"/api/v1/commissioning/clients/{c['clientId']}/projects", json={"name": "Project A"}).json()
        project_id = p["projectId"]

        target_key = "btn:1:2:3:Button A"

        with client.websocket_connect(f"/api/v1/commissioning/projects/{project_id}/ws") as ws:
            # Publish directly from inside the websocket portal thread so the
            # broker's asyncio queues are used from the correct event loop.
            broker = getattr(app.state, "project_event_broker", None)
            self.assertIsNotNone(broker)

            ws.portal.call(
                lambda: broker.publish(
                    projectId=project_id,
                    event={
                        "type": "test_result",
                        "projectId": project_id,
                        "recordedAtUtc": "2026-03-22T12:34:56.789123+00:00",
                        "targetKey": target_key,
                        "outcome": "PASS",
                        "targetName": "Button A",
                        "kind": "BUTTON",
                        "refs": {"deviceName": "Device 1"},
                    },
                )
            )

            msg1 = _recv_until(ws, lambda m: m.get("type") == "test_result" and m.get("targetKey") == target_key)
            self.assertEqual(msg1.get("projectId"), project_id)
            self.assertEqual(msg1.get("outcome"), "PASS")
            self.assertEqual(msg1.get("recordedAtUtc"), "2026-03-22T12:34:56.789123+00:00")
            self.assertIsNone(msg1.get("failNote"))

            ws.portal.call(
                lambda: broker.publish(
                    projectId=project_id,
                    event={
                        "type": "test_result",
                        "projectId": project_id,
                        "recordedAtUtc": "2026-03-22T12:36:56.789123+00:00",
                        "targetKey": target_key,
                        "outcome": "FAIL",
                        "targetName": "Button A",
                        "kind": "BUTTON",
                        "refs": {"deviceName": "Device 1"},
                        "failNote": "Button not responding",
                    },
                )
            )

            msg1b = _recv_until(ws, lambda m: m.get("type") == "test_result" and m.get("outcome") == "FAIL")
            self.assertEqual(msg1b.get("projectId"), project_id)
            self.assertEqual(msg1b.get("targetKey"), target_key)
            self.assertEqual(msg1b.get("recordedAtUtc"), "2026-03-22T12:36:56.789123+00:00")
            self.assertEqual(msg1b.get("failNote"), "Button not responding")

            ws.portal.call(
                lambda: broker.publish(
                    projectId=project_id,
                    event={
                        "type": "fail_tag_updated",
                        "projectId": project_id,
                        "recordedAtUtc": "2026-03-22T12:35:56.789123+00:00",
                        "targetKey": target_key,
                        "tag": "IN_PROGRESS",
                    },
                )
            )

            msg2 = _recv_until(ws, lambda m: m.get("type") == "fail_tag_updated" and m.get("targetKey") == target_key)
            self.assertEqual(msg2.get("projectId"), project_id)
            self.assertEqual(msg2.get("tag"), "IN_PROGRESS")

    def test_testing_ws_submit_is_slim_then_commissioning_rollups_follow(self):
        """test_result is ack-sized; progress/rollups arrive on a debounced commissioning_rollups event."""
        TestClient = _require_fastapi()

        from sentinel.server.app.main import create_app
        from sentinel.server.services.repositories import InMemoryRepository

        app = create_app(repo=InMemoryRepository())
        client = TestClient(app)

        c = client.post("/api/v1/commissioning/clients", json={"name": "Client A"}).json()
        p = client.post(f"/api/v1/commissioning/clients/{c['clientId']}/projects", json={"name": "Project A"}).json()
        project_id = p["projectId"]

        tech = client.post(f"/api/v1/commissioning/projects/{project_id}/tech-links", json={}).json()
        tech_token = str(tech.get("techUrl") or "").split("/")[-1]
        self.assertTrue(tech_token, "Expected tech token from techUrl.")

        with client.websocket_connect(f"/api/v1/testing/{tech_token}/ws") as ws:
            ws.send_text(
                json.dumps(
                    {
                        "type": "test_result.submit",
                        "target": {
                            "targetKey": "btn:1:2:3:Button A",
                            "targetName": "Button A",
                            "kind": "BUTTON",
                            "refs": {"deviceName": "Device 1"},
                        },
                        "outcome": "PASS",
                    }
                )
            )
            msg = _recv_until(ws, lambda m: m.get("type") == "test_result" and m.get("outcome") == "PASS")
            self.assertEqual(msg.get("projectId"), project_id)
            self.assertEqual(msg.get("targetKey"), "btn:1:2:3:Button A")
            self.assertNotIn("progress", msg)
            self.assertNotIn("rollups", msg)
            self.assertIsInstance(msg.get("seq"), int)
            time.sleep(0.25)
            roll = _recv_until(ws, lambda m: m.get("type") == "commissioning_rollups")
            self.assertEqual(roll.get("projectId"), project_id)
            self.assertIn("progress", roll)
            self.assertIn("rollups", roll)
            self.assertIsInstance(roll.get("seq"), int)

    def test_testing_ws_snapshot_includes_layer_locks_and_lock_updates(self):
        TestClient = _require_fastapi()

        from sentinel.server.app.main import create_app
        from sentinel.server.services.repositories import InMemoryRepository

        app = create_app(repo=InMemoryRepository())
        client = TestClient(app)

        c = client.post("/api/v1/commissioning/clients", json={"name": "Client A"}).json()
        p = client.post(f"/api/v1/commissioning/clients/{c['clientId']}/projects", json={"name": "Project A"}).json()
        project_id = p["projectId"]
        tech = client.post(f"/api/v1/commissioning/projects/{project_id}/tech-links", json={}).json()
        tech_token = str(tech.get("techUrl") or "").split("/")[-1]
        self.assertTrue(tech_token, "Expected tech token from techUrl.")

        with client.websocket_connect(f"/api/v1/testing/{tech_token}/ws") as ws:
            snapshot = _recv_until(ws, lambda m: m.get("type") == "testing_snapshot")
            self.assertEqual(snapshot.get("projectId"), project_id)
            self.assertEqual(snapshot.get("layerLocks"), [])
            ws.send_text(
                json.dumps(
                    {
                        "type": "layer_lock.set",
                        "scopeKey": "project::device::page",
                        "layerKey": "layer-1",
                        "visible": False,
                        "locked": True,
                    }
                )
            )
            event = _recv_until(ws, lambda m: m.get("type") == "layer_lock_state")
            self.assertEqual(event.get("projectId"), project_id)
            self.assertEqual(event.get("scopeKey"), "project::device::page")
            self.assertEqual(event.get("layerKey"), "layer-1")
            self.assertEqual(event.get("visible"), False)
            self.assertEqual(event.get("locked"), True)
            self.assertIsInstance(event.get("seq"), int)

        with client.websocket_connect(f"/api/v1/testing/{tech_token}/ws") as ws2:
            snapshot2 = _recv_until(ws2, lambda m: m.get("type") == "testing_snapshot")
            locks = list(snapshot2.get("layerLocks") or [])
            self.assertEqual(len(locks), 1)
            self.assertEqual(locks[0].get("scopeKey"), "project::device::page")
            self.assertEqual(locks[0].get("layerKey"), "layer-1")
            self.assertEqual(locks[0].get("visible"), False)
            self.assertEqual(locks[0].get("locked"), True)

    def test_testing_ws_submits_and_receives_progress_rollups(self):
        TestClient = _require_fastapi()

        from sentinel.server.app.main import create_app
        from sentinel.server.services.repositories import InMemoryRepository

        app = create_app(repo=InMemoryRepository())
        client = TestClient(app)

        c = client.post("/api/v1/commissioning/clients", json={"name": "Client A"}).json()
        p = client.post(f"/api/v1/commissioning/clients/{c['clientId']}/projects", json={"name": "Project A"}).json()
        project_id = p["projectId"]

        tech = client.post(f"/api/v1/commissioning/projects/{project_id}/tech-links", json={}).json()
        tech_token = str(tech.get("techUrl") or "").split("/")[-1]
        self.assertTrue(tech_token, "Expected tech token from techUrl.")

        with client.websocket_connect(f"/api/v1/testing/{tech_token}/ws") as ws:
            ws.send_text(
                json.dumps(
                    {
                        "type": "test_result.submit",
                        "target": {
                            "targetKey": "btn:1:2:3:Button A",
                            "targetName": "Button A",
                            "kind": "BUTTON",
                            "refs": {"deviceName": "Device 1"},
                        },
                        "outcome": "PASS",
                    }
                )
            )
            msg = _recv_until(ws, lambda m: m.get("type") in ("test_result", "test_result.recorded") and m.get("outcome") == "PASS")
            self.assertEqual(msg.get("projectId"), project_id)
            self.assertNotIn("progress", msg)
            self.assertNotIn("rollups", msg)
            self.assertIsInstance(msg.get("seq"), int)
            time.sleep(0.25)
            roll1 = _recv_until(ws, lambda m: m.get("type") == "commissioning_rollups")
            self.assertIn("progress", roll1)
            self.assertIn("rollups", roll1)

            ws.send_text(
                json.dumps(
                    {
                        "type": "test_result.submit",
                        "target": {
                            "targetKey": "btn:1:2:3:Button A",
                            "targetName": "Button A",
                            "kind": "BUTTON",
                            "refs": {"deviceName": "Device 1"},
                        },
                        "outcome": "FAIL",
                        "failNote": "Button not responding",
                    }
                )
            )
            msg2 = _recv_until(ws, lambda m: m.get("type") in ("test_result", "test_result.recorded") and m.get("outcome") == "FAIL")
            self.assertEqual(msg2.get("projectId"), project_id)
            self.assertEqual(msg2.get("failNote"), "Button not responding")
            self.assertNotIn("progress", msg2)
            self.assertNotIn("rollups", msg2)
            self.assertIsInstance(msg2.get("seq"), int)
            time.sleep(0.25)
            roll2 = _recv_until(ws, lambda m: m.get("type") == "commissioning_rollups")
            self.assertIn("progress", roll2)
            self.assertIn("rollups", roll2)

    def test_testing_submit_fanout_reaches_commissioning_ws(self):
        TestClient = _require_fastapi()

        from sentinel.server.app.main import create_app
        from sentinel.server.services.repositories import InMemoryRepository

        app = create_app(repo=InMemoryRepository())
        client = TestClient(app)

        c = client.post("/api/v1/commissioning/clients", json={"name": "Client A"}).json()
        p = client.post(f"/api/v1/commissioning/clients/{c['clientId']}/projects", json={"name": "Project A"}).json()
        project_id = p["projectId"]

        tech = client.post(f"/api/v1/commissioning/projects/{project_id}/tech-links", json={}).json()
        tech_token = str(tech.get("techUrl") or "").split("/")[-1]
        self.assertTrue(tech_token, "Expected tech token from techUrl.")

        with client.websocket_connect(f"/api/v1/commissioning/projects/{project_id}/ws") as commission_ws:
            snap = _recv_until(commission_ws, lambda m: m.get("type") == "commissioning_snapshot")
            self.assertEqual(snap.get("projectId"), project_id)
            self.assertIn("progress", snap)
            self.assertIn("rollups", snap)
            self.assertIn("activities", snap)
            self.assertIn("fails", snap)
            self.assertIn("activeUpload", snap)
            self.assertIsInstance(snap.get("seq"), int)

            with client.websocket_connect(f"/api/v1/testing/{tech_token}/ws") as tech_ws:
                tech_ws.send_text(
                    json.dumps(
                        {
                            "type": "test_result.submit",
                            "target": {
                                "targetKey": "btn:1:2:3:Button A",
                                "targetName": "Button A",
                                "kind": "BUTTON",
                                "refs": {
                                    "deviceName": "Device 1",
                                    "pageName": "Home",
                                    "buttonName": "Button A",
                                    "scope": "BUTTON",
                                },
                            },
                            "outcome": "PASS",
                        }
                    )
                )

                tech_msg = _recv_until(tech_ws, lambda m: m.get("type") == "test_result" and m.get("outcome") == "PASS")
                self.assertEqual(tech_msg.get("projectId"), project_id)

                commission_msg = _recv_until(commission_ws, lambda m: m.get("type") == "test_result" and m.get("outcome") == "PASS")
                self.assertEqual(commission_msg.get("projectId"), project_id)
                self.assertEqual(commission_msg.get("targetKey"), "btn:1:2:3:Button A")
