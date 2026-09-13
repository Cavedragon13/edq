"""Folder-navigation regression tests; all mutations use temporary fixtures."""
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

source = os.environ.get('GALLERY_SOURCE', str(Path(__file__).with_name('dl_gallery.py')))
spec = importlib.util.spec_from_file_location('gallery', source)
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)


class NavigationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        g.DOWNLOADS = self.base / 'Downloads'
        g.AI_GENERATED = self.base / 'ai_generated'
        g.FAVORITES_FILE = self.base / 'favorites.json'
        g.THUMB_CACHE = self.base / 'thumbs'
        g.THUMB_CACHE.mkdir()
        self.folder = g.DOWNLOADS / 'CG Dream # & 雪' / '2025-02'
        self.folder.mkdir(parents=True)
        (g.DOWNLOADS / 'empty').mkdir()
        g.AI_GENERATED.mkdir()
        self.output = self.base / 'service-output'
        self.output.mkdir()
        (g.AI_GENERATED / 'linked-service').symlink_to(self.output)
        (self.folder / 'escape').symlink_to(self.base)
        self.filename = 'image # & <雪>.png'
        g.Image.new('RGB', (20, 20), 'blue').save(self.folder / self.filename)
        g.Image.new('RGB', (20, 20), 'red').save(g.DOWNLOADS / self.filename)
        self.relative = (self.folder / self.filename).relative_to(g.DOWNLOADS).as_posix()
        self.directory = self.folder.relative_to(g.DOWNLOADS).as_posix()
        self.server = g.ThreadingHTTPServer(('127.0.0.1', 0), g.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def get(self, path, method='GET'):
        with urlopen(Request(self.url + path, method=method)) as r:
            return r.read()

    def page(self, subdir='', root='downloads'):
        return self.get('/?' + urlencode({'root': root, 'dir': subdir})).decode()

    def asset(self, route, name=None, root='downloads'):
        return '/' + route + '/' + quote(name or self.relative, safe='') + '?' + urlencode({'root': root})

    def test_nested_navigation_and_media(self):
        root = self.page()
        self.assertIn('class="folder"', root)
        page = self.page(self.directory)
        self.assertIn('2025-02 — Gallery', page)
        self.assertIn('↑ Up', page)
        self.assertIn('CG+Dream+%23+%26+%E9%9B%AA', page)
        self.assertNotIn('>escape</a>', page)
        items = json.loads(re.search(r'const mediaItems = (.*);', page)[1])
        self.assertEqual([i['name'] for i in items], [self.relative])
        self.assertIn('%23%20%26%20%3C', page)
        self.assertIn('image # &amp; &lt;雪&gt;.png', page)
        self.assertTrue(self.get(self.asset('thumb')).startswith(b'\xff\xd8'))
        self.assertTrue(self.get(self.asset('img')).startswith(b'\x89PNG'))
        for block in re.findall(r'<script[^>]*>(.*?)</script>', page, re.S):
            result = subprocess.run(['node', '--check'], input=block, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_favorites_and_delete_keep_nested_identity(self):
        self.get(self.asset('favorite'), 'POST')
        self.assertIn(('downloads', self.relative), g.load_favorites())
        self.assertTrue(g.list_media(g.FAVORITES_KEY, g.AI_GENERATED, g.load_favorites())[0]['fav'])
        self.get(self.asset('delete'), 'POST')
        self.assertFalse((self.folder / self.filename).exists())
        self.assertTrue((g.DOWNLOADS / self.filename).exists())
        self.assertEqual(g.load_favorites(), set())

    def test_default_root_favorites(self):
        self.get('/favorite/' + quote(self.filename, safe=''), 'POST')
        page = self.get('/').decode()
        self.assertIn('"fav": true', page)

    def test_empty_folder_and_linked_service(self):
        self.assertIn('No images, videos, or subfolders here.', self.page('empty'))
        self.assertIn('id="ss-btn" disabled', self.page('empty'))
        (self.output / 'nested').mkdir()
        self.assertIn('class="folder"', self.page(root='linked-service'))
        self.assertIn('nested — Gallery', self.page('nested', 'linked-service'))

    def test_invalid_paths(self):
        for subdir in ['../', '/etc', self.directory + '/escape', 'missing', self.relative, '\x00']:
            with self.subTest(subdir=subdir), self.assertRaises(HTTPError) as error:
                self.page(subdir)
            self.assertEqual(error.exception.code, 404)
        for route in ['img', 'thumb', 'favorite', 'delete']:
            with self.subTest(route=route), self.assertRaises(HTTPError) as error:
                self.get(self.asset(route, '../outside.png'), 'POST' if route in ['favorite', 'delete'] else 'GET')
            self.assertEqual(error.exception.code, 404)


if __name__ == '__main__':
    unittest.main(verbosity=2)
