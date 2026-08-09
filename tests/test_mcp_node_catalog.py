import tempfile
import unittest
from pathlib import Path
from comfy_pi_agent.mcp.node_catalog import NodeCatalogStore, node_schema_hash

class NodeCatalogTests(unittest.TestCase):
    def test_volatile_widget_default_does_not_change_schema_hash(self):
        left={"input":{"required":{"seed":["INT",{"default":1,"min":0}]}} ,"output":["LATENT"]}
        right={"input":{"required":{"seed":["INT",{"default":999,"min":0}]}} ,"output":["LATENT"]}
        self.assertEqual(node_schema_hash("Sampler",left),node_schema_hash("Sampler",right))
        right["output"]=["IMAGE"]
        self.assertNotEqual(node_schema_hash("Sampler",left),node_schema_hash("Sampler",right))

    def test_reconcile_generations_and_schema_scoped_lessons(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=NodeCatalogStore(Path(tmp)/"catalog.sqlite3")
            a={"A":{"display_name":"A","python_module":"nodes","input":{},"output":["X"]}}
            first=store.reconcile(a,source="test")
            h=node_schema_hash("A",a["A"]); store.put_lesson("A",h,"edge",{"to":"B"})
            second=store.reconcile({"B":{"display_name":"B","python_module":"custom_nodes.pack","input":{},"output":[]}},source="test")
            self.assertEqual(first["generation"]+1,second["generation"])
            self.assertEqual(store.lessons("A",h)[0]["payload"],{"to":"B"})
            self.assertEqual(store.search("A"),[])
            store.close()

if __name__ == "__main__": unittest.main()
