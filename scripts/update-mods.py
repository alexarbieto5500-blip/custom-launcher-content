import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
MANIFESTS = ROOT / 'manifests'
API = 'https://api.modrinth.com/v2'
AGENT = 'alexarbieto5500-blip/custom-launcher-content (https://github.com/alexarbieto5500-blip/custom-launcher-content)'


def request(url):
    return urlopen(Request(url, headers={'User-Agent': AGENT}), timeout=60)


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def save_json(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def resolve(mod, config):
    if mod['provider'] != 'modrinth':
        raise ValueError('Proveedor no soportado: ' + mod['provider'])
    project = mod['project_id']
    if not re.fullmatch(r'[A-Za-z0-9_-]+', project):
        raise ValueError('ID de proyecto invalido')
    query = urlencode({'loaders': json.dumps([config['mod_loader']]), 'game_versions': json.dumps([config['minecraft_version']])})
    with request(f'{API}/project/{project}/version?{query}') as response:
        versions = json.load(response)
    versions = [v for v in versions if v['version_type'] == mod['release_channel'] and config['minecraft_version'] in v['game_versions'] and config['mod_loader'] in v['loaders']]
    if not versions:
        raise ValueError('Sin versiones compatibles: ' + mod['id'])
    version = max(versions, key=lambda v: v['date_published'])
    files = [f for f in version['files'] if f['filename'].endswith('.jar')]
    primary = [f for f in files if f['primary']]
    if len(primary) != 1 and len(files) != 1:
        raise ValueError('No se puede identificar el JAR principal')
    file = primary[0] if len(primary) == 1 else files[0]
    name = file['filename']
    if not re.fullmatch(r'[A-Za-z0-9._+\-]+\.jar', name):
        raise ValueError('Nombre de archivo invalido')
    url = file['url']
    if urlparse(url).scheme != 'https' or urlparse(url).hostname != 'cdn.modrinth.com':
        raise ValueError('Origen de descarga no permitido')
    sha512 = hashlib.sha512()
    sha256 = hashlib.sha256()
    size = 0
    with request(url) as response:
        if urlparse(response.geturl()).hostname != 'cdn.modrinth.com' or urlparse(response.geturl()).scheme != 'https':
            raise ValueError('Redireccion no permitida')
        while chunk := response.read(1024 * 1024):
            size += len(chunk)
            if size > file['size']:
                raise ValueError('Tamano superior al esperado')
            sha512.update(chunk)
            sha256.update(chunk)
    if size != file['size'] or sha512.hexdigest() != file['hashes']['sha512'].lower():
        raise ValueError('Fallo de integridad: ' + name)
    return {'id': mod['id'], 'name': mod['name'], 'provider': 'modrinth', 'project_id': version['project_id'], 'version_id': version['id'], 'version': version['version_number'], 'file_name': name, 'url': url, 'sha256': sha256.hexdigest(), 'size': size, 'required': mod['required'], 'dependencies': [d for d in version.get('dependencies', []) if d['dependency_type'] == 'required']}


def validate_dependencies(mods):
    for mod in mods:
        for dep in mod['dependencies']:
            project = dep.get('project_id')
            version = dep.get('version_id')
            if not project and not version:
                raise ValueError('Dependencia sin identificador: ' + mod['name'])
            matches = [m for m in mods if m['required'] and (not project or m['project_id'] == project) and (not version or m['version_id'] == version)]
            if not matches:
                raise ValueError(f"Dependencia no satisfecha: {mod['name']} requiere proyecto {project}, version {version}")
            print('Dependencia satisfecha:', mod['name'], '->', matches[0]['name'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--approve', action='store_true', help='Aprobar el manifiesto propuesto existente')
    args = parser.parse_args()
    proposed = MANIFESTS / 'mods-proposed.json'
    approved = MANIFESTS / 'mods-manifest.json'
    config = read_json(MANIFESTS / 'mods-sources.json')
    if args.approve:
        data = read_json(proposed)
        enabled = {m['id'] for m in config['mods'] if m['enabled']}
        if data['minecraft_version'] != config['minecraft_version'] or data['mod_loader'] != config['mod_loader'] or {m['id'] for m in data['mods']} != enabled:
            raise ValueError('La propuesta no coincide con la configuracion actual')
        validate_dependencies(data['mods'])
        old = read_json(approved) if approved.exists() else {}
        data['revision'] = old.get('revision', 0) + 1
        save_json(approved, data)
        print('Manifiesto aprobado:', approved)
        return
    mods = []
    for mod in config['mods']:
        if mod['enabled']:
            result = resolve(mod, config)
            mods.append(result)
            print(result['name'], result['version'], 'verificado')
    data = {'manifest_version': 1, 'minecraft_version': config['minecraft_version'], 'mod_loader': config['mod_loader'], 'mods': mods}
    save_json(proposed, data)
    print('Propuesta generada:', proposed)
    validate_dependencies(mods)
    print('Revisa la propuesta antes de aprobarla con --approve.')


if __name__ == '__main__':
    main()
