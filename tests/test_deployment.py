"""Guard packaging/config boundaries without touching a server or database."""
import io
import tarfile
import pytest
from deploy import install_guest


def archive_with(path, name, kind=tarfile.REGTYPE):
    with tarfile.open(path, 'w:gz') as archive:
        member = tarfile.TarInfo(name)
        member.type = kind
        member.size = 4 if kind == tarfile.REGTYPE else 0
        archive.addfile(member, io.BytesIO(b'test') if member.size else None)


@pytest.mark.parametrize('name,kind', [('../outside.txt', tarfile.REGTYPE), ('symlink', tarfile.SYMTYPE)])
def test_release_unpack_rejects_escaping_paths_and_links(tmp_path, name, kind):
    source = tmp_path / 'release.tar.gz'
    archive_with(source, name, kind)
    with pytest.raises(RuntimeError, match='Unexpected'):
        install_guest.unpack(source, tmp_path / 'release')
    assert not (tmp_path / 'outside.txt').exists()


def test_release_unpack_refuses_overwriting_previous_files(tmp_path):
    source = tmp_path / 'release.tar.gz'
    archive_with(source, 'backend/app.py')
    install_guest.unpack(source, tmp_path / 'release')
    file = tmp_path / 'release/backend/app.py'
    file.write_text('existing user work')
    with pytest.raises(FileExistsError):
        install_guest.unpack(source, tmp_path / 'release')
    assert file.read_text() == 'existing user work'


def test_environment_roundtrip_preserves_secret_and_encoded_unix_socket(tmp_path, monkeypatch):
    config = tmp_path / 'app.env'
    monkeypatch.setattr(install_guest, 'CONFIG', config)
    values = {'SECRET_KEY':'test-value+percent%and=equals',
        'MONGODB_URI':'mongodb://test:fixture@%2Frun%2Fmongo.sock/makanwhere?authSource=makanwhere&directConnection=true'}
    install_guest.write_environment(values)
    assert install_guest.read_environment(config) == values
    install_guest.write_environment(dict(values, PASSWORD_PEPPER='test-pepper'))
    assert install_guest.read_environment(config)['SECRET_KEY'] == values['SECRET_KEY']


def test_multiline_environment_is_rejected_without_replacing_current_config(tmp_path, monkeypatch):
    config = tmp_path / 'app.env'
    monkeypatch.setattr(install_guest, 'CONFIG', config)
    config.write_text('SECRET_KEY=existing\n')
    with pytest.raises(RuntimeError, match='Multiline'):
        install_guest.write_environment({'SECRET_KEY':'bad\nINJECTED=true'})
    assert config.read_text() == 'SECRET_KEY=existing\n'
