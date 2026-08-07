import importlib.util
import sys
import unittest
from pathlib import Path


class PackageEntrypointTests(unittest.TestCase):
    def test_repository_entrypoint_loads_by_path(self):
        root = Path(__file__).resolve().parents[1]
        name = "ComfyUI-Pi-Agent-test"
        spec = importlib.util.spec_from_file_location(name, root / "__init__.py", submodule_search_locations=[str(root)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
            self.assertGreaterEqual(len(module.NODE_CLASS_MAPPINGS), 30)
            self.assertEqual(module.WEB_DIRECTORY, "./web")
        finally:
            sys.modules.pop(name, None)


if __name__ == "__main__":
    unittest.main()
