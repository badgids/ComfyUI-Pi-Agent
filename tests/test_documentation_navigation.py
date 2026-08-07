import re
import unittest
from collections import deque
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


def local_targets(path: Path):
    text = path.read_text(encoding="utf-8")
    targets = []
    for raw in LINK_RE.findall(text):
        raw = raw.strip()
        if not raw or raw.startswith(("http://", "https://", "mailto:", "#")):
            continue
        # Markdown destinations may optionally use <...>.
        if raw.startswith("<") and raw.endswith(">"):
            raw = raw[1:-1]
        raw = raw.split("#", 1)[0].split("?", 1)[0]
        if not raw:
            continue
        target = (path.parent / unquote(raw)).resolve()
        targets.append(target)
    return targets


class DocumentationNavigationTests(unittest.TestCase):
    def test_all_local_documentation_links_resolve(self):
        problems = []
        for path in ROOT.rglob("*.md"):
            for target in local_targets(path):
                try:
                    target.relative_to(ROOT.resolve())
                except ValueError:
                    # Local links must not escape the repository.
                    problems.append(f"{path.relative_to(ROOT)} -> outside repo: {target}")
                    continue
                if not target.exists():
                    problems.append(f"{path.relative_to(ROOT)} -> missing: {target.relative_to(ROOT)}")
        self.assertEqual(problems, [], "Broken documentation links:\n" + "\n".join(problems))

    def test_every_markdown_document_is_reachable_from_root_readme(self):
        markdown = {p.resolve() for p in ROOT.rglob("*.md")}
        start = (ROOT / "README.md").resolve()
        seen = {start}
        queue = deque([start])
        while queue:
            current = queue.popleft()
            for target in local_targets(current):
                if target.suffix.lower() != ".md" or target not in markdown or target in seen:
                    continue
                seen.add(target)
                queue.append(target)
        unreachable = sorted(str(p.relative_to(ROOT.resolve())) for p in markdown - seen)
        self.assertEqual(unreachable, [], "Markdown files unreachable from README.md:\n" + "\n".join(unreachable))

    def test_every_non_root_markdown_page_has_navigation_back_up(self):
        missing = []
        for path in ROOT.rglob("*.md"):
            if path == ROOT / "README.md":
                continue
            text = path.read_text(encoding="utf-8")
            if "Project README" not in text or "Documentation home" not in text:
                missing.append(str(path.relative_to(ROOT)))
        self.assertEqual(missing, [], "Documentation pages missing parent navigation:\n" + "\n".join(missing))

    def test_root_readme_links_documentation_hub_and_subindexes(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("[Documentation home](docs/index.md)", readme)
        self.assertIn("[Example workflows](examples/workflows/README.md)", readme)
        self.assertIn("[Bundled Pi skills and procedures](pi/bundled-skills/README.md)", readme)
        self.assertIn("[Project inventory](PROJECT_INVENTORY.md)", readme)
        self.assertIn("[Release notes](RELEASE_NOTES.md)", readme)


if __name__ == "__main__":
    unittest.main()
