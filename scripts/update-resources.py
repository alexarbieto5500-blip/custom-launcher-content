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
    if mod['kind'] not in ('shader', 'resourcepack'):
        raise ValueError('Tipo de recurso invalido')
    project = mod['project_id']
    if not re.fullmatch(r'[A-Za-z0-9_-]+', project):
        raise ValueError('ID de proyecto invalido')
    with request(f'{API}/project/{project}') as response:
        metadata = json.load(response)
    if metadata['project_type'] != mod['kind']:
        raise ValueError('Tipo de proyecto incompatible')
    query = urlencode({'game_versions': json.dumps([config['minecraft_version']])})
    with request(f'{API}/project/{project}/version?{query}') as response:
        versions = json.load(response)
    versions = [v for v in versions if v['version_type'] == mod['release_channel'] and config['minecraft_version'] in v['game_versions'] and bool(set(v['loaders']) & set(mod['loaders']))]
    if not versions:
        raise ValueError('Sin versiones compatibles: ' + mod['id'])
    version = max(versions, key=lambda v: v['date_published'])
    files = [f for f in version['files'] if f['filename'].endswith('.zip')]
    primary = [f for f in files if f['primary']]
    if len(primary) != 1 and len(files) != 1:
        raise ValueError('No se puede identificar el ZIP principal')
    file = primary[0] if len(primary) == 1 else files[0]
    name = file['filename']
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 ._+\-]*\.zip', name) or len(name) > 200 or re.fullmatch(r'CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9]', name.split('.')[0].strip(), re.I):
        raise ValueError('Nombre de archivo invalido')
    url = file['url']
    if urlparse(url).scheme != 'https' or urlparse(url).hostname != 'cdn.modrinth.com':
        raise ValueError('Origen de descarga no permitido')
    sha512 = hashlib.sha512()
    sha256 = hashlib.sha256()
    size = 0
    if not 0 < file['size'] <= 512 * 1024 * 1024:
        raise ValueError('Tamano fuera del limite')
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
    return {'id': mod['id'], 'kind': mod['kind'], 'name': mod['name'], 'provider': 'modrinth', 'project_id': version['project_id'], 'version_id': version['id'], 'version': version['version_number'], 'file_name': name, 'url': url, 'sha512': sha512.hexdigest(), 'sha256': sha256.hexdigest(), 'size': size, 'required': mod['required'], 'dependencies': [d for d in version.get('dependencies', []) if d['dependency_type'] == 'required']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--approve', action='store_true', help='Aprobar el manifiesto propuesto existente')
    args = parser.parse_args()
    proposed = MANIFESTS / 'resources-proposed.json'
    approved = MANIFESTS / 'resources-manifest.json'
    config = read_json(MANIFESTS / 'resources-sources.json')
    if config['schema_version'] != 1 or config['minecraft_version'] != '1.21.1' or config['mod_loader'] != 'fabric':
        raise ValueError('Configuracion incompatible')
    if args.approve:
        data = read_json(proposed)
        enabled = {m['id'] for m in config['resources'] if m['enabled']}
        if data['minecraft_version'] != config['minecraft_version'] or data['mod_loader'] != config['mod_loader'] or {m['id'] for m in data['resources']} != enabled:
            raise ValueError('La propuesta no coincide con la configuracion actual')
        if any(m['dependencies'] for m in data['resources']):
            raise ValueError('Hay dependencias requeridas pendientes de resolver')
        sources = {m['id']: m for m in config['resources'] if m['enabled']}
        for item in data['resources']:
            source = sources[item['id']]
            if item['kind'] != source['kind'] or item['required'] != source['required']:
                raise ValueError('La propuesta no coincide con la fuente')
        old = read_json(approved) if approved.exists() else {}
        if {k: v for k, v in old.items() if k != 'revision'} == data:
            print('Sin cambios en el manifiesto aprobado')
            return
        data['revision'] = old.get('revision', 0) + 1
        save_json(approved, data)
        print('Manifiesto aprobado:', approved)
        return
    mods = []
    for mod in config['resources']:
        if mod['enabled']:
            result = resolve(mod, config)
            mods.append(result)
            print(result['name'], result['version'], 'verificado')
    data = {'manifest_version': 1, 'minecraft_version': config['minecraft_version'], 'mod_loader': config['mod_loader'], 'resources': mods}
    if len({(m['kind'], m['file_name'].lower()) for m in mods}) != len(mods):
        raise ValueError('Archivos duplicados')
    save_json(proposed, data)
    print('Propuesta generada:', proposed)
    print('Revisa la propuesta antes de aprobarla con --approve.')


if __name__ == '__main__':
    main()
