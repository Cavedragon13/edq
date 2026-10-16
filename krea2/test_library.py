import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import Request
from unittest.mock import patch

from krea2_library import Library, ScopedRedirect, file_hash, tensor_header


def weights(data=b'abcd', name='diffusion_model.test.lora_A.weight'):
    header=json.dumps({name:{'dtype':'U8','shape':[len(data)],'data_offsets':[0,len(data)]}}).encode()
    return len(header).to_bytes(8,'little')+header+data


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.path=self.root/'favorite.safetensors';self.path.write_bytes(weights())
        self.lock=threading.Lock()
        self.library=Library(self.root,self.root/'logs',self.root/'manifest.json',self.lock)
        self.new=self.root/'new.download';self.new.write_bytes(weights(b'efgh'))
        self.row={'sha256':file_hash(self.path),'expected':file_hash(self.new),
                  'download':'https://civitai.com/api/download/models/123','latest':'v2'}

    def test_atomic_update_keeps_old_weights_and_filename(self):
        with patch('krea2_library.urlopen',return_value=io.BytesIO(self.new.read_bytes())):
            self.library.install(self.path,self.row)
        self.assertEqual(self.path.read_bytes(),weights(b'efgh'))
        self.assertEqual(Path(self.row['backup']).read_bytes(),weights())
        self.library.store(self.path.name,self.row)
        self.library.restore(self.path.name)
        self.assertEqual(self.path.read_bytes(),weights())
        self.assertEqual(Path(self.library.rows[self.path.name]['backup']).read_bytes(),weights(b'efgh'))

    def test_checksum_failure_keeps_original(self):
        with patch('krea2_library.urlopen',return_value=io.BytesIO(weights(b'bad'))):
            with self.assertRaisesRegex(ValueError,'checksum'):
                self.library.install(self.path,self.row)
        self.assertEqual(self.path.read_bytes(),weights())

    def test_generation_prevents_replacement(self):
        self.lock.acquire();self.addCleanup(self.lock.release)
        with patch('krea2_library.urlopen',return_value=io.BytesIO(self.new.read_bytes())):
            with self.assertRaisesRegex(ValueError,'Generation is active'):
                self.library.install(self.path,self.row)
        self.assertEqual(self.path.read_bytes(),weights())

    def test_invalid_tensor_file_rejected(self):
        self.new.write_bytes(b'<html>authentication required</html>')
        with self.assertRaises(ValueError):tensor_header(self.new)

    def test_source_versions_cannot_switch_base_model(self):
        current={'id':1,'modelId':7,'name':'v1','baseModel':'Krea 2'}
        matching={'id':2,'name':'v2','baseModel':'Krea 2','createdAt':'2026-10-01','files':[
            {'type':'Model','name':'x.safetensors','hashes':{'SHA256':'abc'},'downloadUrl':self.row['download']}]}
        wrong={**matching,'id':3,'baseModel':'Flux.1 D','createdAt':'2026-10-16'}
        with patch.object(self.library,'remote_json',side_effect=[current,{'id':7,'name':'Favorite','modelVersions':[wrong,matching]}]):
            row=self.library.resolve(self.path,{})
        self.assertEqual(row['latest'],'v2')

    def test_ambiguous_variants_are_not_automatically_chosen(self):
        version={'id':2,'baseModel':'Krea 2','files':[
            {'type':'Model','name':name,'hashes':{'SHA256':'abc'}} for name in ('a.safetensors','b.safetensors')]}
        with patch.object(self.library,'remote_json',side_effect=[{'id':1,'modelId':7,'baseModel':'Krea 2'}, {'modelVersions':[version]}]):
            with self.assertRaisesRegex(ValueError,'Multiple'):
                self.library.resolve(self.path,{})
        self.assertEqual(self.library.rows[self.path.name]['source_url'],'https://civitai.com/models/7')

    def test_restore_cannot_target_paths_outside_library(self):
        with self.assertRaisesRegex(ValueError,'Invalid LoRA filename'):
            self.library.restore('../other.safetensors')

    def test_cross_host_download_redirect_drops_credentials(self):
        request=Request('https://civitai.com/api/download/models/123',headers={'Authorization':'Bearer test-secret'})
        redirect=ScopedRedirect().redirect_request(request,None,302,'Found',{},'https://cdn.example.com/file')
        self.assertFalse(redirect.has_header('Authorization'))

    def test_cannot_downgrade_to_older_public_release(self):
        current={'id':2,'modelId':7,'baseModel':'Krea 2','name':'new','createdAt':'2026-10-16'}
        older={'id':1,'baseModel':'Krea 2','createdAt':'2026-01-01'}
        with patch.object(self.library,'remote_json',side_effect=[current,{'id':7,'modelVersions':[older]}]):
            result=self.library.resolve(self.path,{})
        self.assertEqual(result['status'],'No newer compatible public version')


if __name__=='__main__':unittest.main()
