import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from comfy_pi_agent.local_llm import (
    configure_local_provider,
    llama_router_action,
    llama_router_models,
    probe_local_server,
    runtime_environment,
)
from comfy_pi_agent.pi_commands import BUILTIN_COMMANDS, parse_slash_command
from comfy_pi_agent.pi_runtime import build_pi_command


ROOT = Path(__file__).resolve().parents[1]


class SlashCommandTests(unittest.TestCase):
    def test_all_documented_pi_builtins_have_chat_bridges(self):
        expected = {
            "login", "logout", "llama", "model", "scoped-models", "settings",
            "resume", "new", "name", "session", "tree", "trust", "fork", "clone",
            "compact", "copy", "export", "import", "share", "reload", "hotkeys",
            "changelog", "quit",
        }
        self.assertEqual({item.name for item in BUILTIN_COMMANDS}, expected)

    def test_slash_parser_preserves_arguments(self):
        parsed = parse_slash_command('/model ollama "qwen2.5 coder:7b"')
        self.assertIsNotNone(parsed)
        name, args, raw = parsed
        self.assertEqual(name, "model")
        self.assertEqual(args, ["ollama", "qwen2.5 coder:7b"])
        self.assertEqual(raw, 'ollama "qwen2.5 coder:7b"')

    def test_non_command_and_double_slash_are_not_intercepted(self):
        self.assertIsNone(parse_slash_command("hello"))
        self.assertIsNone(parse_slash_command("// literal slash"))


    def test_every_catalog_builtin_has_explicit_handler_branch(self):
        import inspect
        from comfy_pi_agent.chat import ChatRuntimeManager
        source = inspect.getsource(ChatRuntimeManager._handle_builtin_command)
        for item in BUILTIN_COMMANDS:
            self.assertIn(f'"{item.name}"', source, item.name)

    def test_pi_launch_stays_lean_and_supports_scoped_models(self):
        command = build_pi_command("pi", provider="ollama", model="qwen", scoped_models="ollama/*")
        for flag in (
            "--mode", "--no-approve", "--no-context-files", "--no-extensions",
            "--no-skills", "--no-prompt-templates", "--no-themes", "--no-session",
        ):
            self.assertIn(flag, command)
        self.assertIn("--models", command)
        self.assertEqual(command[command.index("--models") + 1], "ollama/*")


class LocalLlmTests(unittest.TestCase):
    def test_llamacpp_uses_runtime_env_without_models_json(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict(os.environ, {"PI_CODING_AGENT_DIR": temp}, clear=False):
                result = configure_local_provider(
                    "llama.cpp",
                    "http://127.0.0.1:8080",
                    models=["Qwen3.5-9B"],
                    model="Qwen3.5-9B",
                )
                self.assertEqual(result["provider"], "llama.cpp")
                self.assertFalse((Path(temp) / "models.json").exists())
                self.assertEqual(
                    runtime_environment({"kind": "llama.cpp", "base_url": result["base_url"]}),
                    {"LLAMA_BASE_URL": "http://127.0.0.1:8080"},
                )

    def test_models_json_merge_preserves_existing_providers_and_never_stores_raw_key(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "models.json"
            path.write_text(json.dumps({"providers": {"existing": {"baseUrl": "http://example.invalid/v1", "models": [{"id": "keep-me"}]}}}), encoding="utf-8")
            with patch.dict(os.environ, {"PI_CODING_AGENT_DIR": temp}, clear=False):
                result = configure_local_provider(
                    "ollama",
                    "http://127.0.0.1:11434",
                    models=["qwen2.5:7b"],
                    model="qwen2.5:7b",
                )
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("existing", data["providers"])
            self.assertIn("ollama", data["providers"])
            self.assertEqual(data["providers"]["ollama"]["apiKey"], "ollama")
            self.assertEqual(result["model"], "qwen2.5:7b")

    def test_api_key_environment_reference_is_written_instead_of_secret(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict(os.environ, {"PI_CODING_AGENT_DIR": temp}, clear=False):
                configure_local_provider(
                    "openai-compatible",
                    "http://127.0.0.1:9999/v1",
                    models=["local-model"],
                    model="local-model",
                    provider_id="my-local",
                    api_key_env="LOCAL_LLM_API_KEY",
                )
            text = (Path(temp) / "models.json").read_text(encoding="utf-8")
            self.assertIn('"apiKey": "$LOCAL_LLM_API_KEY"', text)
            self.assertNotIn("super-secret", text)

    def test_ollama_and_openai_style_model_discovery(self):
        with patch("comfy_pi_agent.local_llm._json_request", return_value={"models": [{"name": "qwen:7b"}]}) as request:
            ollama = probe_local_server("ollama")
            self.assertTrue(ollama["available"])
            self.assertEqual(ollama["models"], ["qwen:7b"])
            self.assertTrue(request.call_args.args[0].endswith("/api/tags"))
        with patch("comfy_pi_agent.local_llm._json_request", return_value={"data": [{"id": "model-a"}, {"id": "model-b"}]}) as request:
            generic = probe_local_server("openai-compatible", "http://127.0.0.1:9000")
            self.assertTrue(generic["available"])
            self.assertEqual(generic["models"], ["model-a", "model-b"])
            self.assertTrue(request.call_args.args[0].endswith("/v1/models"))


    def test_llama_router_management_uses_router_endpoints_only_when_called(self):
        router_payload = {
            "data": [
                {"id": "loaded-model", "status": {"value": "loaded"}},
                {"id": "cold-model", "status": {"value": "unloaded"}},
            ]
        }
        with patch("comfy_pi_agent.local_llm._json_request", return_value=router_payload) as request:
            result = llama_router_models("http://127.0.0.1:8080")
            self.assertEqual([m["id"] for m in result["models"]], ["loaded-model", "cold-model"])
            self.assertTrue(request.call_args.args[0].endswith("/models"))
        with patch("comfy_pi_agent.local_llm._json_request", return_value={"success": True}) as request:
            result = llama_router_action("load", "loaded-model", "http://127.0.0.1:8080")
            self.assertTrue(result["ok"])
            self.assertTrue(request.call_args.args[0].endswith("/models/load"))
            self.assertEqual(request.call_args.kwargs["method"], "POST")
            self.assertEqual(request.call_args.kwargs["payload"], {"model": "loaded-model"})
        with patch("comfy_pi_agent.local_llm._json_request", return_value={"success": True}) as request:
            llama_router_action("download", "owner/model:Q4_K_M", "http://127.0.0.1:8080")
            self.assertTrue(request.call_args.args[0].endswith("/models"))

    def test_frontend_exposes_command_picker_and_explicit_local_detection(self):
        source = (ROOT / "web" / "pi_agent.js").read_text(encoding="utf-8")
        for needle in (
            "/pi-agent/chat/commands",
            "/pi-agent/local-llm/discover",
            "/pi-agent/local-llm/probe",
            "/pi-agent/local-llm/configure",
            "pi-agent-command-menu",
            "Detect common servers",
            "Type / for Pi commands",
        ):
            self.assertIn(needle, source)

    def test_local_server_discovery_is_not_called_at_import(self):
        # Import-time behavior is intentionally passive. The HTTP helper is referenced only
        # from explicit probe/discovery functions, not module top level.
        source = (ROOT / "comfy_pi_agent" / "local_llm.py").read_text(encoding="utf-8")
        top_level_before_functions = source.split("def _normalize_kind", 1)[0]
        self.assertNotIn("urlopen(", top_level_before_functions)


if __name__ == "__main__":
    unittest.main()
