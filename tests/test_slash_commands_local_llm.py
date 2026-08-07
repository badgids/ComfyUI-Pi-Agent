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
    local_provider_presets,
    probe_local_server,
    runtime_environment,
)
from comfy_pi_agent.pi_commands import BUILTIN_COMMANDS, parse_slash_command
from comfy_pi_agent.pi_runtime import build_pi_command
from comfy_pi_agent.provider_catalog import PI_BUILTIN_PROVIDERS, provider_options, simplified_models


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
    def test_llamacpp_is_registered_in_pi_models_json_like_other_local_servers(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict(os.environ, {"PI_CODING_AGENT_DIR": temp}, clear=False):
                result = configure_local_provider(
                    "llama.cpp",
                    "http://127.0.0.1:8080",
                    models=["Qwen3.6-35B"],
                    model="Qwen3.6-35B",
                )
                self.assertEqual(result["provider"], "llama.cpp")
                self.assertEqual(result["model"], "Qwen3.6-35B")
                data = json.loads((Path(temp) / "models.json").read_text(encoding="utf-8"))
                provider = data["providers"]["llama.cpp"]
                self.assertEqual(provider["baseUrl"], "http://127.0.0.1:8080/v1")
                self.assertEqual(provider["api"], "openai-completions")
                self.assertEqual(provider["models"][0]["id"], "Qwen3.6-35B")
                self.assertEqual(runtime_environment({"kind": "llama.cpp", "base_url": result["base_url"]}), {})

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
            self.assertEqual(data["providers"]["ollama"]["apiKey"], "local")
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

    def test_llama_router_discovery_lists_all_routable_models(self):
        payload = {
            "data": [
                {"id": "loaded-model", "status": {"value": "loaded"}},
                {"id": "cold-model", "status": {"value": "unloaded"}},
                {"id": "sleeping-model", "status": {"value": "sleeping"}},
                {"id": "broken-model", "status": {"value": "unloaded", "failed": True}},
            ]
        }
        with patch("comfy_pi_agent.local_llm._json_request", return_value=payload) as request:
            result = probe_local_server("llama.cpp", "http://127.0.0.1:8080")
            self.assertTrue(result["available"])
            self.assertEqual(result["models"], ["cold-model", "loaded-model", "sleeping-model"])
            self.assertTrue(request.call_args.args[0].endswith("/models?reload=1"))

    def test_ollama_and_openai_style_model_discovery(self):
        with patch("comfy_pi_agent.local_llm._json_request", return_value={"models": [{"name": "qwen:7b"}, {"name": "llama3.1:8b"}, {"name": "gemma3:12b"}]}) as request:
            ollama = probe_local_server("ollama")
            self.assertTrue(ollama["available"])
            self.assertEqual(ollama["models"], ["gemma3:12b", "llama3.1:8b", "qwen:7b"])
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

    def test_frontend_uses_dead_simple_provider_and_model_dropdowns(self):
        source = (ROOT / "web" / "pi_agent.js").read_text(encoding="utf-8")
        for needle in (
            "/pi-agent/chat/commands",
            "/pi-agent/local-llm/configure",
            "/pi-agent/model/providers",
            "/pi-agent/chat/model-catalog",
            "/pi-agent/chat/model/select",
            'id="pi-agent-provider"',
            'id="pi-agent-model"',
            "Pi built-in providers",
            "Local model hosts",
            "Advanced: custom endpoint",
            "Endpoint override (optional)",
            "Provider and Model are selected directly beneath the chat box",
            "Type / for Pi commands",
        ):
            self.assertIn(needle, source)
        self.assertEqual(source.count('id="pi-agent-provider"'), 1)
        self.assertEqual(source.count('id="pi-agent-model"'), 1)
        textarea_at = source.index('id="pi-agent-chat-input"')
        provider_at = source.index('id="pi-agent-provider"')
        model_at = source.index('id="pi-agent-model"')
        status_at = source.index('id="pi-agent-statusline"')
        self.assertLess(textarea_at, provider_at)
        self.assertLess(provider_at, model_at)
        self.assertLess(model_at, status_at)
        for obsolete in (
            "Pi provider override",
            "Pi provider id (optional)",
            "Use in this chat",
            "Detect common servers",
        ):
            self.assertNotIn(obsolete, source)

    def test_provider_dropdown_covers_every_current_pi_known_provider(self):
        expected = {
            "amazon-bedrock", "ant-ling", "anthropic", "google", "google-vertex",
            "openai", "azure-openai-responses", "openai-codex", "radius", "nvidia",
            "deepseek", "github-copilot", "xai", "groq", "cerebras", "openrouter",
            "vercel-ai-gateway", "zai", "zai-coding-cn", "mistral", "minimax",
            "minimax-cn", "moonshotai", "moonshotai-cn", "huggingface", "fireworks",
            "together", "opencode", "opencode-go", "kimi-coding",
            "cloudflare-workers-ai", "cloudflare-ai-gateway", "qwen-token-plan",
            "qwen-token-plan-cn", "xiaomi",
            "xiaomi-token-plan-cn", "xiaomi-token-plan-ams", "xiaomi-token-plan-sgp",
        }
        self.assertEqual({provider_id for provider_id, _label in PI_BUILTIN_PROVIDERS}, expected)
        options = provider_options([])
        selectors = {item["selector"] for item in options}
        self.assertTrue(expected.issubset(selectors))
        for local in {"llama.cpp", "ollama", "lm-studio", "vllm", "openai-compatible"}:
            self.assertIn(local, selectors)

    def test_model_catalog_keeps_all_models_grouped_by_provider(self):
        models = simplified_models([
            {"provider": "openai-codex", "id": "gpt-5.5", "name": "GPT-5.5"},
            {"provider": "openai-codex", "id": "gpt-5.6-sol", "name": "GPT-5.6 Sol"},
            {"provider": "anthropic", "id": "claude-sonnet", "name": "Claude Sonnet"},
        ])
        self.assertEqual(len(models), 3)
        self.assertEqual([item["id"] for item in models if item["provider"] == "openai-codex"], ["gpt-5.5", "gpt-5.6-sol"])

    def test_local_provider_presets_are_metadata_only(self):
        presets = {item["kind"]: item for item in local_provider_presets()}
        self.assertEqual(presets["llama.cpp"]["provider"], "llama.cpp")
        self.assertEqual(presets["llama.cpp"]["default_base_url"], "http://127.0.0.1:8080")
        self.assertEqual(presets["ollama"]["provider"], "ollama")

    def test_old_url_in_provider_field_is_repaired(self):
        from comfy_pi_agent.chat import _normalized_provider_model
        provider, model = _normalized_provider_model(
            "http://127.0.0.1:8080",
            "",
            {"kind": "llama.cpp", "model": "Qwen3.6-35B"},
        )
        self.assertEqual(provider, "llama.cpp")
        self.assertEqual(model, "Qwen3.6-35B")

    def test_model_command_treats_local_provider_name_as_provider_selection(self):
        import inspect
        from comfy_pi_agent.chat import ChatRuntimeManager
        source = inspect.getsource(ChatRuntimeManager._handle_builtin_command)
        self.assertIn('len(args) == 1 and first.lower() in local_aliases', source)
        self.assertIn('self.activate_local_provider', source)

    def test_llama_router_dropdown_switch_requests_load_for_unloaded_model(self):
        import threading
        from types import SimpleNamespace
        from unittest.mock import Mock
        from comfy_pi_agent.chat import ChatRuntimeManager

        with tempfile.TemporaryDirectory() as temp:
            with patch("comfy_pi_agent.chat._session_root", return_value=Path(temp)):
                manager = ChatRuntimeManager()
                document = manager.store.create(provider="llama.cpp", model="loaded-model")
                document["local_llm"] = {
                    "enabled": True,
                    "kind": "llama.cpp",
                    "base_url": "http://127.0.0.1:8080",
                    "provider": "llama.cpp",
                    "model": "loaded-model",
                    "models": ["loaded-model", "cold-model"],
                }
                manager.store.save(document)
                client = Mock()
                client.set_model.return_value = {"provider": "llama.cpp", "id": "cold-model", "name": "cold-model"}
                live = SimpleNamespace(client=client, lock=threading.Lock(), provider="llama.cpp", model="loaded-model")
                manager._live[document["session_id"]] = live
                with patch("comfy_pi_agent.chat.llama_router_models", return_value={"ok": True, "models": [{"id": "cold-model", "status": "unloaded", "failed": False}]}), \
                     patch("comfy_pi_agent.chat.llama_router_action", return_value={"ok": True}) as load:
                    _result, saved = manager.select_model(document["session_id"], "llama.cpp", "cold-model")
                load.assert_called_once_with("load", "cold-model", "http://127.0.0.1:8080", timeout=20.0)
                client.set_model.assert_called_once_with("llama.cpp", "cold-model")
                self.assertEqual(saved["local_llm"]["model"], "cold-model")

    def test_main_dropdown_model_switch_uses_live_pi_rpc_when_available(self):
        import threading
        from types import SimpleNamespace
        from unittest.mock import Mock
        from comfy_pi_agent.chat import ChatRuntimeManager

        with tempfile.TemporaryDirectory() as temp:
            with patch("comfy_pi_agent.chat._session_root", return_value=Path(temp)):
                manager = ChatRuntimeManager()
                document = manager.store.create(provider="openai-codex", model="gpt-5.5")
                client = Mock()
                client.set_model.return_value = {"provider": "openai-codex", "id": "gpt-5.6-sol", "name": "GPT-5.6 Sol"}
                live = SimpleNamespace(client=client, lock=threading.Lock(), provider="openai-codex", model="gpt-5.5")
                manager._live[document["session_id"]] = live
                result, saved = manager.select_model(document["session_id"], "openai-codex", "gpt-5.6-sol")
                client.set_model.assert_called_once_with("openai-codex", "gpt-5.6-sol")
                self.assertTrue(result["switched_live"])
                self.assertEqual(saved["provider"], "openai-codex")
                self.assertEqual(saved["model"], "gpt-5.6-sol")
                self.assertEqual(live.model, "gpt-5.6-sol")

    def test_local_server_discovery_is_not_called_at_import(self):
        # Import-time behavior is intentionally passive. The HTTP helper is referenced only
        # from explicit probe/discovery functions, not module top level.
        source = (ROOT / "comfy_pi_agent" / "local_llm.py").read_text(encoding="utf-8")
        top_level_before_functions = source.split("def _normalize_kind", 1)[0]
        self.assertNotIn("urlopen(", top_level_before_functions)


if __name__ == "__main__":
    unittest.main()
