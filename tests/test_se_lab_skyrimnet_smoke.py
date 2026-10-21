import copy
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from hold_music import se_lab_skyrimnet_smoke as smoke
from tools import se_lab_skyrimnet_smoke as cli

RUN = "20261021T100000Z-123456789abc"
SECRET = "NEVER-EXPORT-SECRET-SENTINEL"


def response(name):
    data = {}
    for path, value in smoke.CHECKS[name].items():
        target = data
        parts = path.split(".")
        for key in parts[:-1]:
            target = target.setdefault(key, {})
        target[parts[-1]] = value
    return {"data": data, "private": {"api_key": SECRET}}


def tcp(pid=12):
    return [dict(local_address="127.0.0.1", local_port=port, remote_address="0.0.0.0",
                 remote_port=0, state="Listen", pid=pid) for port in (18880, 18889)]


class SmokeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.runtime = self.root / smoke.tier.RUNTIME_CONTROL
        self.runtime.mkdir()
        (self.root / smoke.tier.CONTROL).mkdir()
        self.started = 1700000000000000000
        ticks = self.started // 100 + 621355968000000000
        paths = [self.root / smoke.tier.INSTANCE / "ModOrganizer.exe",
                 self.root / "Game/skse64_loader.exe", self.root / "Game/SkyrimSE.exe"]
        self.processes = [dict(pid=10+i, parent_pid=9+i, path=str(p), created_ticks=ticks+i+1)
                          for i, p in enumerate(paths)]
        self.modules = []
        files = {}
        for name in sorted(smoke.tier.NATIVE_DLLS):
            relative = "mods/Approved " + name + "/SKSE/Plugins/" + name
            path = self.root / smoke.tier.INSTANCE / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(name.encode())
            files[relative] = dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            self.modules.append(dict(name=name, path=str(path)))
        self.inputs = dict(implementation={"frozen": "hash"}, protected={"baseline": "unchanged"},
                           instance={"files": files})
        self.run = dict(version=1, tier=smoke.tier.TIER, run_id=RUN, operation="skyrimnet_disabled_first_boot",
                        inputs=self.inputs, inputs_sha256=smoke.tier._digest(self.inputs),
                        launch_command=smoke.tier._runtime_command(self.root), started_ns=self.started)
        self.launch = dict(tier=smoke.tier.TIER, run_id=RUN, process_started=True, launcher_pid=10,
                           processes=self.processes, game=self.processes[-1], launch_attributed=True)
        self.write_documents()
        for name, value in (("_root", self.root), ("_implementation", self.inputs["implementation"]),
                            ("_protected", self.inputs["protected"])):
            mock = patch.object(smoke.tier, name, return_value=value)
            mock.start(); self.addCleanup(mock.stop)
        self.rows = tcp()
        self.kw = dict(process_probe=lambda: copy.deepcopy(self.processes),
                       module_probe=lambda pid: copy.deepcopy(self.modules),
                       connection_probe=lambda: copy.deepcopy(self.rows))
        self.calls = []

    def write_documents(self):
        for name, value in (("run.json", self.run), ("launch-result.json", self.launch)):
            (self.runtime / name).write_text(json.dumps(value))

    def transport(self, route, pid, deadline, verify, connections):
        self.calls.append(route)
        verify()
        self.assertEqual(pid, 12)
        return json.dumps(response(route.split("name=", 1)[1])).encode()

    def plan(self):
        return smoke.smoke_plan(RUN, **self.kw)

    def collect(self, token=None, transport=None):
        return smoke.collect_smoke(RUN, token or self.plan()["review_token"],
                                   transport=transport or self.transport, **self.kw)

    def test_plan_is_readonly_and_does_not_connect(self):
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with patch.object(smoke.socket, "socket", side_effect=AssertionError("no sockets")):
            report = self.plan()
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})
        self.assertFalse(report["network_requests_performed"])
        self.assertEqual(len(report["binding"]["modules"]), 7)

    def test_happy_capture_exports_only_fixed_safe_projection(self):
        report = self.collect()
        self.assertEqual(report["status"], "disabled_controls_observed")
        self.assertEqual(self.calls, list(smoke.ROUTES))
        self.assertTrue(report["identity_stable"])
        self.assertFalse(report["runtime_verified"])
        self.assertFalse(report["credentials_verified"])
        captures = list((self.runtime / "smoke").glob("*.json"))
        self.assertEqual(len(captures), 1)
        self.assertNotIn(SECRET, captures[0].read_text())
        self.assertNotIn("api_key", captures[0].read_text())

    def test_stale_cross_operation_and_unicode_tokens_send_nothing(self):
        for token in ("skyrimnet-launch-v1:wrong", "not-a-token", "é"):
            with self.subTest(token=token), self.assertRaises(ValueError):
                self.collect(token)
        self.assertFalse(self.calls)

    def test_reused_pid_or_missing_lineage_refuses(self):
        for change in ("ticks", "parent", "attribution"):
            with self.subTest(change=change):
                original = copy.deepcopy(self.processes)
                if change == "ticks": self.processes[-1]["created_ticks"] += 1
                elif change == "parent": self.processes[-1]["parent_pid"] = 99
                else:
                    self.launch["launch_attributed"] = False;self.write_documents()
                with self.assertRaises(ValueError): self.plan()
                self.processes[:] = original
                self.launch["launch_attributed"] = True;self.write_documents()

    def test_foreign_wildcard_missing_or_duplicate_listener_refuses(self):
        original = copy.deepcopy(self.rows)
        for change in ("foreign", "wildcard", "missing", "duplicate", "malformed"):
            self.rows[:] = copy.deepcopy(original)
            if change == "foreign": self.rows[0]["pid"] = 999
            elif change == "wildcard": self.rows[0]["local_address"] = "0.0.0.0"
            elif change == "missing": self.rows.pop()
            elif change == "duplicate": self.rows.append(dict(self.rows[0]))
            else: self.rows.append({"private": SECRET})
            with self.subTest(change=change), self.assertRaises(ValueError):self.plan()

    def test_missing_foreign_or_virtual_module_path_fails_closed(self):
        original = copy.deepcopy(self.modules)
        for change in ("missing", "foreign", "virtual", "duplicate"):
            self.modules[:] = copy.deepcopy(original)
            if change == "missing": self.modules.pop()
            elif change == "foreign": self.modules[0]["path"] = str(self.root / "outside.dll")
            elif change == "virtual": self.modules[0]["path"] = str(self.root / "Game/Data/SKSE/Plugins" / self.modules[0]["name"])
            else: self.modules[-1] = dict(self.modules[0])
            with self.subTest(change=change), self.assertRaises(ValueError):self.plan()

    def test_changed_module_after_plan_sends_nothing(self):
        token = self.plan()["review_token"]
        Path(self.modules[0]["path"]).write_bytes(b"different")
        with self.assertRaises(ValueError): self.collect(token)
        self.assertFalse(self.calls)

    def test_changed_launch_document_invalidates_review_without_http(self):
        token = self.plan()["review_token"]
        self.launch["capture_note"] = "later observation"
        self.write_documents()
        with self.assertRaises(ValueError): self.collect(token)
        self.assertFalse(self.calls)

    def test_protected_state_drift_refuses_before_http(self):
        token = self.plan()["review_token"]
        with patch.object(smoke.tier, "_protected", return_value={"baseline": "changed"}), self.assertRaises(ValueError):
            self.collect(token)
        self.assertFalse(self.calls)

    def test_wrong_types_values_and_missing_controls_never_export_values(self):
        for bad in ("false", 0, True, SECRET, None):
            def transport(*args):
                payload = response("game")
                payload["data"]["general"]["globalAIEnabled"] = bad
                return json.dumps(payload).encode()
            with self.subTest(bad=bad):
                report = self.collect(transport=transport)
                self.assertFalse(report["disabled_controls_observed"])
                self.assertNotIn(SECRET, json.dumps(report))

    def test_duplicate_json_and_private_exception_are_sanitized(self):
        for payload in (b'{"data":{},"data":{}}',b'{"error":"'+SECRET.encode()+b'"}',b'{"data":{"x":NaN}}'):
            report = self.collect(transport=lambda *args: payload)
            self.assertEqual(report["observation_failure"], "bounded_observation_failed")
            self.assertNotIn(SECRET, json.dumps(report))
        def fail(*args):raise OSError(SECRET)
        self.assertNotIn(SECRET, json.dumps(self.collect(transport=fail)))

    def test_process_exit_stops_subsequent_requests(self):
        def exit_after_get(*args):
            raw = self.transport(*args)
            self.processes.pop()
            return raw
        report = self.collect(transport=exit_after_get)
        self.assertEqual(len(self.calls), 1)
        self.assertFalse(report["identity_stable"])
        self.assertFalse(report["live_snapshot_complete"])

    def test_module_change_during_read_refuses_complete_claim(self):
        def change(*args):
            raw = self.transport(*args)
            Path(self.modules[0]["path"]).write_bytes(b"changed")
            return raw
        report = self.collect(transport=change)
        self.assertFalse(report["identity_stable"])
        self.assertFalse(report["disabled_controls_observed"])

    def test_cli_sanitizes_preflight_errors(self):
        import io
        output = io.StringIO()
        with patch.object(cli, "smoke_plan", side_effect=ValueError(SECRET)), patch("sys.stdout", output):
            self.assertEqual(cli.main(["plan", "--run-id", RUN]), 1)
        self.assertNotIn(SECRET, output.getvalue())


class FakeSocket:
    def __init__(self, response):self.response=response;self.sent=[];self.connected=[]
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def settimeout(self,value):pass
    def connect(self,address):self.connected.append(address)
    def getsockname(self):return ("127.0.0.1",53123)
    def sendall(self,raw):self.sent.append(raw)
    def recv(self,size):raw,self.response=self.response[:size],self.response[size:];return raw


class HTTPTests(unittest.TestCase):
    def raw(self,body=b'{"data":{}}',status=b'200 OK',extra=b''):
        return b'HTTP/1.1 '+status+b'\r\nContent-Type: application/json\r\nContent-Length: '+str(len(body)).encode()+b'\r\n'+extra+b'\r\n'+body
    def run_get(self,raw,peer=12,route=None):
        sock=FakeSocket(raw)
        rows=tcp()+[dict(local_address="127.0.0.1",local_port=18880,remote_address="127.0.0.1",remote_port=53123,state="Established",pid=peer)]
        with patch.object(smoke.socket,"socket",return_value=sock):
            result=smoke._http_get(route or smoke.ROUTES[0],12,time.monotonic()+30,lambda:None,lambda:rows)
        return result,sock
    def test_exact_connection_and_get_without_proxy_or_auth(self):
        with patch.dict("os.environ",{"HTTP_PROXY":"http://evil.invalid","HTTPS_PROXY":"http://evil.invalid","NO_PROXY":""}):
            body,sock=self.run_get(self.raw())
        self.assertEqual(body,b'{"data":{}}')
        self.assertEqual(sock.connected,[("127.0.0.1",18880)])
        request=sock.sent[0]
        self.assertTrue(request.startswith(b'GET /config?api=get&name=game HTTP/1.1'))
        self.assertNotIn(b'Authorization',request);self.assertNotIn(b'Cookie',request)
    def test_foreign_accepted_connection_refuses_before_sending(self):
        sock=FakeSocket(self.raw());rows=tcp()+[dict(local_address="127.0.0.1",local_port=18880,remote_address="127.0.0.1",remote_port=53123,state="Established",pid=999)]
        with patch.object(smoke.socket,"socket",return_value=sock),self.assertRaises(ValueError):
            smoke._http_get(smoke.ROUTES[0],12,time.monotonic()+30,lambda:None,lambda:rows)
        self.assertFalse(sock.sent)
    def test_listener_takeover_after_response_is_not_accepted_or_retried(self):
        sock=FakeSocket(self.raw())
        established=dict(local_address="127.0.0.1",local_port=18880,remote_address="127.0.0.1",remote_port=53123,state="Established",pid=12)
        rows=iter([tcp()+[established],tcp(999)])
        with patch.object(smoke.socket,"socket",return_value=sock),self.assertRaises(ValueError):
            smoke._http_get(smoke.ROUTES[0],12,time.monotonic()+30,lambda:None,lambda:next(rows))
        self.assertEqual(len(sock.sent),1)
    def test_expired_deadline_never_connects(self):
        sock=FakeSocket(self.raw())
        with patch.object(smoke.socket,"socket",return_value=sock),self.assertRaises(ValueError):
            smoke._http_get(smoke.ROUTES[0],12,time.monotonic()-1,lambda:None,lambda:tcp())
        self.assertFalse(sock.connected)
    def test_redirect_auth_chunked_compressed_and_wrong_length_refuse(self):
        for raw in (self.raw(status=b'302 Found',extra=b'Location: http://evil.invalid/\r\n'),
                    self.raw(status=b'401 Unauthorized'),self.raw(extra=b'Transfer-Encoding: chunked\r\n'),
                    self.raw(extra=b'Content-Encoding: gzip\r\n'),self.raw()+b'extra'):
            with self.subTest(raw=raw[:45]),self.assertRaises(ValueError):self.run_get(raw)
    def test_oversized_header_body_duplicate_headers_and_nonallowlisted_route(self):
        for raw in (b'HTTP/1.1 200 OK\r\nX: '+b'x'*smoke.MAX_HEADERS,
                    b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 9999999\r\n\r\n',
                    self.raw(extra=b'Content-Length: 1\r\n')):
            with self.assertRaises(ValueError):self.run_get(raw)
        with self.assertRaises(ValueError):self.run_get(self.raw(),route='/auth')


if __name__ == "__main__":unittest.main()
