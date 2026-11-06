import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import app_update
import maintenance


def source_archive(extra=None):
    files = {'app.py': b'VERSION = 2\n', 'engine.py': b'VERSION = 2\n',
             'maintenance.py': b'VERSION = 2\n', 'requirements.txt': b'gallery-dl\n'}
    files.update(extra or {})
    result = io.BytesIO()
    with zipfile.ZipFile(result, 'w') as archive:
        for name, data in files.items():
            archive.writestr('project-commit/' + name, data)
    return result.getvalue()


class UpdateTests(unittest.TestCase):
    def test_zip_update_backs_up_sources_and_preserves_session(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp)
            (root / 'app.py').write_text('VERSION = 1\n', encoding='utf-8')
            profile = root / '.browser-profile'
            profile.mkdir()
            (profile / 'session').write_bytes(b'private')
            with patch('app_update.APP_DIR', root):
                archive = source_archive({'.browser-profile/session': b'overwritten',
                                          '.venv/pyvenv.cfg': b'overwritten',
                                          '../outside.py': b'overwritten',
                                          'INSTALL.bat': b'@echo off\ncall :check\n:check\nexit /b 0\n'})
                self.assertTrue(app_update.install_archive(archive, 'a' * 40))
                self.assertFalse(app_update.install_archive(archive, 'a' * 40))
            self.assertEqual((root / 'app.py').read_text(), 'VERSION = 2\n')
            self.assertEqual((profile / 'session').read_bytes(), b'private')
            self.assertFalse((root / '.venv').exists())
            self.assertIn(b'\r\n', (root / 'INSTALL.bat').read_bytes())
            backup = list((root / '.update-backups').glob('*/old/app.py'))
            self.assertEqual(len(backup), 1)
            self.assertEqual(backup[0].read_text(), 'VERSION = 1\n')

    def test_invalid_zip_source_is_rejected_before_replacement(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp)
            (root / 'app.py').write_bytes(b'original')
            with patch('app_update.APP_DIR', root):
                with self.assertRaises(SyntaxError):
                    app_update.install_archive(source_archive({'maintenance.py': b'def broken('}), 'a' * 40)
            self.assertEqual((root / 'app.py').read_bytes(), b'original')

    def test_git_update_preserves_local_code_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.git').mkdir()
            def git_response(*args, **kwargs):
                value = ('https://github.com/' + app_update.REPOSITORY + '.git\n'
                         if args[0] == 'remote' else ' M engine.py\n')
                return subprocess.CompletedProcess([], 0, stdout=value)
            with patch('app_update.APP_DIR', root), \
                    patch('app_update.git', side_effect=git_response) as git:
                with self.assertRaisesRegex(RuntimeError, 'Local code changes'):
                    app_update.update_application()
            self.assertFalse(any(c.args[0] in ('fetch', 'merge') for c in git.call_args_list))

    def test_git_update_migrates_the_previous_repository_name(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            root = Path(tmp)
            (root / '.git').mkdir()
            def git_response(*args, **kwargs):
                if args[:3] == ('remote', 'get-url', 'origin'):
                    value = 'https://github.com/' + app_update.LEGACY_REPOSITORY + '.git\n'
                elif args[0] == 'branch':
                    value = 'main\n'
                elif args[0] == 'rev-parse':
                    value = 'a' * 40 + '\n'
                else:
                    value = ''
                return subprocess.CompletedProcess([], 0, stdout=value)
            with patch('app_update.APP_DIR', root), \
                    patch('app_update.git', side_effect=git_response) as git:
                self.assertFalse(app_update.update_application())
            git.assert_any_call('remote', 'set-url', 'origin',
                                'https://github.com/' + app_update.REPOSITORY + '.git')

    def test_reloaded_updater_failure_propagates_to_gui(self):
        with patch.object(sys, 'argv', ['maintenance.py']), \
                patch('app_update.update_application', return_value=True), \
                patch('maintenance.subprocess.run', return_value=subprocess.CompletedProcess([], 7)), \
                patch('maintenance.update') as update:
            with self.assertRaises(SystemExit) as result:
                maintenance.main()
            self.assertEqual(result.exception.code, 7)
            update.assert_not_called()


if __name__ == '__main__':
    unittest.main()
