"""Check limde-preview's file classification and helpers offline. Opens no window."""
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "limde-preview"
loader = SourceFileLoader("limde_preview", str(SCRIPT))
preview = module_from_spec(spec_from_loader("limde_preview", loader))
loader.exec_module(preview)


class PreviewTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def file(self, name, data):
        path = self.root / name
        path.write_bytes(data)
        return path

    def test_classify_by_type(self):
        f = self.file("x", b"data")
        self.assertEqual(preview.classify(f, "application/pdf"), "pdf")
        self.assertEqual(preview.classify(f, "image/svg+xml"), "svg")
        self.assertEqual(preview.classify(f, "image/png"), "image")
        self.assertEqual(preview.classify(f, "text/x-python"), "text")
        self.assertEqual(preview.classify(f, "application/json"), "text")
        self.assertEqual(preview.classify(f, "application/zip"), "other")
        self.assertEqual(preview.classify(self.root, "inode/directory"), "other")

    def test_unknown_extension_is_sniffed(self):
        self.assertEqual(preview.classify(self.file("a.conf9", b"[a]\nb = 1\n"),
                                          "application/octet-stream"), "text")
        self.assertEqual(preview.classify(self.file("b.bin", bytes(range(256)) * 4),
                                          "application/octet-stream"), "other")
        # A multibyte character cut at the 4 KB boundary is still text.
        cut = b"a" * 4095 + "é".encode()
        self.assertEqual(preview.classify(self.file("c.log9", cut), "application/octet-stream"), "text")

    def test_read_text_stops_at_the_limit(self):
        f = self.file("long.txt", b"x" * 20)
        self.assertEqual(preview.read_text(f, limit=50), "x" * 20)
        self.assertTrue(preview.read_text(f, limit=10).startswith("x" * 10 + "\n\n[…"))
        self.assertIn("�", preview.read_text(self.file("bad.txt", b"\xff ok")))

    def test_pdf_command_renders_the_requested_pages(self):
        self.assertEqual(preview.pdf_command(Path("/d/a.pdf"), Path("/t/p"), 2, 50),
                         ["pdftoppm", "-png", "-r", "110", "-f", "2", "-l", "50", "/d/a.pdf", "/t/p"])

    def test_human_size(self):
        self.assertEqual(preview.human_size(999), "999 bytes")
        self.assertEqual(preview.human_size(1500), "1.5 KB")
        self.assertEqual(preview.human_size(2_500_000_000), "2.5 GB")

    def test_pdf_page_sizes_reads_pdfinfo(self):
        out = "Pages:           3\nPage    1 size:  2592 x 1728 pts\nPage    2 size:  612 x 792 pts (letter)\n"
        self.assertEqual(preview.pdf_page_sizes(out), [(2592.0, 1728.0), (612.0, 792.0)])
        self.assertEqual(preview.pdf_page_sizes("Title: x\n"), [])
        self.assertEqual(preview.pdf_page_count(out), 3)
        self.assertEqual(preview.pdf_page_count("Title: x\n"), 0)

    def test_page_at_follows_the_middle_of_the_view(self):
        tops = [12, 1112, 2212]  # 1088 px pages, 12 px gaps
        self.assertEqual(preview.page_at(tops, 0, 800), 1)
        self.assertEqual(preview.page_at(tops, 800, 800), 2)
        self.assertEqual(preview.page_at(tops, 5000, 800), 3)

    def test_zoom_keeps_the_point_under_the_pointer(self):
        # Content point 300 sits under the pointer at 100 (scrolled 200); after 2x it is at 600.
        self.assertEqual(preview.zoom_scroll(200, 100, 2.0), 500)
        self.assertEqual(preview.zoom_scroll(0, 50, 0.5), 0)

    def test_fit_scales_down_only(self):
        self.assertEqual(preview.fit(500, 400, 1920, 1200), (500, 400))
        self.assertEqual(preview.fit(935, 1210, 1920, 1200), (741, 960))

    def folder(self, sort, hidden="0", own=None):
        config = self.root / "config"
        (config / "pcmanfm/default").mkdir(parents=True, exist_ok=True)
        (config / "pcmanfm/default/pcmanfm.conf").write_text(f"[ui]\nsort={sort}\nshow_hidden={hidden}\n")
        docs = self.root / "docs"
        docs.mkdir(exist_ok=True)
        if own:
            (config / "libfm").mkdir(exist_ok=True)
            (config / "libfm/dir-settings.conf").write_text(f"[{docs}]\n{own}\n")
        for i, name in enumerate(["b.txt", "file10.pdf", "file2.pdf", ".hidden", "A.png"]):
            f = docs / name
            f.write_bytes(b"x" * (i + 1))
            os.utime(f, (1000 + i, 1000 + i))
        (docs / "sub").mkdir(exist_ok=True)
        return config, docs

    def names(self, config, docs, start="b.txt"):
        return [p.name for p in preview.folder_order(docs / start, config)]

    def test_folder_order_follows_pcmanfm_name_sort_naturally(self):
        config, docs = self.folder("name;ascending;")
        self.assertEqual(self.names(config, docs), ["sub", "A.png", "b.txt", "file2.pdf", "file10.pdf"])

    def test_folder_order_mtime_descending_hidden_and_mingle(self):
        config, docs = self.folder("mtime;descending;", hidden="1")
        self.assertEqual(self.names(config, docs), ["sub", "A.png", ".hidden", "file2.pdf", "file10.pdf", "b.txt"])
        config, docs = self.folder("size;ascending;mingle;")
        self.assertEqual(self.names(config, docs)[-1], "A.png")
        self.assertNotIn(".hidden", self.names(config, docs))
        self.assertIn(".hidden", self.names(config, docs, start=".hidden"))

    def test_per_folder_settings_override_the_default(self):
        config, docs = self.folder("name;ascending;", own="Sort=name;descending;\nShowHidden=true")
        self.assertEqual(self.names(config, docs)[:2], ["sub", "file10.pdf"])
        self.assertIn(".hidden", self.names(config, docs))

    def test_wrong_arguments_print_usage(self):
        done = subprocess.run([sys.executable, "-I", SCRIPT], capture_output=True, text=True)
        self.assertEqual(done.returncode, 2)
        self.assertIn("limde-preview FILE", done.stderr)


if __name__ == "__main__":
    unittest.main()
